"""Subscription mutation service.

Single path for "change a subscription's enabled / sources -> sync Redis ->
optionally fire instant notify". Reused by REST routes and TG callbacks so the
side-effects never diverge between entry points.

``sync_subscription_to_redis`` already removes a now-disabled subscription from
its region and clears its initialized flag, and re-adds it (clearing initialized
for re-init) when enabled — so both enable and disable go through one sync call,
mirroring the existing ``PATCH /subscriptions/{id}/toggle`` behavior.
"""

import asyncio

from loguru import logger

from src.modules.providers import sync_subscription_to_redis
from src.modules.subscriptions.repository import SubscriptionRepository

svc_log = logger.bind(module="SubscriptionService")


async def _sync_and_maybe_notify(
    repo: SubscriptionRepository, subscription_id: int, was_disabled: bool
) -> dict | None:
    """Resync one subscription to Redis; fire instant-notify if it was re-enabled.

    Args:
        repo: Subscription repository.
        subscription_id: Subscription ID.
        was_disabled: True if this change re-enabled a previously-disabled sub
            (clears initialized + triggers an immediate catch-up notify).

    Returns:
        The provider-joined subscription dict, or None if it vanished.
    """
    sub = await repo.get_by_id_with_provider(subscription_id)
    if not sub:
        return None
    await sync_subscription_to_redis(sub, was_disabled=was_disabled)
    if (
        was_disabled
        and sub.get("enabled")
        and sub.get("service")
        and sub.get("service_id")
    ):
        from src.jobs.instant_notify import notify_for_new_subscription

        asyncio.create_task(
            notify_for_new_subscription(
                user_id=sub["user_id"],
                subscription=sub,
                service=sub["service"],
                service_id=sub["service_id"],
            )
        )
        svc_log.info(
            f"Triggered instant notify for re-enabled subscription {sub['id']}"
        )
    return sub


async def set_enabled(
    repo: SubscriptionRepository, existing: dict, enabled: bool
) -> dict | None:
    """Set whole-subscription enabled (master switch). Does NOT touch sources.

    Args:
        repo: Subscription repository.
        existing: Current subscription row (must have id, enabled).
        enabled: Target enabled state.

    Returns:
        The provider-joined subscription dict after sync, or None.
    """
    was_disabled = (not existing["enabled"]) and enabled
    await repo.update(existing["id"], {"enabled": enabled})
    return await _sync_and_maybe_notify(repo, existing["id"], was_disabled)


async def set_source_enabled(
    repo: SubscriptionRepository, existing: dict, source: str, enabled: bool
) -> dict | None:
    """Mute/unmute one source for a subscription (only ``disabled_sources``).

    Does NOT touch ``subscriptions.enabled`` — source state is purely the
    ``disabled_sources`` array; a fully-muted subscription simply matches nothing
    via the source guard. After the change we resync to Redis so the match-loop
    guard sees the new array; ``enabled`` is untouched, so no re-init / notify.

    Args:
        repo: Subscription repository.
        existing: Current subscription row (must have id).
        source: Source.key to toggle.
        enabled: True = receive this source, False = mute it.

    Returns:
        The updated subscription row (with disabled_sources), or None.
    """
    updated = await repo.set_source_enabled(existing["id"], source, enabled)
    if not updated:
        return None
    sub = await repo.get_by_id_with_provider(existing["id"])
    if sub:
        await sync_subscription_to_redis(sub, was_disabled=False)
    return updated
