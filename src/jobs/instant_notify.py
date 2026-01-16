"""
Instant Notification Module.

Handles immediate notification when subscription is created or resumed.
"""

from loguru import logger

from src.connections.postgres import get_postgres
from src.connections.redis import get_redis
from src.crawler.detail_fetcher import get_detail_fetcher
from src.crawler.types import CombinedRawData
from src.jobs.broadcaster import get_broadcaster
from src.matching import filter_redis_objects
from src.modules.objects import ObjectRepository
from src.utils import DBReadyData, transform_to_db_ready

notify_log = logger.bind(module="Notify")


class InstantNotifier:
    """
    Handles instant notification for new/resumed subscriptions.
    """

    FETCH_COUNT = 10  # Number of items to fetch/check

    def __init__(self):
        self._postgres = None
        self._redis = None
        self._broadcaster = None

    async def _ensure_connections(self):
        """Ensure all connections are established."""
        if self._postgres is None:
            self._postgres = await get_postgres()
        if self._redis is None:
            self._redis = await get_redis()
        if self._broadcaster is None:
            self._broadcaster = get_broadcaster()

    async def notify_for_subscription(
        self,
        user_id: int,
        subscription: dict,
        service: str = "telegram",
        service_id: str | None = None,
    ) -> dict:
        """
        Check and notify user for a subscription immediately.

        Args:
            user_id: User ID
            subscription: Subscription dict with filters
            service: Notification service (telegram, line, etc.)
            service_id: Service-specific user ID (chat_id, etc.)

        Returns:
            Result dict with stats
        """
        await self._ensure_connections()

        region = subscription.get("region")
        sub_id = subscription.get("id")
        sub_name = subscription.get("name", f"訂閱 {sub_id}")

        if not region:
            notify_log.warning(
                f"Subscription {sub_id} has no region, skipping instant notify"
            )
            return {"checked": 0, "matched": 0, "notified": 0, "error": "no_region"}

        notify_log.info(
            f"Instant notify check for subscription {sub_id}, region {region}"
        )

        try:
            # Use Redis cache with fallback to DB
            # If Redis and DB are both empty, will crawl
            result = await self._notify_from_redis(
                subscription, service, service_id, sub_name
            )

            # Mark subscription as initialized
            await self._redis.mark_subscription_initialized(sub_id)

            notify_log.info(
                f"Instant notify completed for sub {sub_id}: "
                f"checked={result['checked']}, matched={result['matched']}, notified={result['notified']}"
            )

            return result

        except Exception as e:
            notify_log.error(f"Instant notify failed for subscription {sub_id}: {e}")
            return {"checked": 0, "matched": 0, "notified": 0, "error": str(e)}

    async def notify_for_subscriptions_batch(
        self,
        user_id: int,
        subscriptions: list[dict],
        service: str = "telegram",
        service_id: str | None = None,
    ) -> dict:
        """
        Notify for multiple subscriptions efficiently.

        Groups by region and fetches data once per region.

        Args:
            user_id: User ID
            subscriptions: List of subscription dicts
            service: Notification service
            service_id: Service user ID

        Returns:
            Aggregated result dict
        """
        await self._ensure_connections()

        if not subscriptions:
            return {"checked": 0, "matched": 0, "notified": 0}

        # Group subscriptions by region
        by_region: dict[int, list[dict]] = {}
        for sub in subscriptions:
            region = sub.get("region")
            if region:
                if region not in by_region:
                    by_region[region] = []
                by_region[region].append(sub)

        notify_log.info(
            f"Batch notify for user {user_id}: "
            f"{len(subscriptions)} subscriptions across {len(by_region)} regions"
        )

        total_checked = 0
        total_matched = 0
        total_notified = 0

        # Process each region once
        for region, region_subs in by_region.items():
            try:
                result = await self._notify_region_batch(
                    region, region_subs, service, service_id
                )
                total_checked += result["checked"]
                total_matched += result["matched"]
                total_notified += result["notified"]

                # Mark all subscriptions as initialized
                for sub in region_subs:
                    await self._redis.mark_subscription_initialized(sub["id"])

            except Exception as e:
                notify_log.error(f"Batch notify failed for region {region}: {e}")

        notify_log.info(
            f"Batch notify completed for user {user_id}: "
            f"checked={total_checked}, matched={total_matched}, notified={total_notified}"
        )

        return {
            "checked": total_checked,
            "matched": total_matched,
            "notified": total_notified,
        }

    async def _notify_region_batch(
        self,
        region: int,
        subscriptions: list[dict],
        service: str,
        service_id: str,
    ) -> dict:
        """
        Notify for multiple subscriptions in the same region.

        Uses Redis cache with fallback to DB. Fetches objects once
        and matches against all subscriptions.

        Flow:
        1. Get objects from Redis region cache (fallback to DB)
        2. Pre-filter objects for all subscriptions
        3. Find objects with has_detail=false
        4. Fetch detail for those objects
        5. Update DB and Redis
        6. Match only has_detail=true objects against each subscription
        7. Send notifications

        Args:
            region: Region code
            subscriptions: List of subscriptions for this region
            service: Notification service
            service_id: Service user ID

        Returns:
            Result dict
        """
        repo = ObjectRepository(self._postgres.pool)

        # Step 1: Get objects from Redis (fallback to DB)
        objects = await self._redis.get_region_objects(region)

        if objects is None:
            # Redis miss - load from DB and populate Redis
            notify_log.info(f"Redis cache miss for region {region}, loading from DB")
            db_objects = await repo.get_latest_by_region(region, self.FETCH_COUNT)
            objects = db_objects

            if objects:
                # Populate Redis cache
                await self._redis.set_region_objects(region, objects)
                notify_log.info(
                    f"Loaded {len(objects)} objects from DB for region {region}"
                )
            else:
                notify_log.info(f"No objects in DB for region {region}")
                return {"checked": 0, "matched": 0, "notified": 0}
        else:
            notify_log.info(
                f"Found {len(objects)} objects in Redis for region {region}"
            )

        if not objects:
            return {"checked": 0, "matched": 0, "notified": 0}

        # Step 2: Pre-filter for all subscriptions (union of conditions)
        filtered_objects, skipped = filter_redis_objects(objects, subscriptions)
        notify_log.info(
            f"Pre-filter: {len(objects)} → {len(filtered_objects)} "
            f"(skipped {skipped} by pre-filter)"
        )

        if not filtered_objects:
            return {"checked": len(objects), "matched": 0, "notified": 0}

        # Step 3: Find objects that need detail
        objects_need_detail = [
            obj for obj in filtered_objects if not obj.get("has_detail", False)
        ]

        # Step 4: Fetch detail for objects without it
        if objects_need_detail:
            notify_log.info(
                f"Fetching detail for {len(objects_need_detail)} objects without detail"
            )

            detail_fetcher = get_detail_fetcher()
            await detail_fetcher.start()

            try:
                ids_to_fetch = [obj["id"] for obj in objects_need_detail]
                details, _, _ = await detail_fetcher.fetch_details_batch_raw(
                    ids_to_fetch
                )

                # Update objects with fetched details
                updated_objects: list[dict] = []
                for obj in objects_need_detail:
                    obj_id = obj["id"]
                    detail_data = details.get(obj_id)

                    if detail_data:
                        # Create combined data and transform
                        combined: CombinedRawData = {
                            "id": str(obj_id),
                            "url": obj.get("url", ""),
                            "title": obj.get("title", ""),
                            "price_raw": str(obj.get("price", "")),
                            "tags": obj.get("tags", []),
                            "kind_name": obj.get("kind_name", ""),
                            "address_raw": obj.get("address", ""),
                            "surrounding_type": detail_data.get("surrounding_type"),
                            "surrounding_raw": detail_data.get("surrounding_raw"),
                            "region": str(region),
                            "section": str(obj.get("section", "")),
                            "kind": str(obj.get("kind", "")),
                            "floor_raw": detail_data.get("floor_raw", ""),
                            "layout_raw": detail_data.get("layout_raw", ""),
                            "area_raw": detail_data.get("area_raw", ""),
                            "gender_raw": detail_data.get("gender_raw"),
                            "shape_raw": detail_data.get("shape_raw"),
                            "fitment_raw": detail_data.get("fitment_raw"),
                            "options": detail_data.get("options", []),
                            "has_detail": True,
                        }

                        db_ready = transform_to_db_ready(combined)
                        updated_objects.append(db_ready)

                        # Update DB
                        await repo.update_with_detail(obj_id, db_ready)

                # Update Redis cache with new data
                if updated_objects:
                    await self._redis.update_region_objects(region, updated_objects)
                    notify_log.info(
                        f"Updated {len(updated_objects)} objects with detail"
                    )

                    # Update filtered_objects with new data
                    updated_by_id = {obj["id"]: obj for obj in updated_objects}
                    filtered_objects = [
                        updated_by_id.get(obj["id"], obj) for obj in filtered_objects
                    ]

            finally:
                await detail_fetcher.close()

        # Step 5: Match only objects with has_detail=true
        objects_with_detail = [
            obj for obj in filtered_objects if obj.get("has_detail", False)
        ]

        notify_log.info(
            f"Matching {len(objects_with_detail)} objects with detail "
            f"(out of {len(filtered_objects)} filtered)"
        )

        # Step 6: Match and notify for each subscription
        total_matched = 0
        total_notified = 0

        for sub in subscriptions:
            sub_name = sub.get("name", f"訂閱 {sub.get('id')}")
            matched_objects = []

            for obj in objects_with_detail:
                if self._matches_subscription(obj, sub):
                    matched_objects.append(obj)

            total_matched += len(matched_objects)

            # Send notifications for matched objects
            if matched_objects and service_id:
                for obj in matched_objects:
                    try:
                        await self._broadcaster.send_notification(
                            service=service,
                            service_id=service_id,
                            obj=obj,
                            subscription_name=sub_name,
                        )
                        total_notified += 1
                    except Exception as e:
                        notify_log.error(
                            f"Failed to notify for object {obj.get('id')}: {e}"
                        )

            notify_log.debug(
                f"Subscription {sub.get('id')}: matched {len(matched_objects)} objects"
            )

        return {
            "checked": len(objects),
            "matched": total_matched,
            "notified": total_notified,
        }

    async def _notify_from_redis(
        self,
        subscription: dict,
        service: str,
        service_id: str,
        sub_name: str,
    ) -> dict:
        """
        Notify using Redis cache with fallback to DB.

        Flow:
        1. Get objects from Redis region cache
        2. If Redis miss, load from DB and populate Redis
        3. Pre-filter objects by price/area
        4. Find objects with has_detail=false
        5. Fetch detail for those objects
        6. Update DB and Redis
        7. Match only has_detail=true objects against subscription
        8. Send notifications
        """
        region = subscription["region"]
        repo = ObjectRepository(self._postgres.pool)

        # Step 1: Try Redis first
        objects = await self._redis.get_region_objects(region)

        if objects is None:
            # Redis miss - load from DB and populate Redis
            notify_log.info(f"Redis cache miss for region {region}, loading from DB")
            db_objects = await repo.get_latest_by_region(region, self.FETCH_COUNT)
            objects = db_objects

            if objects:
                # Populate Redis cache
                await self._redis.set_region_objects(region, objects)
            else:
                notify_log.info(f"No objects in DB for region {region}")
                return {"checked": 0, "matched": 0, "notified": 0}
        else:
            notify_log.info(
                f"Found {len(objects)} objects in Redis for region {region}"
            )

        if not objects:
            return {"checked": 0, "matched": 0, "notified": 0}

        # Step 2: Pre-filter
        filtered_objects, skipped = filter_redis_objects(objects, [subscription])
        notify_log.info(
            f"Pre-filter: {len(objects)} → {len(filtered_objects)} "
            f"(skipped {skipped} by pre-filter)"
        )

        if not filtered_objects:
            return {"checked": len(objects), "matched": 0, "notified": 0}

        # Step 3: Find objects that need detail
        objects_need_detail = [
            obj for obj in filtered_objects if not obj.get("has_detail", False)
        ]

        # Step 4: Fetch detail for objects without it
        if objects_need_detail:
            notify_log.info(
                f"Fetching detail for {len(objects_need_detail)} objects without detail"
            )

            detail_fetcher = get_detail_fetcher()
            await detail_fetcher.start()

            try:
                ids_to_fetch = [obj["id"] for obj in objects_need_detail]
                details, _, _ = await detail_fetcher.fetch_details_batch_raw(
                    ids_to_fetch
                )

                # Update objects with fetched details
                updated_objects: list[dict] = []
                for obj in objects_need_detail:
                    obj_id = obj["id"]
                    detail_data = details.get(obj_id)

                    if detail_data:
                        # Create combined data and transform
                        combined: CombinedRawData = {
                            "id": str(obj_id),
                            "url": obj.get("url", ""),
                            "title": obj.get("title", ""),
                            "price_raw": str(obj.get("price", "")),
                            "tags": obj.get("tags", []),
                            "kind_name": obj.get("kind_name", ""),
                            "address_raw": obj.get("address", ""),
                            "surrounding_type": detail_data.get("surrounding_type"),
                            "surrounding_raw": detail_data.get("surrounding_raw"),
                            "region": str(region),
                            "section": str(obj.get("section", "")),
                            "kind": str(obj.get("kind", "")),
                            "floor_raw": detail_data.get("floor_raw", ""),
                            "layout_raw": detail_data.get("layout_raw", ""),
                            "area_raw": detail_data.get("area_raw", ""),
                            "gender_raw": detail_data.get("gender_raw"),
                            "shape_raw": detail_data.get("shape_raw"),
                            "fitment_raw": detail_data.get("fitment_raw"),
                            "options": detail_data.get("options", []),
                            "has_detail": True,
                        }

                        db_ready = transform_to_db_ready(combined)
                        updated_objects.append(db_ready)

                        # Update DB
                        await repo.update_with_detail(obj_id, db_ready)

                # Update Redis cache with new data
                if updated_objects:
                    await self._redis.update_region_objects(region, updated_objects)
                    notify_log.info(
                        f"Updated {len(updated_objects)} objects with detail"
                    )

                    # Update filtered_objects with new data
                    updated_by_id = {obj["id"]: obj for obj in updated_objects}
                    filtered_objects = [
                        updated_by_id.get(obj["id"], obj) for obj in filtered_objects
                    ]

            finally:
                await detail_fetcher.close()

        # Step 5: Match only objects with has_detail=true
        objects_with_detail = [
            obj for obj in filtered_objects if obj.get("has_detail", False)
        ]

        notify_log.info(
            f"Matching {len(objects_with_detail)} objects with detail "
            f"(out of {len(filtered_objects)} filtered)"
        )

        # Step 6: Match and notify
        return await self._match_and_notify(
            objects_with_detail, subscription, service, service_id, sub_name
        )

    async def _match_and_notify(
        self,
        objects: list[DBReadyData],
        subscription: dict,
        service: str,
        service_id: str,
        sub_name: str,
    ) -> dict:
        """
        Match objects against subscription and notify.

        Args:
            objects: List of DBReadyData dicts
            subscription: Subscription dict
            service: Notification service
            service_id: Service user ID
            sub_name: Subscription name for display

        Returns:
            Result dict with checked/matched/notified counts
        """
        matched = []

        for obj in objects:
            if self._matches_subscription(obj, subscription):
                matched.append(obj)

        notify_log.info(
            f"Matched {len(matched)} objects for subscription {subscription.get('id')}"
        )

        # Send notifications
        notified = 0
        if matched and service_id:
            for obj in matched:
                try:
                    # Send DBReadyData directly (broadcaster now supports dict)
                    await self._broadcaster.send_notification(
                        service=service,
                        service_id=service_id,
                        obj=obj,
                        subscription_name=sub_name,
                    )
                    notified += 1
                except Exception as e:
                    notify_log.error(
                        f"Failed to notify for object {obj.get('id')}: {e}"
                    )

        return {
            "checked": len(objects),
            "matched": len(matched),
            "notified": notified,
        }

    def _matches_subscription(self, obj: dict, sub: dict) -> bool:
        """
        Check if object matches subscription filters.
        Based on Checker._basic_match_object_to_subscription logic.

        Args:
            obj: Object dict
            sub: Subscription dict with filters

        Returns:
            True if matches all filters
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

        # Kind (property type)
        if sub.get("kind"):
            obj_kind = obj.get("kind")
            if obj_kind is not None and obj_kind not in sub["kind"]:
                return False

        # Section (district)
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

        # Layout - obj.layout in sub.layout list (4 means 4+)
        if sub.get("layout"):
            obj_layout = obj.get("layout")
            if obj_layout is not None:
                matched = False
                for required in sub["layout"]:
                    if required == 4 and obj_layout >= 4:
                        matched = True
                        break
                    elif obj_layout == required:
                        matched = True
                        break
                if not matched:
                    return False

        # Floor range
        floor_min = sub.get("floor_min")
        floor_max = sub.get("floor_max")
        if floor_min is not None or floor_max is not None:
            obj_floor = obj.get("floor")
            if obj_floor is not None:
                if floor_min is not None and obj_floor < floor_min:
                    return False
                if floor_max is not None and obj_floor > floor_max:
                    return False

        # Exclude rooftop addition
        if sub.get("exclude_rooftop"):
            if obj.get("is_rooftop"):
                return False

        return True


# Singleton instance
_notifier: InstantNotifier | None = None


def get_instant_notifier() -> InstantNotifier:
    """Get InstantNotifier singleton."""
    global _notifier
    if _notifier is None:
        _notifier = InstantNotifier()
    return _notifier


async def notify_for_new_subscription(
    user_id: int,
    subscription: dict,
    service: str = "telegram",
    service_id: str | None = None,
) -> dict:
    """
    Convenience function to notify for a new subscription.

    Args:
        user_id: User ID
        subscription: Subscription dict
        service: Notification service
        service_id: Service user ID

    Returns:
        Result dict
    """
    notifier = get_instant_notifier()
    return await notifier.notify_for_subscription(
        user_id, subscription, service, service_id
    )


async def notify_for_subscriptions_batch(
    user_id: int,
    subscriptions: list[dict],
    service: str = "telegram",
    service_id: str | None = None,
) -> dict:
    """
    Notify for multiple subscriptions efficiently.

    Groups subscriptions by region and fetches data once per region.

    Args:
        user_id: User ID
        subscriptions: List of subscription dicts
        service: Notification service
        service_id: Service user ID

    Returns:
        Result dict with aggregated stats
    """
    notifier = get_instant_notifier()
    return await notifier.notify_for_subscriptions_batch(
        user_id, subscriptions, service, service_id
    )
