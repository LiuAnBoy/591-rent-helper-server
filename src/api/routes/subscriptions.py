"""Subscription CRUD routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from src.api.dependencies import CurrentUser

subs_log = logger.bind(module="Subscriptions")

from src.connections.postgres import get_postgres  # noqa: E402
from src.modules.providers import (  # noqa: E402
    remove_subscription_from_redis,
    sync_subscription_to_redis,
)
from src.modules.subscriptions import (  # noqa: E402
    SubscriptionCreate,
    SubscriptionListResponse,
    SubscriptionRepository,
    SubscriptionResponse,
    SubscriptionUpdate,
    parse_floor_ranges,
)
from src.modules.users import UserRepository  # noqa: E402

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


async def get_repository() -> SubscriptionRepository:
    """Get subscription repository instance."""
    postgres = await get_postgres()
    return SubscriptionRepository(postgres.pool)


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

    postgres = await get_postgres()
    repo = SubscriptionRepository(postgres.pool)
    user_repo = UserRepository(postgres.pool)

    # Check subscription limit based on user role
    count = await repo.count_by_user(current_user.id)
    max_subs = await user_repo.get_role_limit(current_user.role)

    if count >= max_subs:
        raise HTTPException(status_code=400, detail=f"已達訂閱數量上限 ({max_subs})")

    try:
        # Convert floor list to floor_min/floor_max for storage
        create_data = data.model_dump()
        if "floor" in create_data and create_data["floor"]:
            floor_list = create_data.pop("floor")
            floor_min, floor_max = parse_floor_ranges(floor_list)
            create_data["floor_min"] = floor_min
            create_data["floor_max"] = floor_max
        elif "floor" in create_data:
            create_data.pop("floor")

        subscription = await repo.create(user_id=current_user.id, data=create_data)

        # Get subscription with provider info for Redis sync
        sub_with_provider = await repo.get_by_id_with_provider(subscription["id"])

        if sub_with_provider:
            # Sync single subscription to Redis
            await sync_subscription_to_redis(sub_with_provider)

            # Trigger instant notification in background if provider enabled
            if sub_with_provider.get("service") and sub_with_provider.get("service_id"):
                from src.jobs.instant_notify import notify_for_new_subscription

                asyncio.create_task(
                    notify_for_new_subscription(
                        user_id=current_user.id,
                        subscription=sub_with_provider,
                        service=sub_with_provider["service"],
                        service_id=sub_with_provider["service_id"],
                    )
                )
                subs_log.info(
                    f"Triggered instant notify for subscription {subscription['id']}"
                )

        subs_log.info(
            f"Created subscription {subscription['id']} for user {current_user.id}"
        )

        return {"success": True}
    except Exception as e:
        subs_log.error(f"Failed to create subscription: {e}")
        raise HTTPException(status_code=500, detail="建立訂閱失敗") from None


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
    return {"total": len(subscriptions), "items": subscriptions}


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

    # Detect region change
    old_region = existing["region"]
    new_region = update_data.get("region", old_region)
    region_changed = old_region != new_region

    try:
        await repo.update(subscription_id, update_data)

        # If region changed, remove from old region first
        if region_changed:
            await remove_subscription_from_redis(old_region, subscription_id)
            subs_log.info(
                f"Subscription {subscription_id} region changed: {old_region} -> {new_region}"
            )

        # Get updated subscription with provider info and sync to Redis
        sub_with_provider = await repo.get_by_id_with_provider(subscription_id)
        if sub_with_provider:
            await sync_subscription_to_redis(sub_with_provider)

        subs_log.info(f"Updated subscription {subscription_id}")
        return {"success": True}
    except Exception as e:
        subs_log.error(f"Failed to update subscription: {e}")
        raise HTTPException(status_code=500, detail="更新訂閱失敗") from None


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
        raise HTTPException(status_code=500, detail="刪除訂閱失敗") from None


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
    await repo.update(subscription_id, {"enabled": new_status})

    # Get updated subscription with provider info and sync to Redis
    sub_with_provider = await repo.get_by_id_with_provider(subscription_id)
    if sub_with_provider:
        await sync_subscription_to_redis(sub_with_provider, was_disabled=was_disabled)

        # If re-enabling, trigger instant notification
        if was_disabled and new_status:
            if sub_with_provider.get("service") and sub_with_provider.get("service_id"):
                from src.jobs.instant_notify import notify_for_new_subscription

                asyncio.create_task(
                    notify_for_new_subscription(
                        user_id=current_user.id,
                        subscription=sub_with_provider,
                        service=sub_with_provider["service"],
                        service_id=sub_with_provider["service_id"],
                    )
                )
                subs_log.info(
                    f"Triggered instant notify for re-enabled subscription {subscription_id}"
                )

    subs_log.info(f"Toggled subscription {subscription_id} to {new_status}")
    return {"success": True}
