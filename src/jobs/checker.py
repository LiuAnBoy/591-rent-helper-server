"""
Listing Checker Module.

Checks for new objects and triggers notifications.
"""

import asyncio

from loguru import logger

from src.connections.postgres import PostgresConnection, get_postgres
from src.connections.redis import RedisConnection, get_redis
from src.crawler.combiner import combine_raw_data, combine_with_list_only
from src.crawler.detail_fetcher import DetailFetcher, get_detail_fetcher
from src.crawler.list_fetcher import ListFetcher, get_list_fetcher
from src.crawler.types import DetailRawData, ListRawData
from src.jobs.broadcaster import Broadcaster, ErrorType, get_broadcaster
from src.matching import filter_objects, match_object_to_subscription
from src.modules.objects import ObjectRepository
from src.utils import (
    DBReadyData,
    transform_to_db_ready,
)

checker_log = logger.bind(module="Checker")


class Checker:
    """
    Checker for new rental objects.

    Workflow:
    1. Get active regions from Redis subscriptions
    2. For each region:
       - If not initialized: crawl 5 items, save, NO notify, mark initialized
       - If initialized: crawl 10 items, compare seen_ids, match subscriptions, notify
    3. All matching done in Redis (no PostgreSQL queries during crawl)
    """

    # Pagination settings
    PAGE_SIZE = 30  # Items per page
    MAX_PAGES = 2  # Maximum pages to fetch (60 items max)

    def __init__(
        self,
        postgres: PostgresConnection | None = None,
        redis: RedisConnection | None = None,
        list_fetcher: ListFetcher | None = None,
        detail_fetcher: DetailFetcher | None = None,
        broadcaster: Broadcaster | None = None,
        enable_broadcast: bool = True,
        detail_max_workers: int = 3,
    ):
        """
        Initialize Checker.

        Args:
            postgres: PostgreSQL connection (will be created if not provided)
            redis: Redis connection (will be created if not provided)
            list_fetcher: List fetcher instance (will be created if not provided)
            detail_fetcher: Detail fetcher with bs4 + Playwright fallback
            broadcaster: Broadcaster instance (will be created if not provided)
            enable_broadcast: Whether to send notifications (default True)
            detail_max_workers: Max parallel workers for detail page fetching
        """
        self._postgres = postgres
        self._redis = redis
        self._list_fetcher = list_fetcher
        self._detail_fetcher = detail_fetcher
        self._broadcaster = broadcaster
        self._enable_broadcast = enable_broadcast
        self._detail_max_workers = detail_max_workers
        self._owns_fetcher = False
        self._object_repo: ObjectRepository | None = None

    async def _ensure_connections(self) -> None:
        """Ensure all connections are established."""
        if self._postgres is None:
            self._postgres = await get_postgres()
        if self._redis is None:
            self._redis = await get_redis()
        if self._object_repo is None:
            self._object_repo = ObjectRepository(self._postgres.pool)
        if self._list_fetcher is None:
            self._list_fetcher = get_list_fetcher(headless=True)
            self._owns_fetcher = True
            await self._list_fetcher.start()
        if self._detail_fetcher is None:
            self._detail_fetcher = get_detail_fetcher(
                playwright_max_workers=self._detail_max_workers
            )
            await self._detail_fetcher.start()
        if self._broadcaster is None and self._enable_broadcast:
            self._broadcaster = get_broadcaster()

    async def close(self) -> None:
        """Close owned resources."""
        if self._owns_fetcher and self._list_fetcher:
            await self._list_fetcher.close()
        if self._detail_fetcher:
            await self._detail_fetcher.close()

    async def sync_subscriptions_to_redis(self) -> int:
        """
        Sync all enabled subscriptions from PostgreSQL to Redis.
        Should be called at server startup.

        Returns:
            Number of subscriptions synced
        """
        await self._ensure_connections()

        from src.modules.subscriptions import SubscriptionRepository

        repo = SubscriptionRepository(self._postgres.pool)

        # Get all enabled subscriptions from PostgreSQL
        subscriptions = await repo.get_all_enabled()

        # Sync to Redis
        await self._redis.sync_subscriptions(subscriptions)

        checker_log.info(f"Synced {len(subscriptions)} subscriptions to Redis")
        return len(subscriptions)

    def _transform_object(
        self,
        list_data: ListRawData,
        detail_data: DetailRawData | None,
        region: int,
    ) -> DBReadyData:
        """
        Transform raw data to DB-ready format (no I/O operations).

        ETL Flow:
        1. Combine: list_data + detail_data → CombinedRawData
        2. Transform: CombinedRawData → DBReadyData

        Args:
            list_data: Raw data from list page
            detail_data: Raw data from detail page (can be None)
            region: Region code

        Returns:
            DBReadyData dict (for subscription matching)
        """
        # Step 1: Combine raw data
        if detail_data:
            combined = combine_raw_data(list_data, detail_data)
        else:
            # If detail fetch failed, use list data only
            combined = combine_with_list_only(list_data)

        # Step 2: Transform to DB-ready format
        return transform_to_db_ready(combined)

    async def _save_objects_batch(
        self,
        objects: list[DBReadyData],
        region: int,
    ) -> None:
        """
        Batch save objects to DB and Redis.

        Args:
            objects: List of DBReadyData to save
            region: Region code
        """
        if not objects:
            return

        # Save to DB (batch UPSERT)
        inserted = await self._object_repo.save_batch(objects)
        checker_log.info(f"Batch saved {len(objects)} objects ({inserted} new)")

        # Add to Redis seen set (batch)
        all_ids = {obj["id"] for obj in objects}
        await self._redis.add_seen_ids(region, all_ids)

        # Update Redis region objects cache (incremental, no delete)
        await self._redis.update_region_objects(region, objects)

        # Log summary
        id_list = ", ".join(str(obj["id"]) for obj in objects)
        checker_log.info(f"Saved {len(objects)} new objects: {id_list}")

    async def _match_subscriptions_in_redis(self, region: int, obj: dict) -> list[dict]:
        """
        Find matching subscriptions for an object from Redis.

        Args:
            region: Region code
            obj: Object data

        Returns:
            List of matching subscription dicts
        """
        subscriptions = await self._redis.get_subscriptions_by_region(region)
        matches = []

        for sub in subscriptions:
            if match_object_to_subscription(obj, sub):
                matches.append(sub)

        return matches

    async def check(
        self,
        region: int,
        force_notify: bool = False,
    ) -> dict:
        """
        Check for new objects in a region.

        Flow:
        1. Crawl list pages with auto-pagination (up to MAX_PAGES)
        2. Redis filter: find new IDs only
        3. For each new object:
           - Fetch detail (BS4 → Playwright fallback)
           - Merge list + detail data
           - Save to DB (single write)
           - Update Redis (seen set + object cache)
        4. Subscription matching
        5. Push notifications

        Args:
            region: City code (1=Taipei, 3=New Taipei)
            force_notify: Force notifications even for uninitialized subs (for testing)

        Returns:
            Dict with check results
        """
        await self._ensure_connections()

        checker_log.info(f"Checking region={region}")

        # Start crawler run tracking
        run_id = await self._postgres.start_crawler_run(region)

        try:
            # Step 1: Fetch list with auto-pagination
            # If page 1 is all new items, automatically fetch page 2
            all_list_items: list[ListRawData] = []
            all_new_ids: set[int] = set()
            total_fetched = 0
            pages_fetched = 0

            for page in range(self.MAX_PAGES):
                first_row = page * self.PAGE_SIZE

                # Fetch page
                page_items = await self._list_fetcher.fetch_objects_raw(
                    region=region,
                    sort="posttime_desc",
                    first_row=first_row,
                )

                if not page_items:
                    if page == 0:
                        # First page failed - this is an error
                        checker_log.warning("No objects fetched from page 1")
                        if self._broadcaster:
                            await self._broadcaster.notify_admin(
                                error_type=ErrorType.LIST_FETCH_FAILED,
                                region=region,
                                details="ListFetcher 無法抓取列表頁 (ETL raw)",
                            )
                        await self._postgres.finish_crawler_run(
                            run_id=run_id,
                            status="success",
                            total_fetched=0,
                            new_objects=0,
                        )
                        return {
                            "region": region,
                            "fetched": 0,
                            "new_count": 0,
                            "matches": [],
                            "detail_fetched": 0,
                            "broadcast": {"total": 0, "success": 0, "failed": 0},
                            "initialized_subs": [],
                        }
                    # Later pages empty - just stop pagination
                    break

                pages_fetched += 1
                total_fetched += len(page_items)

                # Check which items are new (skip items with empty ID)
                page_ids = {int(item["id"]) for item in page_items if item.get("id")}
                new_ids_in_page = await self._redis.get_new_ids(region, page_ids)

                # Collect new items
                for item in page_items:
                    if item.get("id") and int(item["id"]) in new_ids_in_page:
                        all_list_items.append(item)
                        all_new_ids.add(int(item["id"]))

                checker_log.info(
                    f"Page {page + 1}: {len(new_ids_in_page)}/{len(page_items)} new"
                )

                # Decide if we need next page
                if len(new_ids_in_page) < len(page_items):
                    # Found some old items, no need for next page
                    break

                # All items are new, might need next page
                if page < self.MAX_PAGES - 1:
                    checker_log.info("All items are new, fetching next page...")
                    await asyncio.sleep(1)  # Rate limit between pages

            # Log summary
            if pages_fetched > 1:
                checker_log.info(
                    f"Fetched {total_fetched} objects from {pages_fetched} pages, "
                    f"{len(all_new_ids)} new"
                )
            else:
                checker_log.info(
                    f"Fetched {total_fetched} objects from list, {len(all_new_ids)} new"
                )

            # Use collected data for rest of flow
            list_raw_items = all_list_items
            new_ids = all_new_ids

            # Initialize result variables
            matches = []
            initialized_subs = []
            broadcast_result = {"total": 0, "success": 0, "failed": 0, "details": [], "failures": []}
            detail_fetched = 0
            detail_not_found = 0
            detail_failed = 0
            processed_objects = []

            # Track pre-filter stats for result
            pre_filter_input = 0
            pre_filter_output = 0
            pre_filter_skipped = 0

            if new_ids:
                # Build lookup dict for list raw data (skip empty IDs)
                list_data_by_id = {
                    int(item["id"]): item for item in list_raw_items if item.get("id")
                }

                # Get only NEW items for pre-filtering
                new_items = [
                    list_data_by_id[oid] for oid in new_ids if oid in list_data_by_id
                ]

                # Step 2.5: Pre-filter before detail fetch
                # Only fetch detail for objects that might match some subscription
                all_subs = await self._redis.get_subscriptions_by_region(region)

                pre_filter_input = len(new_items)
                details: dict[int, DetailRawData] = {}

                if all_subs:
                    filtered_items, pre_filter_skipped = filter_objects(
                        new_items, all_subs
                    )
                    pre_filter_output = len(filtered_items)

                    # Get IDs from filtered items (need detail)
                    ids_need_detail = [int(item["id"]) for item in filtered_items]

                    checker_log.info(
                        f"Pre-filter: {pre_filter_input} → {pre_filter_output} "
                        f"(skipped {pre_filter_skipped} by pre-filter)"
                    )

                    # Step 3: Fetch detail raw data for filtered items only
                    if ids_need_detail:
                        await asyncio.sleep(1)
                        checker_log.info(
                            f"Fetching detail for {len(ids_need_detail)} objects (ETL)"
                        )

                        (
                            details,
                            detail_not_found,
                            detail_failed,
                        ) = await self._detail_fetcher.fetch_details_batch_raw(
                            ids_need_detail
                        )
                        detail_fetched = len(details)

                        # Notify admin only for actual errors (not 404s)
                        if detail_failed > 0 and self._broadcaster:
                            failed_ids = [
                                oid for oid in ids_need_detail if oid not in details
                            ]
                            await self._broadcaster.notify_admin(
                                error_type=ErrorType.DETAIL_FETCH_FAILED,
                                region=region,
                                details=f"{detail_failed} detail pages failed\nIDs: {failed_ids[:5]}{'...' if len(failed_ids) > 5 else ''}",
                            )
                else:
                    # No subscriptions = nothing to match, skip all detail fetches
                    pre_filter_output = 0
                    pre_filter_skipped = pre_filter_input
                    checker_log.info(
                        f"No subscriptions for region {region}, skipping detail fetch"
                    )

                # Step 4: Transform ALL new objects (with or without detail)
                # Objects with detail → has_detail=true
                # Objects without detail → has_detail=false
                for object_id in new_ids:
                    if object_id not in list_data_by_id:
                        continue
                    list_data = list_data_by_id[object_id]
                    detail_data = details.get(object_id)  # None if not fetched
                    processed_obj = self._transform_object(
                        list_data, detail_data, region
                    )
                    processed_objects.append(processed_obj)

                # Step 5: Batch save ALL new objects to DB and Redis
                if processed_objects:
                    await self._save_objects_batch(processed_objects, region)

                # Step 6: Subscription matching (only for objects with detail)
                # Reuse all_subs from pre-filter step (already fetched above)
                uninitialized_subs = await self._redis.get_uninitialized_subscriptions(
                    all_subs
                )
                uninitialized_ids = {sub["id"] for sub in uninitialized_subs}

                # Only match objects with has_detail=true
                objects_with_detail = [
                    obj for obj in processed_objects if obj.get("has_detail", False)
                ]

                for obj in objects_with_detail:
                    # obj is already DBReadyData (dict), no conversion needed

                    for sub in all_subs:
                        if not match_object_to_subscription(obj, sub):
                            continue

                        sub_id = sub["id"]
                        if sub_id in uninitialized_ids:
                            # Uninitialized subscription - mark as initialized, don't notify
                            if sub_id not in initialized_subs:
                                initialized_subs.append(sub_id)
                        else:
                            # Initialized subscription - match and notify
                            matches.append((obj, [sub]))
                            checker_log.info(
                                f"Object {obj['id']} matches subscription {sub_id}"
                            )

                # Mark uninitialized subscriptions as initialized
                for sub_id in initialized_subs:
                    await self._redis.mark_subscription_initialized(sub_id)
                    checker_log.info(
                        f"Subscription {sub_id} initialized (first run, no notifications)"
                    )

                # Step 6: Broadcast notifications
                if matches and self._enable_broadcast and self._broadcaster:
                    # Group matches by object
                    object_subs_map: dict[int, tuple[DBReadyData, list[dict]]] = {}
                    for obj, subs in matches:
                        if obj["id"] not in object_subs_map:
                            object_subs_map[obj["id"]] = (obj, [])
                        object_subs_map[obj["id"]][1].extend(subs)

                    grouped_matches = list(object_subs_map.values())
                    checker_log.info(f"Broadcasting {len(grouped_matches)} matches...")
                    broadcast_result = await self._broadcaster.broadcast(
                        grouped_matches
                    )

                    # Save notification logs to DB (success + failed)
                    notification_details = broadcast_result.get("details", [])
                    if notification_details:
                        try:
                            await self._postgres.save_notification_logs_batch(
                                notification_details, crawler_run_id=run_id
                            )
                        except Exception as e:
                            # Handle stale subscription (exists in Redis but not in PostgreSQL)
                            if "foreign key constraint" in str(e).lower():
                                checker_log.warning(
                                    f"Stale subscription found in Redis "
                                    f"(not in PostgreSQL). Skipping log save: {e}"
                                )
                            else:
                                checker_log.error(
                                    f"Failed to save notification logs: {e}"
                                )

                    # Notify admin only if some broadcasts failed
                    failures = broadcast_result.get("failures", [])
                    if failures:
                        failure_lines = [
                            f"- {f['provider_id']}: {f['error']}"
                            for f in failures[:10]
                        ]
                        truncated = (
                            f"\n... 及其他 {len(failures) - 10} 筆"
                            if len(failures) > 10
                            else ""
                        )
                        await self._broadcaster.notify_admin(
                            error_type=ErrorType.BROADCAST_ERROR,
                            region=region,
                            details=(
                                f"推播失敗: {broadcast_result['failed']}/{broadcast_result['total']}\n"
                                + "\n".join(failure_lines)
                                + truncated
                            ),
                        )

            # Finish crawler run
            await self._postgres.finish_crawler_run(
                run_id=run_id,
                status="success",
                total_fetched=total_fetched,
                new_objects=len(new_ids),
            )

            result = {
                "region": region,
                "fetched": total_fetched,
                "new_count": len(new_ids),
                "pre_filter_input": pre_filter_input,
                "pre_filter_output": pre_filter_output,
                "pre_filter_skipped": pre_filter_skipped,
                "detail_fetched": detail_fetched,
                "detail_not_found": detail_not_found,
                "detail_failed": detail_failed,
                "matches": matches,
                "broadcast": broadcast_result,
                "initialized_subs": initialized_subs,
            }

            # Build log message
            log_parts = [
                f"Check complete: region={region}",
                f"fetched={result['fetched']}",
                f"new={result['new_count']}",
            ]
            if pre_filter_input > 0:
                log_parts.append(f"pre-filter={pre_filter_output}/{pre_filter_input}")
            # Detail stats: fetched/not_found/failed
            detail_stats = f"detail={detail_fetched}"
            if detail_not_found > 0 or detail_failed > 0:
                detail_stats += f"({detail_not_found} not_found"
                if detail_failed > 0:
                    detail_stats += f", {detail_failed} failed"
                detail_stats += ")"
            log_parts.append(detail_stats)
            log_parts.extend(
                [
                    f"matches={len(matches)}",
                    f"initialized={len(initialized_subs)}",
                    f"notified={broadcast_result['success']}/{broadcast_result['total']}",
                ]
            )
            checker_log.info(" ".join(log_parts))

            return result

        except Exception as e:
            checker_log.error(f"Check failed: {e}")

            # Notify admin about the error
            if self._broadcaster:
                # Classify error type
                error_str = str(e).lower()
                if (
                    "postgres" in error_str
                    or "database" in error_str
                    or "sql" in error_str
                ):
                    error_type = ErrorType.DB_ERROR
                elif "redis" in error_str:
                    error_type = ErrorType.REDIS_ERROR
                else:
                    error_type = ErrorType.UNKNOWN_ERROR

                await self._broadcaster.notify_admin(
                    error_type=error_type,
                    region=region,
                    details=str(e)[:500],  # Limit error message length
                )

            await self._postgres.finish_crawler_run(
                run_id=run_id,
                status="failed",
                total_fetched=0,
                new_objects=0,
                error_message=str(e),
            )
            raise

    async def check_active_regions(self) -> list[dict]:
        """
        Check all regions that have active subscriptions.
        Regions are determined from Redis subscription data.

        Returns:
            List of check results for each region
        """
        await self._ensure_connections()

        # Get active regions from Redis
        active_regions = await self._redis.get_active_regions()

        if not active_regions:
            checker_log.info("No active regions with subscriptions")
            return []

        checker_log.info(
            f"Found {len(active_regions)} active regions: {active_regions}"
        )

        results = []
        for region in sorted(active_regions):
            try:
                result = await self.check(region=region)
                results.append(result)
            except Exception as e:
                checker_log.error(f"Failed to check region {region}: {e}")
                results.append(
                    {
                        "region": region,
                        "error": str(e),
                        "fetched": 0,
                        "new_count": 0,
                        "matches": [],
                        "broadcast": {"total": 0, "success": 0, "failed": 0},
                    }
                )

        return results


async def main():
    """Test checker."""
    checker = Checker(enable_broadcast=False)

    try:
        # Sync subscriptions first
        await checker.sync_subscriptions_to_redis()

        # Check active regions
        results = await checker.check_active_regions()

        print("\n" + "=" * 50)
        print("Check Results")
        print("=" * 50)

        for result in results:
            region = result.get("region", "?")
            print(f"\nRegion {region}:")
            print(f"  Fetched: {result.get('fetched', 0)}")
            print(f"  New: {result.get('new_count', 0)}")
            print(f"  Matches: {len(result.get('matches', []))}")
            if result.get("initialized"):
                print("  (First run - no notifications)")
            if result.get("error"):
                print(f"  Error: {result['error']}")

    finally:
        await checker.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
