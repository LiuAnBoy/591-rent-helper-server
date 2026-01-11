"""
Start Command Module.

Handles the /start command - shows welcome message or completes binding.
"""

from typing import Optional

from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult
from src.modules.bindings import BindingRepository
from src.modules.providers import sync_user_subscriptions_to_redis


class StartCommand(BaseCommand):
    """Welcome command - shows introduction or handles binding."""

    name = "start"
    description = "Start using the bot"
    usage = "/start"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: Optional[dict] = None,
    ) -> CommandResult:
        """
        Execute /start command.

        If args contains BIND_<code>, complete the binding (deprecated).
        Otherwise, show welcome message with Web App button.

        Args:
            user_id: Platform user ID (chat_id)
            args: Command arguments (may contain bind code)
            context: Optional context

        Returns:
            Binding result or welcome message
        """
        # Check if this is a binding request via deep link (deprecated)
        if args.startswith("BIND_"):
            return await self._handle_binding(user_id, args[5:])

        # Normal welcome message - Web App flow
        steps = [
            "點擊下方「開啟管理頁面」按鈕",
            "自動登入後設定篩選條件",
            "開始接收新物件通知！",
        ]

        return CommandResult.ok(
            message="歡迎使用 591 租屋通知",
            title="welcome",
            user_id=user_id,
            steps=steps,
        )

    async def _handle_binding(self, chat_id: str, code: str) -> CommandResult:
        """
        Handle binding request from deep link.

        Args:
            chat_id: Telegram chat ID
            code: Bind code (without BIND_ prefix)

        Returns:
            Binding success or failure result
        """
        import os

        if not self._pool:
            logger.error("Database pool not available")
            return CommandResult.fail("系統錯誤，請稍後再試")

        code = code.strip()
        if not code:
            return CommandResult.fail("綁定碼無效")

        repo = BindingRepository(self._pool)

        try:
            user_id = await repo.verify_bind_code("telegram", code, chat_id)

            if user_id:
                logger.info(f"Binding completed: user {user_id} -> telegram:{chat_id}")

                # Sync subscriptions to Redis so notifications work immediately
                await sync_user_subscriptions_to_redis(user_id)

                return CommandResult.ok(
                    message="綁定成功",
                    title="bind_success",
                    web_url=os.getenv("WEB_APP_URL"),
                )
            else:
                return CommandResult.fail("綁定碼無效或已過期")

        except Exception as e:
            logger.error(f"Binding failed: {e}")
            return CommandResult.fail("綁定失敗，請稍後再試")
