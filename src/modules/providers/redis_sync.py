"""
Provider Sync Utilities.

Handles syncing subscription data to Redis after provider changes.
"""

from loguru import logger

from src.connections.postgres import get_postgres
from src.connections.redis import get_redis
from src.modules.subscriptions import SubscriptionRepository

sync_log = logger.bind(module="Sync")


async def sync_user_subscriptions_to_redis(user_id: int) -> int:
    """
    Sync a specific user's subscriptions to Redis after provider change.

    This updates the Redis cache with the latest provider info (service_id)
    so that notifications are sent to the correct destination.

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
            f"Synced subscriptions to Redis after provider change for user {user_id} "
            f"({len(user_subs)} user subs, {len(all_subscriptions)} total)"
        )
        return len(user_subs)

    except Exception as e:
        sync_log.error(f"Failed to sync subscriptions to Redis: {e}")
        return 0
