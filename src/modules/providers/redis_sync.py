"""
Provider Sync Utilities.

Handles syncing subscription data to Redis.
"""

import asyncio

from loguru import logger

from src.connections.postgres import get_postgres
from src.connections.redis import get_redis
from src.modules.subscriptions import SubscriptionRepository

sync_log = logger.bind(module="Sync")


async def sync_subscription_to_redis(
    subscription: dict, was_disabled: bool = False
) -> bool:
    """
    Sync a single subscription to Redis.

    Args:
        subscription: Subscription data (must have 'id', 'region', 'enabled')
        was_disabled: If True, subscription was previously disabled (re-enabling)

    Returns:
        True if successful, False otherwise
    """
    try:
        redis = await get_redis()
        await redis.sync_subscription(subscription, was_disabled)
        sync_log.debug(f"Synced subscription {subscription['id']} to Redis")
        return True
    except Exception as e:
        sync_log.error(f"Failed to sync subscription {subscription['id']} to Redis: {e}")
        return False


async def remove_subscription_from_redis(
    region: int, subscription_id: int, max_retries: int = 3, retry_delay: float = 0.5
) -> bool:
    """
    Remove a subscription from Redis cache with retry mechanism.

    Args:
        region: Region code
        subscription_id: Subscription ID
        max_retries: Maximum retry attempts
        retry_delay: Initial delay between retries (exponential backoff)

    Returns:
        True if successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            redis = await get_redis()
            await redis.remove_subscription(region, subscription_id)
            sync_log.debug(f"Removed subscription {subscription_id} from Redis")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2**attempt)
                sync_log.warning(
                    f"Redis remove failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                sync_log.error(
                    f"Redis remove failed after {max_retries} attempts: {e}. "
                    f"Subscription {subscription_id} may still exist in Redis."
                )
                return False
    return False


async def sync_user_subscriptions_to_redis(user_id: int) -> int:
    """
    Sync all subscriptions of a specific user to Redis.

    Used when provider settings change (e.g., toggle_telegram, pause, resume).

    Args:
        user_id: User ID whose subscriptions need syncing

    Returns:
        Number of subscriptions synced
    """
    try:
        postgres = await get_postgres()
        redis = await get_redis()

        repo = SubscriptionRepository(postgres.pool)

        # Get all enabled subscriptions (with provider info)
        all_subscriptions = await repo.get_all_enabled()

        # Sync all to Redis (this replaces by region)
        await redis.sync_subscriptions(all_subscriptions)

        # Count user's subscriptions
        user_subs = [s for s in all_subscriptions if s.get("user_id") == user_id]

        sync_log.info(
            f"Synced subscriptions to Redis for user {user_id} "
            f"({len(user_subs)} user subs, {len(all_subscriptions)} total)"
        )
        return len(user_subs)

    except Exception as e:
        sync_log.error(f"Failed to sync subscriptions to Redis: {e}")
        return 0
