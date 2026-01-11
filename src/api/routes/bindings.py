"""Notification bindings routes."""

import os

from fastapi import APIRouter, HTTPException
from loguru import logger

from src.api.dependencies import CurrentUser
from src.connections.postgres import get_postgres
from src.modules.providers import UserProviderRepository, sync_user_subscriptions_to_redis
from src.modules.bindings import BindCodeResponse, BindingResponse

router = APIRouter(prefix="/bindings", tags=["Bindings"])


async def get_provider_repository() -> UserProviderRepository:
    """Get user provider repository instance."""
    postgres = await get_postgres()
    return UserProviderRepository(postgres.pool)


@router.get("/telegram", response_model=BindingResponse)
async def get_telegram_binding(current_user: CurrentUser) -> dict:
    """
    Get Telegram binding status for current user.

    Requires authentication.
    """
    repo = await get_provider_repository()

    try:
        providers = await repo.get_by_user(current_user.id)
        telegram_provider = next(
            (p for p in providers if p.provider == "telegram"), None
        )

        if not telegram_provider:
            return {
                "service": "telegram",
                "is_bound": False,
                "service_id": None,
                "enabled": False,
                "created_at": None,
            }

        return {
            "service": "telegram",
            "is_bound": True,
            "service_id": telegram_provider.provider_id,
            "enabled": telegram_provider.notify_enabled,
            "created_at": telegram_provider.created_at,
        }
    except Exception as e:
        logger.error(f"Failed to get telegram binding: {e}")
        raise HTTPException(status_code=500, detail="查詢綁定失敗")


@router.post("/telegram", response_model=BindCodeResponse, deprecated=True)
async def bind_telegram(current_user: CurrentUser) -> dict:
    """
    Start Telegram binding process (DEPRECATED).

    This endpoint is deprecated. Use Telegram Web App login instead.
    Generates a bind code and returns a deep link URL.
    The code is valid for 10 minutes.

    Requires authentication.
    """
    # NOTE: This endpoint is deprecated and will be removed.
    # Keep backward compatibility by importing old repository
    from src.modules.bindings import BindingRepository

    postgres = await get_postgres()
    repo = BindingRepository(postgres.pool)

    try:
        code = await repo.create_bind_code(current_user.id, "telegram")
        logger.info(f"Generated bind code for user {current_user.id}")

        response = {
            "code": code,
            "expires_in": repo.BIND_CODE_EXPIRY_MINUTES * 60,
        }

        bot_username = os.getenv("TELEGRAM_BOT_USERNAME")
        if bot_username:
            response["bind_url"] = f"https://t.me/{bot_username}?start=BIND_{code}"

        return response
    except Exception as e:
        logger.error(f"Failed to generate bind code: {e}")
        raise HTTPException(status_code=500, detail="產生綁定碼失敗")


@router.delete("/telegram")
async def unbind_telegram(current_user: CurrentUser) -> dict:
    """
    Delete Telegram binding for current user.

    Requires authentication.
    """
    repo = await get_provider_repository()

    try:
        deleted = await repo.delete(current_user.id, "telegram")

        if not deleted:
            raise HTTPException(status_code=404, detail="綁定不存在")

        logger.info(f"Deleted telegram binding for user {current_user.id}")

        # Sync subscriptions to Redis (removes service_id from cached subscriptions)
        await sync_user_subscriptions_to_redis(current_user.id)

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete binding: {e}")
        raise HTTPException(status_code=500, detail="解除綁定失敗")


@router.patch("/telegram/toggle")
async def toggle_telegram(current_user: CurrentUser, enabled: bool) -> dict:
    """
    Enable or disable Telegram notifications.

    Requires authentication.

    Args:
        enabled: Whether to enable notifications
    """
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

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle binding: {e}")
        raise HTTPException(status_code=500, detail="更新失敗")
