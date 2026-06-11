"""
Notification Control Commands.

The "暫停通知 / 開始通知" commands no longer toggle immediately — they reply with
a dynamic inline menu (built by the Telegram handler from the user's current
state). The actual user-level toggle lives in ``apply_user_notify`` so both the
menu callbacks and any direct caller share one implementation.
"""

import asyncio

from asyncpg import Pool
from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult

cmd_log = logger.bind(module="BotCommand")
from src.modules.providers import (  # noqa: E402
    UserProviderRepository,
    sync_user_subscriptions_to_redis,
)


async def apply_user_notify(
    pool: Pool, service: str, provider_id: str, enabled: bool
) -> dict:
    """Set user-level ``notify_enabled`` and resync; resume also batch-notifies.

    Shared by the TG menu callbacks (and any future direct caller) so the
    user-level pause/resume side-effects never diverge.

    Args:
        pool: Database pool.
        service: Provider name (e.g. "telegram").
        provider_id: Platform user id (chat_id for Telegram private chats).
        enabled: Target notify_enabled state.

    Returns:
        ``{"ok": bool, "changed": bool, "has_enabled_subs": bool}``.
    """
    from src.modules.subscriptions import SubscriptionRepository

    repo = UserProviderRepository(pool)
    provider = await repo.find_by_provider(provider=service, provider_id=provider_id)
    if not provider:
        return {"ok": False, "changed": False, "has_enabled_subs": False}

    sub_repo = SubscriptionRepository(pool)
    enabled_subs = await sub_repo.get_by_user(provider.user_id, enabled_only=True)
    has_enabled_subs = bool(enabled_subs)

    if provider.notify_enabled == enabled:
        return {"ok": True, "changed": False, "has_enabled_subs": has_enabled_subs}

    await repo.update_notify_enabled(provider.user_id, service, enabled)
    await sync_user_subscriptions_to_redis(provider.user_id)
    cmd_log.info(f"Set notify_enabled={enabled} for user {provider.user_id} ({service})")

    if enabled and enabled_subs:
        from src.jobs.instant_notify import notify_for_subscriptions_batch

        asyncio.create_task(
            notify_for_subscriptions_batch(
                user_id=provider.user_id,
                subscriptions=enabled_subs,
                service=service,
                service_id=provider_id,
            )
        )

    return {"ok": True, "changed": True, "has_enabled_subs": has_enabled_subs}


class PauseCommand(BaseCommand):
    """Pause command - replies with the pause menu (per-item turn off)."""

    name = "pause"
    description = "Pause notifications"
    usage = "/pause"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: dict | None = None,
    ) -> CommandResult:
        """Reply with the pause menu; the handler fills in the dynamic buttons."""
        return CommandResult.ok(
            message="選擇要暫停的項目：", title="notify_pause_menu"
        )


class ResumeCommand(BaseCommand):
    """Resume command - replies with the resume menu (per-item turn on)."""

    name = "resume"
    description = "Resume notifications"
    usage = "/resume"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: dict | None = None,
    ) -> CommandResult:
        """Reply with the resume menu; the handler fills in the dynamic buttons."""
        return CommandResult.ok(
            message="選擇要恢復的項目：", title="notify_resume_menu"
        )
