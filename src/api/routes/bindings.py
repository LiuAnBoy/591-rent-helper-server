"""Notification bindings routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from src.api.dependencies import CurrentUser
from src.connections.postgres import get_postgres
from src.modules.providers import UserProviderRepository, sync_user_subscriptions_to_redis

router = APIRouter(prefix="/bindings", tags=["Bindings"])


async def get_provider_repository() -> UserProviderRepository:
    """Get user provider repository instance."""
    postgres = await get_postgres()
    return UserProviderRepository(postgres.pool)


@router.patch("/telegram/toggle")
async def toggle_telegram(current_user: CurrentUser, enabled: bool) -> dict:
    """
    Enable or disable Telegram notifications.

    Requires authentication.

    Args:
        enabled: Whether to enable notifications
    """
    import asyncio
    from src.modules.subscriptions import SubscriptionRepository

    repo = await get_provider_repository()

    try:
        # Check if provider exists
        providers = await repo.get_by_user(current_user.id)
        telegram_provider = next(
            (p for p in providers if p.provider == "telegram"), None
        )

        if not telegram_provider:
            raise HTTPException(status_code=404, detail="尚未綁定 Telegram")

        updated = await repo.update_notify_enabled(current_user.id, "telegram", enabled)

        if not updated:
            raise HTTPException(status_code=500, detail="更新失敗")

        logger.info(f"Toggled telegram binding for user {current_user.id}: {enabled}")

        # Sync subscriptions to Redis (updates enabled status in cached subscriptions)
        await sync_user_subscriptions_to_redis(current_user.id)

        # Trigger instant notification when enabling notifications
        if enabled:
            postgres = await get_postgres()
            sub_repo = SubscriptionRepository(postgres.pool)
            subscriptions = await sub_repo.get_by_user(current_user.id, enabled_only=True)

            if subscriptions:
                from src.jobs.instant_notify import notify_for_new_subscription

                for sub in subscriptions:
                    asyncio.create_task(
                        notify_for_new_subscription(
                            user_id=current_user.id,
                            subscription=sub,
                            service="telegram",
                            service_id=telegram_provider.provider_id,
                        )
                    )
                logger.info(f"Triggered instant notify for {len(subscriptions)} subscriptions")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle binding: {e}")
        raise HTTPException(status_code=500, detail="更新失敗")
