"""
Instant Notification Module.

Handles immediate notification when subscription is created or resumed.
"""

import re
from typing import Optional

from loguru import logger

from src.connections.postgres import get_postgres
from src.connections.redis import get_redis
from src.crawler.list_fetcher import ListFetcher, get_list_fetcher
from src.jobs.broadcaster import get_broadcaster
from src.modules.objects import ObjectRepository, RentalObject

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
        service_id: str = None,
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
            notify_log.warning(f"Subscription {sub_id} has no region, skipping instant notify")
            return {"checked": 0, "matched": 0, "notified": 0, "error": "no_region"}

        notify_log.info(f"Instant notify check for subscription {sub_id}, region {region}")

        try:
            # Check if region has existing data
            has_data = await self._redis.has_seen_ids(region)

            if has_data:
                # Region already has data - fetch from DB
                result = await self._notify_from_db(
                    subscription, service, service_id, sub_name
                )
            else:
                # Region has no data - need to crawl
                result = await self._notify_from_crawl(
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
        service_id: str = None,
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

        Fetches objects once and matches against all subscriptions.

        Args:
            region: Region code
            subscriptions: List of subscriptions for this region
            service: Notification service
            service_id: Service user ID

        Returns:
            Result dict
        """
        # Check if region has existing data
        has_data = await self._redis.has_seen_ids(region)

        if has_data:
            # Region has data - fetch from DB
            repo = ObjectRepository(self._postgres.pool)
            objects = await repo.get_latest_by_region(region, self.FETCH_COUNT)
            notify_log.info(f"Found {len(objects)} objects in DB for region {region}")
        else:
            # Region has no data - need to crawl
            fetcher = get_list_fetcher()
            await fetcher.start()

            try:
                fetched_objects = await fetcher.fetch_objects(
                    region=region,
                    sort="posttime_desc",
                    max_items=self.FETCH_COUNT,
                )
                notify_log.info(f"Crawled {len(fetched_objects)} objects for region {region}")

                # Save to DB
                repo = ObjectRepository(self._postgres.pool)
                all_ids = set()

                for fetched_obj in fetched_objects:
                    all_ids.add(fetched_obj.id)
                    await repo.save(fetched_obj)

                # Add to seen_ids
                if all_ids:
                    await self._redis.add_seen_ids(region, all_ids)

                # Convert to dict for matching
                objects = [self._rental_object_to_dict(o) for o in fetched_objects]

            finally:
                await fetcher.close()

        # Match objects against ALL subscriptions for this region
        total_matched = 0
        total_notified = 0

        for sub in subscriptions:
            sub_name = sub.get("name", f"訂閱 {sub.get('id')}")
            matched_objects = []

            for obj in objects:
                if self._matches_subscription(obj, sub):
                    matched_objects.append(obj)

            total_matched += len(matched_objects)

            # Send notifications for matched objects
            if matched_objects and service_id:
                for obj in matched_objects:
                    try:
                        rental_obj = self._dict_to_rental_object(obj)
                        await self._broadcaster.send_notification(
                            service=service,
                            service_id=service_id,
                            obj=rental_obj,
                            subscription_name=sub_name,
                        )
                        total_notified += 1
                    except Exception as e:
                        notify_log.error(f"Failed to notify for object {obj.get('id')}: {e}")

            notify_log.debug(
                f"Subscription {sub.get('id')}: matched {len(matched_objects)} objects"
            )

        return {
            "checked": len(objects),
            "matched": total_matched,
            "notified": total_notified,
        }

    async def _notify_from_db(
        self,
        subscription: dict,
        service: str,
        service_id: str,
        sub_name: str,
    ) -> dict:
        """
        Notify using existing data from database.
        """
        region = subscription["region"]

        # Get latest objects from DB
        repo = ObjectRepository(self._postgres.pool)
        objects = await repo.get_latest_by_region(region, self.FETCH_COUNT)

        notify_log.info(f"Found {len(objects)} objects in DB for region {region}")

        # Match and notify
        return await self._match_and_notify(
            objects, subscription, service, service_id, sub_name
        )

    async def _notify_from_crawl(
        self,
        subscription: dict,
        service: str,
        service_id: str,
        sub_name: str,
    ) -> dict:
        """
        Crawl new data and notify.
        """
        region = subscription["region"]

        # Initialize fetcher
        fetcher = get_list_fetcher()
        await fetcher.start()

        try:
            # Crawl objects
            fetched_objects = await fetcher.fetch_objects(
                region=region,
                sort="posttime_desc",
                max_items=self.FETCH_COUNT,
            )

            notify_log.info(f"Crawled {len(fetched_objects)} objects for region {region}")

            # Save to DB and filter new ones
            repo = ObjectRepository(self._postgres.pool)
            new_objects = []
            all_ids = set()

            for fetched_obj in fetched_objects:
                all_ids.add(fetched_obj.id)
                is_new = await repo.save(fetched_obj)
                if is_new:
                    new_objects.append(fetched_obj)

            # Add to seen_ids
            if all_ids:
                await self._redis.add_seen_ids(region, all_ids)

            notify_log.info(f"Saved {len(new_objects)} new objects to DB")

            # Match and notify (only new objects)
            # Convert RentalObject to dict for matching
            new_objects_dict = [self._rental_object_to_dict(obj) for obj in new_objects]

            return await self._match_and_notify(
                new_objects_dict, subscription, service, service_id, sub_name,
                original_objects=new_objects
            )

        finally:
            await fetcher.close()

    async def _match_and_notify(
        self,
        objects: list,
        subscription: dict,
        service: str,
        service_id: str,
        sub_name: str,
        original_objects: list = None,
    ) -> dict:
        """
        Match objects against subscription and notify.
        """
        matched = []
        matched_indices = []

        for idx, obj in enumerate(objects):
            if self._matches_subscription(obj, subscription):
                matched.append(obj)
                matched_indices.append(idx)

        notify_log.info(f"Matched {len(matched)} objects for subscription {subscription.get('id')}")

        # Send notifications
        notified = 0
        if matched and service_id:
            for idx, obj in zip(matched_indices, matched):
                try:
                    # Get RentalObject for notification
                    if original_objects and idx < len(original_objects):
                        rental_obj = original_objects[idx]
                    else:
                        rental_obj = self._dict_to_rental_object(obj)

                    await self._broadcaster.send_notification(
                        service=service,
                        service_id=service_id,
                        obj=rental_obj,
                        subscription_name=sub_name,
                    )
                    notified += 1
                except Exception as e:
                    notify_log.error(f"Failed to notify for object {obj.get('id')}: {e}")

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

    def _rental_object_to_dict(self, obj: RentalObject) -> dict:
        """Convert RentalObject to dict for matching."""
        return {
            "id": obj.id,
            "price": obj.price,
            "kind": obj.kind,
            "area": obj.area,
            "layout_str": obj.layout_str,
            "section": obj.section,
            "is_rooftop": getattr(obj, "is_rooftop", False),
        }

    def _dict_to_rental_object(self, obj: dict) -> RentalObject:
        """Convert dict back to RentalObject for notification."""
        return RentalObject(
            id=obj.get("id", 0),
            title=obj.get("title", ""),
            url=obj.get("url", ""),
            region=obj.get("region"),
            section=obj.get("section"),
            address=obj.get("address"),
            kind=obj.get("kind"),
            kind_name=obj.get("kind_name"),
            price=str(obj.get("price", "")) if obj.get("price") else None,
            price_unit=obj.get("price_unit"),
            price_per=obj.get("price_per"),
            area=obj.get("area"),
            layout_str=obj.get("layout_str"),
            floor_name=obj.get("floor_str"),
            tags=obj.get("tags", []),
            surrounding=None,
        )


# Singleton instance
_notifier: Optional[InstantNotifier] = None


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
    service_id: str = None,
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
    service_id: str = None,
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
