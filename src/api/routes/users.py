"""User routes."""

from fastapi import APIRouter
from loguru import logger

from src.api.dependencies import CurrentUser
from src.connections.postgres import get_postgres
from src.modules.bindings import BindingRepository
from src.modules.subscriptions import SubscriptionRepository
from src.modules.users import UserRepository, UserWithBindings

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserWithBindings)
async def get_current_user_profile(current_user: CurrentUser) -> dict:
    """
    Get current user's profile with bindings.

    Returns user data including:
    - Basic profile info
    - Notification bindings (Telegram, etc.)
    - Subscription count and limit
    """
    postgres = await get_postgres()

    # Get bindings
    binding_repo = BindingRepository(postgres.pool)
    bindings = await binding_repo.get_bindings_by_user(current_user.id)

    # Format bindings for response
    bindings_data = [
        {
            "service": b.service,
            "is_bound": b.is_bound,
            "service_id": b.service_id if b.is_bound else None,
            "enabled": b.enabled,
            "created_at": b.created_at,
        }
        for b in bindings
    ]

    # Get subscription count
    sub_repo = SubscriptionRepository(postgres.pool)
    sub_count = await sub_repo.count_by_user(current_user.id)

    # Get max subscriptions for user's role
    user_repo = UserRepository(postgres.pool)
    max_subs = await user_repo.get_role_limit(current_user.role)

    logger.debug(f"Fetched profile for user {current_user.id}")

    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "enabled": current_user.enabled,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "bindings": bindings_data,
        "subscription_count": sub_count,
        "max_subscriptions": max_subs,
    }
