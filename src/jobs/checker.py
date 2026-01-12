"""
Listing Checker Module.

Checks for new objects and triggers notifications.
"""

from typing import Optional

from loguru import logger

from src.connections.postgres import PostgresConnection, get_postgres

checker_log = logger.bind(module="Checker")
from src.connections.redis import RedisConnection, get_redis
from src.crawler.detail_fetcher import DetailFetcher, get_detail_fetcher
from src.crawler.list_fetcher import ListFetcher, get_list_fetcher
from src.jobs.broadcaster import Broadcaster, ErrorType, get_broadcaster
from src.modules.objects import ObjectRepository, RentalObject
from src.utils import convert_options_to_codes, convert_other_to_codes
from src.utils.parsers import parse_is_rooftop


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

    # Crawl settings
    INIT_CRAWL_COUNT = 5    # Items to crawl on first run (no notify)
    NORMAL_CRAWL_COUNT = 10  # Items to crawl on normal run

    def __init__(
        self,
        postgres: Optional[PostgresConnection] = None,
        redis: Optional[RedisConnection] = None,
        list_fetcher: Optional[ListFetcher] = None,
        detail_fetcher: Optional[DetailFetcher] = None,
        broadcaster: Optional[Broadcaster] = None,
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
        self._object_repo: Optional[ObjectRepository] = None

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

    def _merge_detail_to_object(
        self,
        obj: RentalObject,
        detail: Optional[dict],
    ) -> RentalObject:
        """
        Merge detail page data into RentalObject.

        Args:
            obj: RentalObject from list page
            detail: Detail data from detail fetcher (can be None)

        Returns:
            Updated RentalObject with merged data
        """
        import re

        if not detail:
            return obj

        # Fields for matching
        obj.gender = detail.get("gender", "all")
        # pet_allowed: None means not specified, default to False
        obj.pet_allowed = detail.get("pet_allowed") if detail.get("pet_allowed") is not None else False
        obj.options = detail.get("options", [])
        obj.shape = detail.get("shape")
        obj.fitment = detail.get("fitment")

        # Fields for notification display
        obj.address = detail.get("address") or obj.address
        obj.tags = detail.get("tags") or obj.tags
        # Convert tags to other codes for matching
        if obj.tags:
            obj.other = convert_other_to_codes(obj.tags)
        obj.layout_str = detail.get("layout_str") or obj.layout_str
        obj.floor_name = detail.get("floor_str") or obj.floor_name
        obj.floor = detail.get("floor") or obj.floor
        obj.total_floor = detail.get("total_floor") or obj.total_floor
        obj.is_rooftop = detail.get("is_rooftop", False) or obj.is_rooftop
        obj.section = detail.get("section") or obj.section
        obj.kind = detail.get("kind") or obj.kind

        # Parse bathroom from layout_str
        layout_str = detail.get("layout_str")
        if layout_str:
            bath_match = re.search(r"(\d+)衛", layout_str)
            if bath_match:
                obj.bathroom = int(bath_match.group(1))

        return obj

    async def _process_new_object(
        self,
        obj: RentalObject,
        detail: Optional[dict],
        region: int,
    ) -> RentalObject:
        """
        Process a new object: merge detail, save to DB, update Redis.

        Args:
            obj: RentalObject from list page
            detail: Detail data from detail fetcher (can be None)
            region: Region code for Redis operations

        Returns:
            Processed RentalObject
        """
        # 1. Merge detail data into object
        obj = self._merge_detail_to_object(obj, detail)

        # 2. Parse is_rooftop from floor_name if not set from detail
        if not obj.is_rooftop:
            obj.is_rooftop = parse_is_rooftop(obj.floor_name)

        # 3. Save to DB (single complete write)
        await self._object_repo.save(obj)

        # 4. Add to Redis seen set
        await self._redis.add_seen_ids(region, {obj.id})

        # 5. Save to Redis object cache
        await self._redis.save_objects([obj.model_dump()])

        checker_log.debug(f"Processed new object {obj.id}")

        return obj

    def _match_object_to_subscription(self, obj: dict, sub: dict) -> bool:
        """
        Check if an object matches a subscription's criteria.
        All matching done in memory.

        Matching logic:
        - For list criteria (kind, section, layout, shape, etc.): object value must be IN the list
        - For range criteria (price, area): object value must be within range
        - For exclude_rooftop: object must not be rooftop addition
        - For gender: object gender must match (or be "all")
        - For pet_required: object must allow pets

        Args:
            obj: Object data from Redis
            sub: Subscription criteria from Redis

        Returns:
            True if object matches all criteria
        """
        # Price range
        if sub.get("price_min") is not None or sub.get("price_max") is not None:
            obj_price = obj.get("price", 0)
            if isinstance(obj_price, str):
                obj_price = int(obj_price.replace(",", "")) if obj_price else 0

            if sub.get("price_min") is not None and obj_price < sub["price_min"]:
                return False
            if sub.get("price_max") is not None and obj_price > sub["price_max"]:
                return False

        # Kind (property type) - obj.kind in sub.kind list
        if sub.get("kind"):
            obj_kind = obj.get("kind")
            if obj_kind is not None and obj_kind not in sub["kind"]:
                return False

        # Section (district) - obj.section in sub.section list
        if sub.get("section"):
            obj_section = obj.get("section")
            if obj_section is not None and obj_section not in sub["section"]:
                return False

        # Shape (建物型態) - obj.shape in sub.shape list
        # 1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅
        if sub.get("shape"):
            obj_shape = obj.get("shape")
            if obj_shape is not None and obj_shape not in sub["shape"]:
                return False

        # Area range
        if sub.get("area_min") is not None or sub.get("area_max") is not None:
            obj_area = obj.get("area", 0) or 0

            if sub.get("area_min") is not None and obj_area < float(sub["area_min"]):
                return False
            if sub.get("area_max") is not None and obj_area > float(sub["area_max"]):
                return False

        # Layout (格局) - extract room count from layout_str like "2房1廳1衛"
        if sub.get("layout"):
            layout_str = obj.get("layout_str", "") or ""
            obj_rooms = self._extract_room_count(layout_str)
            if obj_rooms is not None:
                # sub.layout is like [1, 2, 3, 4] where 4 means 4+
                matched = False
                for required in sub["layout"]:
                    if required == 4:  # 4房以上
                        if obj_rooms >= 4:
                            matched = True
                            break
                    elif obj_rooms == required:
                        matched = True
                        break
                if not matched:
                    return False

        # Bathroom (衛浴) - similar to layout matching
        # sub.bathroom is like ["1", "2", "3", "4_"] where "4_" means 4+
        if sub.get("bathroom"):
            obj_bathroom = obj.get("bathroom")
            if obj_bathroom is not None:
                matched = False
                for required in sub["bathroom"]:
                    if required == "4_" or required == 4:  # 4衛以上
                        if obj_bathroom >= 4:
                            matched = True
                            break
                    elif int(required) == obj_bathroom:
                        matched = True
                        break
                if not matched:
                    return False

        # Floor (樓層) - use floor_min/floor_max for numeric comparison
        floor_min = sub.get("floor_min")
        floor_max = sub.get("floor_max")
        if floor_min is not None or floor_max is not None:
            obj_floor = obj.get("floor")
            if not self._match_floor(obj_floor, floor_min, floor_max):
                return False

        # Fitment (裝潢) - obj.fitment in sub.fitment list
        # 99=新裝潢, 3=中檔裝潢, 4=高檔裝潢
        if sub.get("fitment"):
            obj_fitment = obj.get("fitment")
            if obj_fitment is not None and obj_fitment not in sub["fitment"]:
                return False

        # Exclude rooftop addition (排除頂樓加蓋)
        if sub.get("exclude_rooftop"):
            if obj.get("is_rooftop"):
                return False

        # Gender restriction (性別限制)
        # sub.gender: "boy" = wants male-only or all, "girl" = wants female-only or all
        if sub.get("gender"):
            obj_gender = obj.get("gender", "all")
            if sub["gender"] == "boy" and obj_gender not in ["boy", "all"]:
                return False
            if sub["gender"] == "girl" and obj_gender not in ["girl", "all"]:
                return False

        # Pet required (需要可養寵物)
        if sub.get("pet_required"):
            obj_pet = obj.get("pet_allowed")
            # If pet_allowed is None (not fetched), we can't determine - skip this check
            # If pet_allowed is False, reject
            if obj_pet is False:
                return False

        # Other (features) - compare subscription.other with object.other (both are codes)
        if sub.get("other"):
            obj_other = set(code.lower() for code in (obj.get("other", []) or []))
            sub_other = set(f.lower() for f in sub["other"])
            # All subscription features must be present in object
            if not sub_other <= obj_other:
                return False

        # Options (設備) - check obj.options (detail page) and obj.tags (list page)
        if sub.get("options"):
            # obj.options from detail page already in codes (e.g., ["cold", "washer"])
            obj_options = obj.get("options", []) or []
            # obj.tags from list page in Chinese, convert to codes
            obj_tags = obj.get("tags", []) or []
            tags_as_codes = convert_options_to_codes(obj_tags)
            # Combine all equipment codes
            all_equipment = set(code.lower() for code in obj_options + tags_as_codes)
            sub_options = set(o.lower() for o in sub["options"])
            # All subscription options must be present in object (AND logic)
            if not sub_options <= all_equipment:
                return False

        return True

    def _extract_room_count(self, layout_str: str) -> Optional[int]:
        """
        Extract room count from layout string.

        Args:
            layout_str: String like "2房1廳1衛" or "3房2廳2衛"

        Returns:
            Number of rooms or None if cannot extract
        """
        import re
        match = re.search(r"(\d+)房", layout_str)
        if match:
            return int(match.group(1))
        return None

    def _extract_floor_number(self, floor_name: str) -> Optional[int]:
        """
        Extract floor number from floor name.

        Args:
            floor_name: String like "3F/10F" or "B1/10F" or "頂樓加蓋"

        Returns:
            Floor number or None if cannot extract
        """
        import re
        # Handle basement floors
        if floor_name.upper().startswith("B"):
            return 0  # Treat basement as floor 0

        # Extract first number (current floor)
        match = re.search(r"(\d+)", floor_name)
        if match:
            return int(match.group(1))
        return None

    def _match_floor(
        self,
        obj_floor: Optional[int],
        floor_min: Optional[int],
        floor_max: Optional[int],
    ) -> bool:
        """
        Match object floor against subscription floor range.

        Args:
            obj_floor: Object's floor number (0=rooftop, negative=basement)
            floor_min: Minimum floor (inclusive), None = no limit
            floor_max: Maximum floor (inclusive), None = no limit

        Returns:
            True if floor matches the range
        """
        if obj_floor is None:
            return True  # No floor info, don't filter

        if floor_min is not None and obj_floor < floor_min:
            return False
        if floor_max is not None and obj_floor > floor_max:
            return False
        return True

    async def _match_subscriptions_in_redis(
        self, region: int, obj: dict
    ) -> list[dict]:
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
            if self._match_object_to_subscription(obj, sub):
                matches.append(sub)

        return matches

    async def check(
        self,
        region: int,
        section: Optional[int] = None,
        max_items: Optional[int] = None,
        force_notify: bool = False,
    ) -> dict:
        """
        Check for new objects in a region.

        Optimized Flow:
        1. Crawl list page (BS4 → Playwright fallback)
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
            section: Optional district code
            max_items: Override max items (default: NORMAL_CRAWL_COUNT)
            force_notify: Force notifications even for uninitialized subs (for testing)

        Returns:
            Dict with check results
        """
        await self._ensure_connections()

        if max_items is None:
            max_items = self.NORMAL_CRAWL_COUNT

        checker_log.info(f"Checking region={region} | max_items={max_items}")

        # Start crawler run tracking
        run_id = await self._postgres.start_crawler_run(region, section)

        try:
            # Step 1: Crawl list page (with fallback)
            objects = await self._list_fetcher.fetch_objects(
                region=region,
                section=section,
                sort="posttime_desc",
                max_items=max_items,
            )

            if not objects:
                checker_log.warning("No objects fetched")
                # Notify admin about list fetch failure
                if self._broadcaster:
                    await self._broadcaster.notify_admin(
                        error_type=ErrorType.LIST_FETCH_FAILED,
                        region=region,
                        details="BS4 和 Playwright 都無法抓取列表頁",
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

            checker_log.info(f"Fetched {len(objects)} objects from list")

            # Step 2: Redis filter - find new IDs (don't save to DB yet)
            fetched_ids = {obj.id for obj in objects}
            new_ids = await self._redis.get_new_ids(region, fetched_ids)
            checker_log.info(f"Found {len(new_ids)} new objects")

            # Initialize result variables
            matches = []
            init_matches = []
            initialized_subs = []
            broadcast_result = {"total": 0, "success": 0, "failed": 0}
            detail_fetched = 0
            processed_objects = []

            if new_ids:
                # Get new objects only
                new_objects = [obj for obj in objects if obj.id in new_ids]
                new_object_ids = [obj.id for obj in new_objects]

                # Step 3: Fetch detail pages for new objects (batch with fallback)
                checker_log.info(f"Fetching detail for {len(new_object_ids)} new objects")
                details = await self._detail_fetcher.fetch_details_batch(new_object_ids)
                detail_fetched = len(details)

                # Notify admin if some detail fetches failed
                failed_detail_count = len(new_object_ids) - detail_fetched
                if failed_detail_count > 0 and self._broadcaster:
                    failed_ids = [oid for oid in new_object_ids if oid not in details]
                    await self._broadcaster.notify_admin(
                        error_type=ErrorType.DETAIL_FETCH_FAILED,
                        region=region,
                        details=f"共 {failed_detail_count} 個物件詳情頁抓取失敗\nIDs: {failed_ids[:5]}{'...' if len(failed_ids) > 5 else ''}",
                    )

                # Step 4: Process each new object (merge + save + redis)
                for obj in new_objects:
                    detail = details.get(obj.id)  # May be None if detail fetch failed
                    processed_obj = await self._process_new_object(obj, detail, region)
                    processed_objects.append(processed_obj)

                checker_log.info(
                    f"Processed {len(processed_objects)} objects "
                    f"({detail_fetched} with detail)"
                )

                # Step 5: Subscription matching
                all_subs = await self._redis.get_subscriptions_by_region(region)
                uninitialized_subs = await self._redis.get_uninitialized_subscriptions(all_subs)
                uninitialized_ids = {sub["id"] for sub in uninitialized_subs}

                for obj in processed_objects:
                    obj_data = obj.model_dump()

                    for sub in all_subs:
                        if not self._match_object_to_subscription(obj_data, sub):
                            continue

                        sub_id = sub["id"]
                        if sub_id in uninitialized_ids:
                            # Uninitialized subscription - match but don't notify
                            init_matches.append((obj, sub))
                            if sub_id not in initialized_subs:
                                initialized_subs.append(sub_id)
                        else:
                            # Initialized subscription - match and notify
                            matches.append((obj, [sub]))
                            checker_log.info(f"Object {obj.id} matches subscription {sub_id}")

                # Mark uninitialized subscriptions as initialized
                for sub_id in initialized_subs:
                    await self._redis.mark_subscription_initialized(sub_id)
                    checker_log.info(f"Subscription {sub_id} initialized (first run, no notifications)")

                # Step 6: Broadcast notifications
                if matches and self._enable_broadcast and self._broadcaster:
                    # Group matches by object
                    object_subs_map: dict[int, tuple[RentalObject, list[dict]]] = {}
                    for obj, subs in matches:
                        if obj.id not in object_subs_map:
                            object_subs_map[obj.id] = (obj, [])
                        object_subs_map[obj.id][1].extend(subs)

                    grouped_matches = list(object_subs_map.values())
                    checker_log.info(f"Broadcasting {len(grouped_matches)} matches...")
                    broadcast_result = await self._broadcaster.broadcast(grouped_matches)

                    # Notify admin if some broadcasts failed
                    if broadcast_result.get("failed", 0) > 0:
                        await self._broadcaster.notify_admin(
                            error_type=ErrorType.BROADCAST_ERROR,
                            region=region,
                            details=f"推播失敗: {broadcast_result['failed']}/{broadcast_result['total']}",
                        )

                    # Mark as notified in PostgreSQL
                    for obj, subs in grouped_matches:
                        for sub in subs:
                            try:
                                await self._postgres.mark_notified(sub["id"], obj.id)
                            except Exception as e:
                                # Handle stale subscription (exists in Redis but not in PostgreSQL)
                                if "foreign key constraint" in str(e).lower():
                                    checker_log.warning(
                                        f"Stale subscription {sub['id']} found in Redis "
                                        f"(not in PostgreSQL). Removing from cache..."
                                    )
                                    await self._redis.remove_subscription(
                                        sub.get("region", region), sub["id"]
                                    )
                                else:
                                    raise

            # Finish crawler run
            await self._postgres.finish_crawler_run(
                run_id=run_id,
                status="success",
                total_fetched=len(objects),
                new_objects=len(new_ids),
            )

            result = {
                "region": region,
                "fetched": len(objects),
                "new_count": len(new_ids),
                "detail_fetched": detail_fetched,
                "matches": matches,
                "broadcast": broadcast_result,
                "initialized_subs": initialized_subs,
            }

            checker_log.info(
                f"Check complete: region={region} fetched={result['fetched']} "
                f"new={result['new_count']} detail={detail_fetched} "
                f"matches={len(matches)} initialized={len(initialized_subs)} "
                f"notified={broadcast_result['success']}/{broadcast_result['total']}"
            )

            return result

        except Exception as e:
            checker_log.error(f"Check failed: {e}")

            # Notify admin about the error
            if self._broadcaster:
                # Classify error type
                error_str = str(e).lower()
                if "postgres" in error_str or "database" in error_str or "sql" in error_str:
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

        checker_log.info(f"Found {len(active_regions)} active regions: {active_regions}")

        results = []
        for region in sorted(active_regions):
            try:
                result = await self.check(region=region)
                results.append(result)
            except Exception as e:
                checker_log.error(f"Failed to check region {region}: {e}")
                results.append({
                    "region": region,
                    "error": str(e),
                    "fetched": 0,
                    "new_count": 0,
                    "matches": [],
                    "broadcast": {"total": 0, "success": 0, "failed": 0},
                })

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
