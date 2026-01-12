"""Subscription CRUD routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from src.api.dependencies import CurrentUser

subs_log = logger.bind(module="Subscriptions")

from src.connections.postgres import get_postgres
from src.connections.redis import get_redis
from src.modules.subscriptions import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
    SubscriptionRepository,
    parse_floor_ranges,
)
from src.modules.users import UserRepository
from src.modules.providers import sync_user_subscriptions_to_redis

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


async def get_repository() -> SubscriptionRepository:
    """Get subscription repository instance."""
    postgres = await get_postgres()
    return SubscriptionRepository(postgres.pool)


async def remove_subscription_from_redis(
    region: int, subscription_id: int, max_retries: int = 3, retry_delay: float = 0.5
) -> None:
    """
    Remove a subscription from Redis cache with retry mechanism.

    Args:
        region: Region code
        subscription_id: Subscription ID
        max_retries: Maximum retry attempts
        retry_delay: Initial delay between retries (exponential backoff)
    """
    import asyncio
    from loguru import logger

    for attempt in range(max_retries):
        try:
            redis = await get_redis()
            await redis.remove_subscription(region, subscription_id)
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                subs_log.warning(
                    f"Redis remove failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                subs_log.error(
                    f"Redis remove failed after {max_retries} attempts: {e}. "
                    f"Subscription {subscription_id} may still exist in Redis."
                )


@router.post("", status_code=201)
async def create_subscription(
    data: SubscriptionCreate,
    current_user: CurrentUser,
) -> dict:
    """
    Create a new subscription.

    Requires authentication.

    Args:
        data: Subscription data
    """
    import asyncio
    from src.modules.providers import UserProviderRepository

    repo = await get_repository()
    postgres = await get_postgres()
    user_repo = UserRepository(postgres.pool)

    # Check subscription limit based on user role
    count = await repo.count_by_user(current_user.id)
    max_subs = await user_repo.get_role_limit(current_user.role)

    if count >= max_subs:
        raise HTTPException(
            status_code=400,
            detail=f"已達訂閱數量上限 ({max_subs})"
        )

    try:
        subscription = await repo.create(
            user_id=current_user.id,
            data=data.model_dump()
        )

        # Sync all user subscriptions to Redis (includes provider info)
        await sync_user_subscriptions_to_redis(current_user.id)

        subs_log.info(f"Created subscription {subscription['id']} for user {current_user.id}")

        # Trigger instant notification in background
        provider_repo = UserProviderRepository(postgres.pool)
        providers = await provider_repo.get_by_user(current_user.id)

        # Find active provider with notifications enabled
        active_provider = next(
            (p for p in providers if p.notify_enabled),
            None
        )

        if active_provider:
            from src.jobs.instant_notify import notify_for_new_subscription

            asyncio.create_task(
                notify_for_new_subscription(
                    user_id=current_user.id,
                    subscription=subscription,
                    service=active_provider.provider,
                    service_id=active_provider.provider_id,
                )
            )
            subs_log.info(f"Triggered instant notify for subscription {subscription['id']}")

        return {"success": True}
    except Exception as e:
        subs_log.error(f"Failed to create subscription: {e}")
        raise HTTPException(status_code=500, detail="建立訂閱失敗")


@router.get("", response_model=SubscriptionListResponse)
async def list_subscriptions(
    current_user: CurrentUser,
    enabled_only: bool = False,
) -> dict:
    """
    List all subscriptions for current user.

    Requires authentication.

    Args:
        enabled_only: Filter by enabled status
    """
    repo = await get_repository()
    subscriptions = await repo.get_by_user(current_user.id, enabled_only)
    return {
        "total": len(subscriptions),
        "items": subscriptions
    }


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    current_user: CurrentUser,
) -> dict:
    """
    Get a single subscription.

    Requires authentication.

    Args:
        subscription_id: Subscription ID
    """
    repo = await get_repository()
    subscription = await repo.get_by_id(subscription_id)

    if not subscription:
        raise HTTPException(status_code=404, detail="訂閱不存在")

    if subscription["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="無權限存取此訂閱")

    return subscription


@router.put("/{subscription_id}")
async def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdate,
    current_user: CurrentUser,
) -> dict:
    """
    Update a subscription.

    Requires authentication.

    Args:
        subscription_id: Subscription ID
        data: Fields to update
    """
    repo = await get_repository()

    # Check ownership
    existing = await repo.get_by_id(subscription_id)
    if not existing:
        raise HTTPException(status_code=404, detail="訂閱不存在")

    if existing["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="無權限修改此訂閱")

    # Update
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        return {"success": True}

    # Convert floor list to floor_min/floor_max for storage
    if "floor" in update_data:
        floor_list = update_data.pop("floor")
        floor_min, floor_max = parse_floor_ranges(floor_list)
        update_data["floor_min"] = floor_min
        update_data["floor_max"] = floor_max

    try:
        subscription = await repo.update(subscription_id, update_data)

        # Sync all user subscriptions to Redis (includes provider info)
        await sync_user_subscriptions_to_redis(current_user.id)

        subs_log.info(f"Updated subscription {subscription_id}")
        return {"success": True}
    except Exception as e:
        subs_log.error(f"Failed to update subscription: {e}")
        raise HTTPException(status_code=500, detail="更新訂閱失敗")


@router.delete("/{subscription_id}")
async def delete_subscription(
    subscription_id: int,
    current_user: CurrentUser,
) -> dict:
    """
    Delete a subscription.

    Requires authentication.

    Args:
        subscription_id: Subscription ID
    """
    repo = await get_repository()

    # Check ownership
    existing = await repo.get_by_id(subscription_id)
    if not existing:
        raise HTTPException(status_code=404, detail="訂閱不存在")

    if existing["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="無權限刪除此訂閱")

    try:
        await repo.delete(subscription_id)

        # Remove from Redis
        await remove_subscription_from_redis(existing["region"], subscription_id)

        subs_log.info(f"Deleted subscription {subscription_id}")
        return {"success": True}
    except Exception as e:
        subs_log.error(f"Failed to delete subscription: {e}")
        raise HTTPException(status_code=500, detail="刪除訂閱失敗")


@router.patch("/{subscription_id}/toggle")
async def toggle_subscription(
    subscription_id: int,
    current_user: CurrentUser,
) -> dict:
    """
    Toggle subscription enabled status.

    Requires authentication.

    Args:
        subscription_id: Subscription ID
    """
    import asyncio
    from src.modules.providers import UserProviderRepository

    repo = await get_repository()
    postgres = await get_postgres()

    # Check ownership
    existing = await repo.get_by_id(subscription_id)
    if not existing:
        raise HTTPException(status_code=404, detail="訂閱不存在")

    if existing["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="無權限修改此訂閱")

    # Toggle
    was_disabled = not existing["enabled"]  # True if currently disabled, will be enabled
    new_status = not existing["enabled"]
    subscription = await repo.update(
        subscription_id,
        {"enabled": new_status}
    )

    # Sync all user subscriptions to Redis (includes provider info)
    await sync_user_subscriptions_to_redis(current_user.id)

    # If re-enabling, trigger instant notification
    if was_disabled and new_status:
        provider_repo = UserProviderRepository(postgres.pool)
        providers = await provider_repo.get_by_user(current_user.id)

        active_provider = next(
            (p for p in providers if p.notify_enabled),
            None
        )

        if active_provider:
            from src.jobs.instant_notify import notify_for_new_subscription

            asyncio.create_task(
                notify_for_new_subscription(
                    user_id=current_user.id,
                    subscription=subscription,
                    service=active_provider.provider,
                    service_id=active_provider.provider_id,
                )
            )
            subs_log.info(f"Triggered instant notify for re-enabled subscription {subscription_id}")

    subs_log.info(f"Toggled subscription {subscription_id} to {new_status}")
    return {"success": True}
