"""User routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from src.api.dependencies import CurrentUser
from src.connections.postgres import get_postgres
from src.modules.providers import UserProviderRepository
from src.modules.subscriptions import SubscriptionRepository
from src.modules.users import UserRepository, UserWithBindings

users_log = logger.bind(module="Users")

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserWithBindings)
async def get_current_user_profile(current_user: CurrentUser) -> dict:
    """
    Get current user's profile with providers.

    Returns user data including:
    - Basic profile info
    - Provider bindings (Telegram, etc.)
    - Subscription count and limit
    """
    if not current_user:
        raise HTTPException(status_code=404, detail="找不到使用者")

    postgres = await get_postgres()

    # Get providers
    provider_repo = UserProviderRepository(postgres.pool)
    providers = await provider_repo.get_by_user(current_user.id)

    # Format providers for response (backward compatible with "bindings" key)
    bindings_data = [
        {
            "service": p.provider,
            "is_bound": True,
            "service_id": p.provider_id,
            "enabled": p.notify_enabled,
            "created_at": p.created_at,
        }
        for p in providers
    ]

    # Get subscription count
    sub_repo = SubscriptionRepository(postgres.pool)
    sub_count = await sub_repo.count_by_user(current_user.id)

    # Get max subscriptions for user's role
    user_repo = UserRepository(postgres.pool)
    max_subs = await user_repo.get_role_limit(current_user.role)

    users_log.debug(f"Fetched profile for user {current_user.id}")

    return {
        "id": current_user.id,
        "email": current_user.email or "",
        "name": current_user.name,
        "role": current_user.role,
        "enabled": current_user.enabled,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "bindings": bindings_data,
        "subscription_count": sub_count,
        "max_subscriptions": max_subs,
    }
