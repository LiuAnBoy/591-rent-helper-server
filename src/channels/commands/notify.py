"""
Notification Control Commands.

Handles /pause and /resume commands for notification control.
"""

from typing import Optional

from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult
from src.modules.providers import UserProviderRepository, sync_user_subscriptions_to_redis


class PauseCommand(BaseCommand):
    """Pause command - disables notifications."""

    name = "pause"
    description = "Pause notifications"
    usage = "/pause"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: Optional[dict] = None,
    ) -> CommandResult:
        """
        Execute /pause command.

        Args:
            user_id: Platform user ID (chat_id)
            args: Command arguments (unused)
            context: Must contain 'service' key

        Returns:
            Result indicating notifications are paused
        """
        if not self._pool:
            logger.error("Database pool not available for pause command")
            return CommandResult.fail("系統錯誤，請稍後再試")

        service = context.get("service", "telegram") if context else "telegram"

        repo = UserProviderRepository(self._pool)

        # Find provider binding
        provider = await repo.find_by_provider(provider=service, provider_id=user_id)

        if not provider:
            return CommandResult.fail("尚未綁定帳號。請點擊「開啟管理頁面」按鈕登入。")

        # Check if already paused
        if not provider.notify_enabled:
            return CommandResult.ok(
                message="通知已經是暫停狀態",
                title="notify_already_paused",
            )

        # Disable notifications
        updated = await repo.update_notify_enabled(provider.user_id, service, False)

        if not updated:
            return CommandResult.fail("更新失敗，請稍後再試")

        # Sync to Redis
        await sync_user_subscriptions_to_redis(provider.user_id)

        logger.info(f"Paused notifications for user {provider.user_id} ({service}:{user_id})")

        return CommandResult.ok(
            message="已暫停通知。輸入 /resume 可恢復通知。",
            title="notify_paused",
        )


class ResumeCommand(BaseCommand):
    """Resume command - enables notifications."""

    name = "resume"
    description = "Resume notifications"
    usage = "/resume"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: Optional[dict] = None,
    ) -> CommandResult:
        """
        Execute /resume command.

        Args:
            user_id: Platform user ID (chat_id)
            args: Command arguments (unused)
            context: Must contain 'service' key

        Returns:
            Result indicating notifications are resumed
        """
        import asyncio
        from src.modules.subscriptions import SubscriptionRepository

        if not self._pool:
            logger.error("Database pool not available for resume command")
            return CommandResult.fail("系統錯誤，請稍後再試")

        service = context.get("service", "telegram") if context else "telegram"

        repo = UserProviderRepository(self._pool)

        # Find provider binding
        provider = await repo.find_by_provider(provider=service, provider_id=user_id)

        if not provider:
            return CommandResult.fail("尚未綁定帳號。請點擊「開啟管理頁面」按鈕登入。")

        # Check if already enabled
        if provider.notify_enabled:
            return CommandResult.ok(
                message="通知已經是開啟狀態",
                title="notify_already_enabled",
            )

        # Enable notifications
        updated = await repo.update_notify_enabled(provider.user_id, service, True)

        if not updated:
            return CommandResult.fail("更新失敗，請稍後再試")

        # Sync to Redis
        await sync_user_subscriptions_to_redis(provider.user_id)

        logger.info(f"Resumed notifications for user {provider.user_id} ({service}:{user_id})")

        # Trigger instant notification for all enabled subscriptions (batch mode)
        sub_repo = SubscriptionRepository(self._pool)
        subscriptions = await sub_repo.get_by_user(provider.user_id, enabled_only=True)

        if subscriptions:
            from src.jobs.instant_notify import notify_for_subscriptions_batch

            asyncio.create_task(
                notify_for_subscriptions_batch(
                    user_id=provider.user_id,
                    subscriptions=subscriptions,
                    service=service,
                    service_id=user_id,
                )
            )

            logger.info(f"Triggered batch instant notify for {len(subscriptions)} subscriptions")

        return CommandResult.ok(
            message="已恢復通知。有新物件時會立即通知你！",
            title="notify_resumed",
        )
