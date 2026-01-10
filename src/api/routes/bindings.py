"""Notification bindings routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from src.api.dependencies import CurrentUser
from src.connections.postgres import get_postgres
from src.modules.bindings import (
    BindingRepository,
    BindCodeResponse,
    BindingResponse,
)

router = APIRouter(prefix="/bindings", tags=["Bindings"])


async def get_repository() -> BindingRepository:
    """Get binding repository instance."""
    postgres = await get_postgres()
    return BindingRepository(postgres.pool)


@router.get("", response_model=list[BindingResponse])
async def list_bindings(current_user: CurrentUser) -> list[dict]:
    """
    Get all notification bindings for current user.

    Requires authentication.
    """
    repo = await get_repository()

    try:
        bindings = await repo.get_bindings_by_user(current_user.id)
        return [
            {
                "service": b.service,
                "is_bound": b.is_bound,
                "service_id": b.service_id if b.is_bound else None,
                "enabled": b.enabled,
                "created_at": b.created_at,
            }
            for b in bindings
        ]
    except Exception as e:
        logger.error(f"Failed to get bindings: {e}")
        raise HTTPException(status_code=500, detail="查詢綁定失敗")


@router.get("/telegram", response_model=BindingResponse)
async def get_telegram_binding(current_user: CurrentUser) -> dict:
    """
    Get Telegram binding status for current user.

    Requires authentication.
    """
    repo = await get_repository()

    try:
        binding = await repo.get_binding_by_user(current_user.id, "telegram")

        if not binding:
            return {
                "service": "telegram",
                "is_bound": False,
                "service_id": None,
                "enabled": False,
                "created_at": None,
            }

        return {
            "service": binding.service,
            "is_bound": binding.is_bound,
            "service_id": binding.service_id if binding.is_bound else None,
            "enabled": binding.enabled,
            "created_at": binding.created_at,
        }
    except Exception as e:
        logger.error(f"Failed to get telegram binding: {e}")
        raise HTTPException(status_code=500, detail="查詢綁定失敗")


@router.post("/telegram/code", response_model=BindCodeResponse)
async def generate_telegram_bind_code(current_user: CurrentUser) -> dict:
    """
    Generate a Telegram bind code for current user.

    The code is valid for 10 minutes.
    Requires authentication.
    """
    repo = await get_repository()

    try:
        code = await repo.create_bind_code(current_user.id, "telegram")
        logger.info(f"Generated bind code for user {current_user.id}")
        return {
            "code": code,
            "expires_in": repo.BIND_CODE_EXPIRY_MINUTES * 60,
        }
    except Exception as e:
        logger.error(f"Failed to generate bind code: {e}")
        raise HTTPException(status_code=500, detail="產生綁定碼失敗")


@router.delete("/telegram")
async def delete_telegram_binding(current_user: CurrentUser) -> dict:
    """
    Delete Telegram binding for current user.

    Requires authentication.
    """
    repo = await get_repository()

    try:
        deleted = await repo.delete_binding(current_user.id, "telegram")

        if not deleted:
            raise HTTPException(status_code=404, detail="綁定不存在")

        logger.info(f"Deleted telegram binding for user {current_user.id}")
        return {"status": True, "message": "已解除 Telegram 綁定"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete binding: {e}")
        raise HTTPException(status_code=500, detail="解除綁定失敗")


@router.patch("/telegram/toggle")
async def toggle_telegram_binding(
    current_user: CurrentUser,
    enabled: bool,
) -> dict:
    """
    Enable or disable Telegram notifications.

    Requires authentication.

    Args:
        enabled: Whether to enable notifications
    """
    repo = await get_repository()

    try:
        binding = await repo.get_binding_by_user(current_user.id, "telegram")
        if not binding or not binding.is_bound:
            raise HTTPException(status_code=404, detail="尚未綁定 Telegram")

        updated = await repo.set_enabled(current_user.id, "telegram", enabled)

        if not updated:
            raise HTTPException(status_code=500, detail="更新失敗")

        status_text = "已啟用" if enabled else "已暫停"
        logger.info(f"Toggled telegram binding for user {current_user.id}: {enabled}")
        return {"status": True, "message": f"Telegram 通知{status_text}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle binding: {e}")
        raise HTTPException(status_code=500, detail="更新失敗")
