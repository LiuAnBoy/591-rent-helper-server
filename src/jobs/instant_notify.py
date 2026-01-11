"""
Instant Notification Module.

Handles immediate notification when subscription is created or resumed.
"""

import re
from typing import Optional

from loguru import logger

from src.connections.postgres import get_postgres
from src.connections.redis import get_redis
from src.crawler.rent591 import Rent591Crawler
from src.jobs.broadcaster import get_broadcaster
from src.modules.objects import ObjectRepository, RentalObject


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
            logger.warning(f"Subscription {sub_id} has no region, skipping instant notify")
            return {"checked": 0, "matched": 0, "notified": 0, "error": "no_region"}

        logger.info(f"Instant notify check for subscription {sub_id}, region {region}")

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

            logger.info(
                f"Instant notify completed for sub {sub_id}: "
                f"checked={result['checked']}, matched={result['matched']}, notified={result['notified']}"
            )

            return result

        except Exception as e:
            logger.error(f"Instant notify failed for subscription {sub_id}: {e}")
            return {"checked": 0, "matched": 0, "notified": 0, "error": str(e)}

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

        logger.info(f"Found {len(objects)} objects in DB for region {region}")

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

        # Initialize crawler
        crawler = Rent591Crawler(headless=True)
        await crawler.start()

        try:
            # Crawl listings
            listings = await crawler.fetch_listings(
                region=region,
                sort="posttime_desc",
                max_items=self.FETCH_COUNT,
            )

            logger.info(f"Crawled {len(listings)} listings for region {region}")

            # Save to DB and filter new ones
            repo = ObjectRepository(self._postgres.pool)
            new_objects = []
            all_ids = set()

            for listing in listings:
                all_ids.add(listing.id)
                is_new = await repo.save(listing)
                if is_new:
                    new_objects.append(listing)

            # Add to seen_ids
            if all_ids:
                await self._redis.add_seen_ids(region, all_ids)

            logger.info(f"Saved {len(new_objects)} new objects to DB")

            # Match and notify (only new objects)
            # Convert RentalObject to dict for matching
            new_objects_dict = [self._rental_object_to_dict(obj) for obj in new_objects]

            return await self._match_and_notify(
                new_objects_dict, subscription, service, service_id, sub_name,
                original_objects=new_objects
            )

        finally:
            await crawler.close()

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

        logger.info(f"Matched {len(matched)} objects for subscription {subscription.get('id')}")

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
                        listing=rental_obj,
                        subscription_name=sub_name,
                    )
                    notified += 1
                except Exception as e:
                    logger.error(f"Failed to notify for object {obj.get('id')}: {e}")

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

        # Layout
        if sub.get("layout"):
            layout_str = obj.get("layout_str", "") or ""
            obj_rooms = self._extract_room_count(layout_str)
            if obj_rooms is not None:
                matched = False
                for required in sub["layout"]:
                    if required == 4 and obj_rooms >= 4:
                        matched = True
                        break
                    elif obj_rooms == required:
                        matched = True
                        break
                if not matched:
                    return False

        # Exclude rooftop addition
        if sub.get("exclude_rooftop"):
            if obj.get("is_rooftop"):
                return False

        return True

    def _extract_room_count(self, layout_str: str) -> Optional[int]:
        """Extract room count from layout string like '2房1廳'."""
        if not layout_str:
            return None
        match = re.search(r"(\d+)房", layout_str)
        return int(match.group(1)) if match else None

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
