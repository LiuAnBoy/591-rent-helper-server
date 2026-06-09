"""
Instant Notification Module.

Handles immediate notification when subscription is created or resumed.
"""

from loguru import logger

from src.connections.postgres import get_postgres
from src.connections.redis import get_redis
from src.crawler.contract import DBReadyData
from src.crawler.registry import get_source
from src.jobs.broadcaster import get_broadcaster
from src.matching import filter_redis_objects, match_object_to_subscription
from src.modules.objects import ObjectRepository

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

        # Step 4: Fetch detail for objects without it (via the source)
        if objects_need_detail:
            notify_log.info(
                f"Fetching detail for {len(objects_need_detail)} objects without detail"
            )

            # Own source instance (not the shared one): instant notify can run
            # concurrently with the scheduled checker, and closing a shared
            # fetcher would tear down the browser the other one is still using.
            source = get_source("591", self._redis)
            await source.start()

            try:
                detail_batch = await source.fetch_detail(objects_need_detail)
                updated_objects: list[DBReadyData] = list(
                    detail_batch.enriched.values()
                )

                # Persist all backfilled detail in one transaction (atomic), then
                # refresh the Redis cache so DB and cache do not drift apart.
                if updated_objects:
                    await repo.update_batch_with_detail(updated_objects)
                    await self._redis.update_region_objects(region, updated_objects)
                    notify_log.info(
                        f"Updated {len(updated_objects)} objects with detail"
                    )

                    # Replace filtered objects with their enriched versions, keyed
                    # by (source, source_id) so a future second source sharing a
                    # source_id cannot overwrite the wrong object.
                    enriched_by_key = {
                        (o["source"], o["source_id"]): o for o in updated_objects
                    }
                    filtered_objects = [
                        enriched_by_key.get((obj["source"], obj["source_id"]), obj)
                        for obj in filtered_objects
                    ]
            finally:
                await source.close()

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
                if match_object_to_subscription(obj, sub):
                    matched_objects.append(obj)

            total_matched += len(matched_objects)

            # Send notifications for matched objects
            if matched_objects and service_id:
                for obj in matched_objects:
                    try:
                        result = await self._broadcaster.send_notification(
                            provider=service,
                            provider_id=service_id,
                            obj=obj,
                            subscription_name=sub_name,
                        )
                        if result.get("success"):
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

        # Step 4: Fetch detail for objects without it (via the source)
        if objects_need_detail:
            notify_log.info(
                f"Fetching detail for {len(objects_need_detail)} objects without detail"
            )

            # Own source instance (not the shared one): instant notify can run
            # concurrently with the scheduled checker, and closing a shared
            # fetcher would tear down the browser the other one is still using.
            source = get_source("591", self._redis)
            await source.start()

            try:
                detail_batch = await source.fetch_detail(objects_need_detail)
                updated_objects: list[DBReadyData] = list(
                    detail_batch.enriched.values()
                )

                # Persist all backfilled detail in one transaction (atomic), then
                # refresh the Redis cache so DB and cache do not drift apart.
                if updated_objects:
                    await repo.update_batch_with_detail(updated_objects)
                    await self._redis.update_region_objects(region, updated_objects)
                    notify_log.info(
                        f"Updated {len(updated_objects)} objects with detail"
                    )

                    # Replace filtered objects with their enriched versions, keyed
                    # by (source, source_id) so a future second source sharing a
                    # source_id cannot overwrite the wrong object.
                    enriched_by_key = {
                        (o["source"], o["source_id"]): o for o in updated_objects
                    }
                    filtered_objects = [
                        enriched_by_key.get((obj["source"], obj["source_id"]), obj)
                        for obj in filtered_objects
                    ]
            finally:
                await source.close()

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
            if match_object_to_subscription(obj, subscription):
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
                    result = await self._broadcaster.send_notification(
                        provider=service,
                        provider_id=service_id,
                        obj=obj,
                        subscription_name=sub_name,
                    )
                    if result.get("success"):
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
