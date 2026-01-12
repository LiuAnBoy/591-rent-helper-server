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
from src.crawler.rent591 import Rent591Crawler
from src.jobs.broadcaster import Broadcaster, get_broadcaster
from src.jobs.parser import parse_is_rooftop
from src.modules.objects import RentalObject
from src.utils import convert_options_to_codes


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
        crawler: Optional[Rent591Crawler] = None,
        detail_crawler: Optional[DetailFetcher] = None,
        broadcaster: Optional[Broadcaster] = None,
        enable_broadcast: bool = True,
        detail_max_workers: int = 3,
    ):
        """
        Initialize Checker.

        Args:
            postgres: PostgreSQL connection (will be created if not provided)
            redis: Redis connection (will be created if not provided)
            crawler: Crawler instance (will be created if not provided)
            detail_crawler: Detail fetcher with bs4 + Playwright fallback
            broadcaster: Broadcaster instance (will be created if not provided)
            enable_broadcast: Whether to send notifications (default True)
            detail_max_workers: Max parallel workers for detail page fetching
        """
        self._postgres = postgres
        self._redis = redis
        self._crawler = crawler
        self._detail_crawler = detail_crawler
        self._broadcaster = broadcaster
        self._enable_broadcast = enable_broadcast
        self._detail_max_workers = detail_max_workers
        self._owns_crawler = False

    async def _ensure_connections(self) -> None:
        """Ensure all connections are established."""
        if self._postgres is None:
            self._postgres = await get_postgres()
        if self._redis is None:
            self._redis = await get_redis()
        if self._crawler is None:
            self._crawler = Rent591Crawler(headless=True)
            self._owns_crawler = True
            await self._crawler.start()
        if self._detail_crawler is None:
            self._detail_crawler = get_detail_fetcher(
                playwright_max_workers=self._detail_max_workers
            )
            await self._detail_crawler.start()
        if self._broadcaster is None and self._enable_broadcast:
            self._broadcaster = get_broadcaster()

    async def close(self) -> None:
        """Close owned resources."""
        if self._owns_crawler and self._crawler:
            await self._crawler.close()
        if self._detail_crawler:
            await self._detail_crawler.close()

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

    async def _fetch_and_update_details(
        self,
        objects: list[RentalObject],
        object_ids: list[int],
    ) -> dict[int, dict]:
        """
        Fetch detail pages and update rental objects.

        Args:
            objects: List of RentalObject to update
            object_ids: IDs to fetch details for

        Returns:
            Dict mapping object_id to detail data
        """
        if not object_ids:
            return {}

        checker_log.info(f"Fetching detail pages for {len(object_ids)} objects...")
        details = await self._detail_crawler.fetch_details_batch(object_ids)

        # Update objects with detail data
        objects_map = {obj.id: obj for obj in objects}
        for obj_id, detail in details.items():
            if obj_id in objects_map:
                obj = objects_map[obj_id]
                obj.gender = detail.get("gender", "all")
                obj.pet_allowed = detail.get("pet_allowed")
                obj.options = detail.get("options", [])
                checker_log.debug(
                    f"Updated {obj_id}: gender={obj.gender}, "
                    f"pet={obj.pet_allowed}, options={len(obj.options)}"
                )

        return details

    def _match_object_to_subscription(self, obj: dict, sub: dict) -> bool:
        """
        Check if an object matches a subscription's criteria.
        All matching done in memory.

        Matching logic:
        - For list criteria (kind, section, layout, etc.): object value must be IN the list
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

        # Floor (樓層) - extract floor from floor_name like "3F/10F" or "B1/10F"
        if sub.get("floor"):
            floor_name = obj.get("floor_name", "") or ""
            obj_floor = self._extract_floor_number(floor_name)
            if obj_floor is not None:
                # sub.floor is like ["1_1", "2_6", "6_12", "13_"]
                matched = self._match_floor(obj_floor, sub["floor"])
                if not matched:
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

        # Features - check if obj.tags contains any subscription features
        if sub.get("features"):
            obj_tags = obj.get("tags", []) or []
            obj_labels = obj.get("labels", []) or []
            all_tags = set(t.lower() for t in obj_tags + obj_labels)

            # Map subscription features to possible tag names
            feature_matched = self._match_features(sub["features"], all_tags, obj)
            if not feature_matched:
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

            option_matched = self._match_options(sub["options"], all_equipment)
            if not option_matched:
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

    def _match_floor(self, obj_floor: int, floor_ranges: list[str]) -> bool:
        """
        Match object floor against subscription floor ranges.

        Args:
            obj_floor: Object's floor number
            floor_ranges: List like ["1_1", "2_6", "6_12", "13_"]

        Returns:
            True if floor matches any range
        """
        for range_str in floor_ranges:
            if range_str == "1_1":  # 1樓
                if obj_floor == 1:
                    return True
            elif range_str == "2_6":  # 2-6層
                if 2 <= obj_floor <= 6:
                    return True
            elif range_str == "6_12":  # 6-12層
                if 6 <= obj_floor <= 12:
                    return True
            elif range_str == "13_":  # 12樓以上
                if obj_floor >= 13:
                    return True
        return False

    def _match_features(
        self, features: list[str], obj_tags: set[str], obj: dict
    ) -> bool:
        """
        Match subscription features against object tags.

        Args:
            features: Subscription features like ["near_subway", "pet", "lift"]
            obj_tags: Object's tags (lowercased)
            obj: Full object data for additional checks

        Returns:
            True if at least one feature matches (OR logic)
        """
        # Feature to tag mapping
        feature_map = {
            "near_subway": ["近捷運", "捷運", "mrt"],
            "pet": ["可養寵", "寵物", "pet"],
            "cook": ["可開伙", "開伙", "廚房"],
            "lift": ["有電梯", "電梯"],
            "balcony_1": ["有陽台", "陽台"],
            "cartplace": ["車位", "停車"],
            "newpost": ["新上架"],
            "lease": ["短租"],
        }

        for feature in features:
            feature_lower = feature.lower()

            # Check direct tag match
            if feature_lower in obj_tags:
                return True

            # Check mapped tags
            if feature_lower in feature_map:
                for tag_variant in feature_map[feature_lower]:
                    if tag_variant in obj_tags or any(tag_variant in t for t in obj_tags):
                        return True

            # Check surrounding for near_subway
            if feature_lower == "near_subway":
                surrounding = obj.get("surrounding", {}) or {}
                if surrounding.get("subway"):
                    return True

        return False

    def _match_options(self, sub_options: list[str], obj_options: set[str]) -> bool:
        """
        Match subscription equipment options against object options.

        Both subscription and object store options as codes (e.g., "cold", "washer").

        Args:
            sub_options: Subscription options like ["cold", "washer", "bed"]
            obj_options: Object's options as codes (lowercased)

        Returns:
            True if at least one option matches (OR logic)
        """
        for option in sub_options:
            if option.lower() in obj_options:
                return True
        return False

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

        Flow:
        1. Crawl list page → get basic object data
        2. Parse is_rooftop from floor_name
        3. Save to PostgreSQL + Redis
        4. Find new IDs
        5. Fetch detail pages for ALL new objects
        6. Full matching
        7. Push notifications

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
            # Step 1: Crawl latest objects from list page
            objects = await self._crawler.fetch_listings(
                region=region,
                section=section,
                sort="posttime_desc",
                max_items=max_items,
            )

            if not objects:
                checker_log.warning("No objects fetched")
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

            checker_log.info(f"Fetched {len(objects)} objects")

            # Step 2: Parse is_rooftop and save to PostgreSQL + Redis
            new_count = 0
            fetched_ids = set()

            for obj in objects:
                fetched_ids.add(obj.id)

                # Parse is_rooftop from floor_name (can be done from list page)
                obj.is_rooftop = parse_is_rooftop(obj.floor_name)

                # Save to PostgreSQL
                is_new = await self._postgres.save_object(obj)
                if is_new:
                    new_count += 1

            # Step 3: Find new IDs (not in seen set)
            new_ids = await self._redis.get_new_ids(region, fetched_ids)
            checker_log.info(f"Found {len(new_ids)} new objects")

            # Step 4: Add to seen set
            await self._redis.add_seen_ids(region, fetched_ids)

            # Step 5: Match subscriptions and notify
            matches = []
            init_matches = []
            initialized_subs = []
            broadcast_result = {"total": 0, "success": 0, "failed": 0}
            detail_fetched = 0

            if new_ids:
                # Get all subscriptions for this region
                all_subs = await self._redis.get_subscriptions_by_region(region)

                # Separate initialized and uninitialized subscriptions
                uninitialized_subs = await self._redis.get_uninitialized_subscriptions(all_subs)
                uninitialized_ids = {sub["id"] for sub in uninitialized_subs}

                # Get new objects only
                new_objects = [obj for obj in objects if obj.id in new_ids]

                # Fetch detail pages for ALL new objects
                if new_objects:
                    new_object_ids = [obj.id for obj in new_objects]
                    checker_log.info(f"Fetching detail for {len(new_object_ids)} new objects")
                    await self._fetch_and_update_details(new_objects, new_object_ids)
                    detail_fetched = len(new_object_ids)

                # Full matching with updated data
                for obj in new_objects:
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

                    # Mark as notified in PostgreSQL
                    for obj, subs in grouped_matches:
                        for sub in subs:
                            await self._postgres.mark_notified(sub["id"], obj.id)

            # Step 7: Save updated objects to Redis (with detail data)
            objects_to_cache = [obj.model_dump() for obj in objects]
            await self._redis.save_objects(objects_to_cache)

            # Finish crawler run
            await self._postgres.finish_crawler_run(
                run_id=run_id,
                status="success",
                total_fetched=len(objects),
                new_objects=new_count,
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
