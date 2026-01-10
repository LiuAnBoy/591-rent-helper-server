"""Subscription CRUD routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from src.api.dependencies import CurrentUser
from src.connections.postgres import get_postgres
from src.connections.redis import get_redis
from src.modules.subscriptions import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    SubscriptionListResponse,
    SubscriptionRepository,
)
from src.modules.users import UserRepository

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


async def get_repository() -> SubscriptionRepository:
    """Get subscription repository instance."""
    postgres = await get_postgres()
    return SubscriptionRepository(postgres.pool)


async def sync_subscription_to_redis(
    subscription: dict,
    was_disabled: bool = False,
    max_retries: int = 3,
    retry_delay: float = 0.5
) -> None:
    """
    Sync a subscription to Redis cache with retry mechanism.

    Args:
        subscription: Subscription data
        was_disabled: If True, subscription was previously disabled (re-enabling)
        max_retries: Maximum retry attempts
        retry_delay: Initial delay between retries (exponential backoff)
    """
    import asyncio
    from loguru import logger

    for attempt in range(max_retries):
        try:
            redis = await get_redis()
            await redis.sync_subscription(subscription, was_disabled=was_disabled)
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logger.warning(
                    f"Redis sync failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    f"Redis sync failed after {max_retries} attempts: {e}. "
                    f"Subscription {subscription.get('id')} may be out of sync."
                )


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
                logger.warning(
                    f"Redis remove failed (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    f"Redis remove failed after {max_retries} attempts: {e}. "
                    f"Subscription {subscription_id} may still exist in Redis."
                )


@router.post("", response_model=SubscriptionResponse, status_code=201)
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

        # Sync to Redis
        await sync_subscription_to_redis(subscription)

        logger.info(f"Created subscription {subscription['id']} for user {current_user.id}")
        return subscription
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
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


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
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
        return existing

    try:
        subscription = await repo.update(subscription_id, update_data)

        # Sync to Redis
        await sync_subscription_to_redis(subscription)

        logger.info(f"Updated subscription {subscription_id}")
        return subscription
    except Exception as e:
        logger.error(f"Failed to update subscription: {e}")
        raise HTTPException(status_code=500, detail="更新訂閱失敗")


@router.delete("/{subscription_id}", status_code=204)
async def delete_subscription(
    subscription_id: int,
    current_user: CurrentUser,
) -> None:
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

        logger.info(f"Deleted subscription {subscription_id}")
    except Exception as e:
        logger.error(f"Failed to delete subscription: {e}")
        raise HTTPException(status_code=500, detail="刪除訂閱失敗")


@router.patch("/{subscription_id}/toggle", response_model=SubscriptionResponse)
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
    repo = await get_repository()

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

    # Sync to Redis (pass was_disabled to trigger re-initialization if re-enabling)
    await sync_subscription_to_redis(subscription, was_disabled=was_disabled and new_status)

    logger.info(f"Toggled subscription {subscription_id} to {new_status}")
    return subscription
