"""
Listing Checker Module.

Checks for new objects and triggers notifications.
"""

from loguru import logger

from src.connections.postgres import PostgresConnection, get_postgres
from src.connections.redis import RedisConnection, get_redis
from src.crawler.base import DetailBatch, Source
from src.crawler.contract import DBReadyData
from src.crawler.registry import get_source
from src.jobs.broadcaster import Broadcaster, ErrorType, get_broadcaster
from src.matching import filter_objects, match_object_to_subscription
from src.modules.objects import ObjectRepository

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
        source: Source | None = None,
        broadcaster: Broadcaster | None = None,
        enable_broadcast: bool = True,
        detail_max_workers: int = 3,
    ):
        """
        Initialize Checker.

        Args:
            postgres: PostgreSQL connection (will be created if not provided)
            redis: Redis connection (will be created if not provided)
            source: Crawl Source (defaults to the registered 591 source)
            broadcaster: Broadcaster instance (will be created if not provided)
            enable_broadcast: Whether to send notifications (default True)
            detail_max_workers: Max parallel workers for detail page fetching
        """
        self._postgres = postgres
        self._redis = redis
        self._source = source
        self._broadcaster = broadcaster
        self._enable_broadcast = enable_broadcast
        self._detail_max_workers = detail_max_workers
        self._owns_source = False
        self._object_repo: ObjectRepository | None = None

    async def _ensure_connections(self) -> None:
        """Ensure all connections are established."""
        if self._postgres is None:
            self._postgres = await get_postgres()
        if self._redis is None:
            self._redis = await get_redis()
        if self._object_repo is None:
            self._object_repo = ObjectRepository(self._postgres.pool)
        if self._source is None:
            # Single source for now; multi-source = loop registry.all_sources().
            self._source = get_source("591", self._redis)
            self._owns_source = True
            await self._source.start()
        if self._broadcaster is None and self._enable_broadcast:
            self._broadcaster = get_broadcaster()

    async def close(self) -> None:
        """Close owned resources."""
        if self._owns_source and self._source:
            await self._source.close()

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

        # Add to Redis seen set (batch) — tracked by source_id (591 listing id)
        all_ids = {obj["source_id"] for obj in objects}
        await self._redis.add_seen_ids(region, all_ids)

        # Update Redis region objects cache (incremental, no delete)
        await self._redis.update_region_objects(region, objects)

        # Log summary
        id_list = ", ".join(str(obj["source_id"]) for obj in objects)
        checker_log.info(f"Saved {len(objects)} new objects: {id_list}")

    async def _report_field_anomalies(
        self, objects: list[DBReadyData], region: int
    ) -> None:
        """
        Alert admin when always-present fields parse to empty (price/section/kind).

        Objects are still saved; this only surfaces likely 591 markup changes.

        Args:
            objects: Newly processed objects for this run
            region: Region code
        """
        checks = (
            ("價格(price=0)", lambda o: not o.get("price")),
            ("區域(section=0)", lambda o: not o.get("section")),
            ("房型(kind=0)", lambda o: not o.get("kind")),
        )

        anomalies: list[str] = []
        for label, is_bad in checks:
            ids = [obj["source_id"] for obj in objects if is_bad(obj)]
            if ids:
                shown = ", ".join(str(i) for i in ids[:10])
                more = "..." if len(ids) > 10 else ""
                anomalies.append(f"{label} {len(ids)} 筆: {shown}{more}")

        if not anomalies:
            return

        checker_log.warning(f"Field parse anomalies (region={region}): {anomalies}")
        if self._broadcaster:
            await self._broadcaster.notify_admin(
                error_type=ErrorType.FIELD_MISSING,
                region=region,
                details="\n".join(anomalies),
            )

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

        # Progress counters kept outside try so the except path can record
        # actual progress instead of overwriting it with zeros.
        all_new_ids: set[str] = set()
        total_fetched = 0

        try:
            # Whether this region has any crawl history yet. Captured BEFORE the
            # save step seeds the seen set. A region with no history (fresh start,
            # flushed/expired seen set, brand-new region) must treat this round as
            # a silent baseline — otherwise every current listing looks "new" and,
            # if subs are already initialized, the whole page gets notified.
            region_has_history = await self._redis.has_seen_ids(region)

            # Step 1: Source crawls the region's list pages and returns NEW,
            # standardized listings (it owns pagination + the seen-set early-stop).
            list_batch = await self._source.fetch_list(region, self.MAX_PAGES)
            total_fetched = list_batch.total_fetched

            if total_fetched == 0:
                # First list page returned nothing -> fetch failure.
                checker_log.warning("No objects fetched from page 1")
                if self._broadcaster:
                    await self._broadcaster.notify_admin(
                        error_type=ErrorType.LIST_FETCH_FAILED,
                        region=region,
                        details="ListFetcher 無法抓取列表頁 (ETL raw)",
                    )
                await self._postgres.finish_crawler_run(
                    run_id=run_id,
                    status="failed",
                    total_fetched=0,
                    new_objects=0,
                    error_message="No objects fetched from page 1",
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

            # Standardized, has_detail=False, already de-duplicated to new only.
            new_items = list_batch.items
            new_ids = {item["source_id"] for item in new_items}
            all_new_ids = set(new_ids)

            # Initialize result variables
            matches = []
            initialized_subs = []
            broadcast_result = {"total": 0, "success": 0, "failed": 0, "failures": []}
            broadcast_errors_str = None
            detail_fetched = 0
            detail_not_found = 0
            detail_failed = 0
            processed_objects = []

            # Track pre-filter stats for result
            pre_filter_input = 0
            pre_filter_output = 0
            pre_filter_skipped = 0

            if new_items:
                # Step 2: Pre-filter (on standardized data) before detail fetch.
                # Only enrich objects that might match some subscription.
                all_subs = await self._redis.get_subscriptions_by_region(region)

                pre_filter_input = len(new_items)
                detail_batch = DetailBatch()

                if all_subs:
                    candidates, pre_filter_skipped = filter_objects(new_items, all_subs)
                    pre_filter_output = len(candidates)

                    checker_log.info(
                        f"Pre-filter: {pre_filter_input} → {pre_filter_output} "
                        f"(skipped {pre_filter_skipped} by pre-filter)"
                    )

                    # Step 3: Source fetches detail for the candidates only.
                    if candidates:
                        checker_log.info(
                            f"Fetching detail for {len(candidates)} objects (ETL)"
                        )
                        detail_batch = await self._source.fetch_detail(candidates)
                        detail_fetched = len(detail_batch.enriched)
                        detail_not_found = detail_batch.not_found
                        detail_failed = detail_batch.failed

                        # Notify admin only for actual errors (not 404s)
                        if detail_failed > 0 and self._broadcaster:
                            failed_ids = detail_batch.failed_ids
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

                # Step 4: Merge enriched detail back in. Objects that got detail
                # become has_detail=true; the rest stay has_detail=false.
                processed_objects = [
                    detail_batch.enriched.get(item["source_id"], item)
                    for item in new_items
                ]

                # Step 5: Batch save ALL new objects to DB and Redis
                if processed_objects:
                    await self._save_objects_batch(processed_objects, region)

                # Step 5.5: Flag fields that should always be present but came
                # out empty (price/section/kind). Rentals always have a price,
                # a district, and a type, so 0 means a parse failure (591 markup
                # change / NUXT null). Objects are still saved; alert admin.
                await self._report_field_anomalies(processed_objects, region)

                # Step 6: Subscription matching (only for objects with detail)
                # Reuse all_subs from pre-filter step (already fetched above)
                uninitialized_subs = await self._redis.get_uninitialized_subscriptions(
                    all_subs
                )
                uninitialized_ids = {sub["id"] for sub in uninitialized_subs}

                # A region with no prior crawl history treats this whole round as a
                # silent baseline: objects are still saved and the seen set seeded
                # (above), subs get marked initialized (below), but nothing is
                # notified. Without this, a cold seen set makes every current
                # listing look "new" and floods already-initialized subs.
                region_baseline = not region_has_history
                if region_baseline and not force_notify:
                    checker_log.info(
                        f"Region {region} has no seen history; this round is a "
                        f"silent baseline (seeding seen set, no notifications)"
                    )

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
                        # Suppress on a cold-region baseline or a not-yet-initialized
                        # sub (first baseline scan) — unless force_notify overrides
                        # it (manual testing).
                        suppress = not force_notify and (
                            region_baseline or sub_id in uninitialized_ids
                        )
                        if suppress:
                            if sub_id not in initialized_subs:
                                initialized_subs.append(sub_id)
                        else:
                            # Notify this match.
                            matches.append((obj, [sub]))
                            checker_log.info(
                                f"Object {obj['source_id']} matches subscription {sub_id}"
                            )

                # Refresh the initialized flag for EVERY current sub each run
                # (mirrors how seen_ids is refreshed). Active subs never wrongly
                # expire -> no periodic swallowed notification; subs with no match
                # this run are still marked after their first scan; deleted subs
                # (absent here) are not refreshed and expire via TTL -> no buildup.
                for sub in all_subs:
                    await self._redis.mark_subscription_initialized(sub["id"])

                if initialized_subs:
                    checker_log.info(
                        f"Initialized {len(initialized_subs)} subscriptions "
                        f"(first scan, no notify): {initialized_subs}"
                    )

                # Step 6: Broadcast notifications
                if matches and self._enable_broadcast and self._broadcaster:
                    # Group matches by object (keyed by source_id)
                    object_subs_map: dict[str, tuple[DBReadyData, list[dict]]] = {}
                    for obj, subs in matches:
                        if obj["source_id"] not in object_subs_map:
                            object_subs_map[obj["source_id"]] = (obj, [])
                        object_subs_map[obj["source_id"]][1].extend(subs)

                    grouped_matches = list(object_subs_map.values())
                    checker_log.info(f"Broadcasting {len(grouped_matches)} matches...")
                    broadcast_result = await self._broadcaster.broadcast(
                        grouped_matches
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
                        broadcast_errors_str = (
                            f"推播失敗: {broadcast_result['failed']}/{broadcast_result['total']}\n"
                            + "\n".join(failure_lines)
                            + truncated
                        )
                        await self._broadcaster.notify_admin(
                            error_type=ErrorType.BROADCAST_ERROR,
                            region=region,
                            details=broadcast_errors_str,
                        )

            # Finish crawler run (including broadcast results)
            await self._postgres.finish_crawler_run(
                run_id=run_id,
                status="success",
                total_fetched=total_fetched,
                new_objects=len(new_ids),
                broadcast_total=broadcast_result.get("total", 0),
                broadcast_success=broadcast_result.get("success", 0),
                broadcast_failed=broadcast_result.get("failed", 0),
                broadcast_errors=broadcast_errors_str if broadcast_result.get("failed", 0) > 0 else None,
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
                total_fetched=total_fetched,
                new_objects=len(all_new_ids),
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
