"""
Redis Connection Module.

Manages Redis connection for caching objects, subscriptions, and seen IDs.
"""

import json
from typing import Optional

import redis.asyncio as redis
from loguru import logger

from config.settings import get_settings

redis_log = logger.bind(module="Redis")


class RedisConnection:
    """Redis connection manager."""

    # TTL settings (seconds)
    TTL_SEEN_IDS = 60 * 60 * 24 * 7      # 7 days
    TTL_OBJECT = 60 * 60 * 24 * 3        # 3 days
    TTL_INITIALIZED = 60 * 60 * 24 * 7   # 7 days

    def __init__(self):
        """Initialize Redis connection."""
        self.settings = get_settings().redis
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        redis_log.info(f"Connecting to Redis at {self.settings.host}:{self.settings.port}")
        self._client = redis.Redis(
            host=self.settings.host,
            port=self.settings.port,
            db=self.settings.db,
            password=self.settings.password or None,
            decode_responses=True,
        )
        # Test connection
        await self._client.ping()
        redis_log.info("Redis connected successfully")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            redis_log.info("Redis connection closed")

    @property
    def client(self) -> redis.Redis:
        """Get Redis client."""
        if not self._client:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    # ========== Key Generators ==========

    def _seen_key(self, region: int) -> str:
        """Generate key for seen objects set."""
        return f"region:{region}:seen_ids"

    def _subscriptions_key(self, region: int) -> str:
        """Generate key for region subscriptions hash."""
        return f"region:{region}:subscriptions"

    def _object_key(self, object_id: int) -> str:
        """Generate key for object data."""
        return f"object:{object_id}"

    # ========== Seen IDs Operations ==========

    async def get_seen_ids(self, region: int) -> set[int]:
        """
        Get all seen object IDs for a region.

        Args:
            region: Region code (1=Taipei, 3=New Taipei)

        Returns:
            Set of object IDs that have been seen
        """
        key = self._seen_key(region)
        ids = await self.client.smembers(key)
        return {int(id_) for id_ in ids}

    async def has_seen_ids(self, region: int) -> bool:
        """
        Check if a region has any seen IDs.

        Args:
            region: Region code

        Returns:
            True if region has seen_ids, False otherwise
        """
        key = self._seen_key(region)
        count = await self.client.scard(key)
        return count > 0

    async def add_seen_ids(self, region: int, ids: set[int]) -> None:
        """
        Add object IDs to the seen set with TTL.

        Args:
            region: Region code
            ids: Set of object IDs to add
        """
        if not ids:
            return
        key = self._seen_key(region)
        await self.client.sadd(key, *[str(id_) for id_ in ids])
        await self.client.expire(key, self.TTL_SEEN_IDS)
        redis_log.debug(f"Added {len(ids)} IDs to {key}")

    async def get_new_ids(self, region: int, ids: set[int]) -> set[int]:
        """
        Find which IDs are new (not in seen set).

        Args:
            region: Region code
            ids: Set of object IDs to check

        Returns:
            Set of IDs that are NOT in the seen set
        """
        if not ids:
            return set()
        seen_ids = await self.get_seen_ids(region)
        return ids - seen_ids

    async def is_seen(self, region: int, object_id: int) -> bool:
        """Check if an object ID has been seen."""
        key = self._seen_key(region)
        return await self.client.sismember(key, str(object_id))

    async def get_seen_count(self, region: int) -> int:
        """Get count of seen objects for a region."""
        key = self._seen_key(region)
        return await self.client.scard(key)

    async def clear_seen(self, region: int) -> None:
        """Clear all seen IDs for a region (use carefully)."""
        key = self._seen_key(region)
        await self.client.delete(key)
        redis_log.warning(f"Cleared all seen IDs for region {region}")

    # ========== Object Operations ==========

    async def save_object(self, obj: dict) -> None:
        """
        Save object data to Redis with TTL.

        Args:
            obj: Object data dictionary (must have 'id' field)
        """
        object_id = obj["id"]
        key = self._object_key(object_id)
        await self.client.set(key, json.dumps(obj, ensure_ascii=False, default=str))
        await self.client.expire(key, self.TTL_OBJECT)
        redis_log.debug(f"Saved object {object_id} to Redis")

    async def save_objects(self, objects: list[dict]) -> None:
        """
        Save multiple objects to Redis.

        Args:
            objects: List of object dictionaries
        """
        pipe = self.client.pipeline()
        for obj in objects:
            key = self._object_key(obj["id"])
            pipe.set(key, json.dumps(obj, ensure_ascii=False, default=str))
            pipe.expire(key, self.TTL_OBJECT)
        await pipe.execute()
        redis_log.debug(f"Saved {len(objects)} objects to Redis")

    async def get_object(self, object_id: int) -> Optional[dict]:
        """
        Get object data from Redis.

        Args:
            object_id: Object ID

        Returns:
            Object data dictionary or None if not found
        """
        key = self._object_key(object_id)
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None

    async def get_objects(self, object_ids: list[int]) -> list[dict]:
        """
        Get multiple objects from Redis.

        Args:
            object_ids: List of object IDs

        Returns:
            List of object dictionaries (excludes not found)
        """
        if not object_ids:
            return []

        pipe = self.client.pipeline()
        for object_id in object_ids:
            pipe.get(self._object_key(object_id))
        results = await pipe.execute()

        objects = []
        for data in results:
            if data:
                objects.append(json.loads(data))
        return objects

    # ========== Subscription Initialization Operations ==========

    def _subscription_initialized_key(self, subscription_id: int) -> str:
        """Generate key for subscription initialized flag."""
        return f"subscription:{subscription_id}:initialized"

    async def is_subscription_initialized(self, subscription_id: int) -> bool:
        """
        Check if a subscription has been initialized.

        Args:
            subscription_id: Subscription ID

        Returns:
            True if subscription has been initialized
        """
        key = self._subscription_initialized_key(subscription_id)
        return await self.client.exists(key) > 0

    async def mark_subscription_initialized(self, subscription_id: int) -> None:
        """
        Mark a subscription as initialized.

        Args:
            subscription_id: Subscription ID
        """
        key = self._subscription_initialized_key(subscription_id)
        await self.client.set(key, "1")
        await self.client.expire(key, self.TTL_INITIALIZED)
        redis_log.debug(f"Marked subscription {subscription_id} as initialized")

    async def clear_subscription_initialized(self, subscription_id: int) -> None:
        """
        Clear subscription initialized flag.

        Args:
            subscription_id: Subscription ID
        """
        key = self._subscription_initialized_key(subscription_id)
        await self.client.delete(key)
        redis_log.debug(f"Cleared initialized flag for subscription {subscription_id}")

    async def get_uninitialized_subscriptions(
        self, subscriptions: list[dict]
    ) -> list[dict]:
        """
        Filter subscriptions that are not yet initialized.

        Args:
            subscriptions: List of subscription dicts

        Returns:
            List of subscriptions that are NOT initialized
        """
        if not subscriptions:
            return []

        pipe = self.client.pipeline()
        for sub in subscriptions:
            pipe.exists(self._subscription_initialized_key(sub["id"]))
        results = await pipe.execute()

        uninitialized = []
        for sub, exists in zip(subscriptions, results):
            if not exists:
                uninitialized.append(sub)
        return uninitialized

    # ========== Subscription Operations ==========

    async def sync_subscription(self, subscription: dict, was_disabled: bool = False) -> None:
        """
        Sync a subscription to Redis.

        Args:
            subscription: Subscription data (must have 'id', 'region', 'enabled')
            was_disabled: If True, subscription was previously disabled (re-enabling)
        """
        if not subscription.get("enabled", True):
            # Remove disabled subscriptions and clear initialized
            await self.remove_subscription(subscription["region"], subscription["id"])
            await self.clear_subscription_initialized(subscription["id"])
            return

        region = subscription["region"]
        sub_id = str(subscription["id"])
        key = self._subscriptions_key(region)

        # If re-enabling, clear initialized so it gets re-initialized
        if was_disabled:
            await self.clear_subscription_initialized(subscription["id"])
            redis_log.info(f"Subscription {sub_id} re-enabled, will re-initialize")

        # Store subscription as JSON
        await self.client.hset(key, sub_id, json.dumps(subscription, ensure_ascii=False, default=str))
        redis_log.debug(f"Synced subscription {sub_id} to region {region}")

    async def sync_subscriptions(self, subscriptions: list[dict]) -> None:
        """
        Sync multiple subscriptions to Redis.
        This will replace all subscriptions for each affected region.

        Args:
            subscriptions: List of subscription dictionaries
        """
        # Group by region
        by_region: dict[int, dict[str, str]] = {}
        for sub in subscriptions:
            if not sub.get("enabled", True):
                continue
            region = sub["region"]
            if region not in by_region:
                by_region[region] = {}
            by_region[region][str(sub["id"])] = json.dumps(sub, ensure_ascii=False, default=str)

        # Clear and set for each region
        pipe = self.client.pipeline()
        for region, subs in by_region.items():
            key = self._subscriptions_key(region)
            pipe.delete(key)
            if subs:
                pipe.hset(key, mapping=subs)
        await pipe.execute()

        redis_log.info(f"Synced {len(subscriptions)} subscriptions across {len(by_region)} regions")

    async def remove_subscription(self, region: int, subscription_id: int) -> None:
        """
        Remove a subscription from Redis.

        Args:
            region: Region code
            subscription_id: Subscription ID
        """
        key = self._subscriptions_key(region)
        await self.client.hdel(key, str(subscription_id))
        redis_log.debug(f"Removed subscription {subscription_id} from region {region}")

    async def get_subscriptions_by_region(self, region: int) -> list[dict]:
        """
        Get all subscriptions for a region.

        Args:
            region: Region code

        Returns:
            List of subscription dictionaries
        """
        key = self._subscriptions_key(region)
        data = await self.client.hgetall(key)
        return [json.loads(v) for v in data.values()]

    async def get_active_regions(self) -> set[int]:
        """
        Get all regions that have subscriptions.

        Returns:
            Set of region codes
        """
        # Scan for region:*:subscriptions keys
        regions = set()
        async for key in self.client.scan_iter(match="region:*:subscriptions"):
            # Extract region from key "region:{id}:subscriptions"
            parts = key.split(":")
            if len(parts) >= 2:
                try:
                    regions.add(int(parts[1]))
                except ValueError:
                    pass
        return regions


# Singleton instance
_redis: Optional[RedisConnection] = None


async def get_redis() -> RedisConnection:
    """Get Redis connection singleton."""
    global _redis
    if _redis is None:
        _redis = RedisConnection()
        await _redis.connect()
    return _redis


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
