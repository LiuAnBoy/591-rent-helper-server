"""
Start Command Module.

Handles the /start command - shows welcome message or completes binding.
"""

from typing import Optional

from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult
from src.modules.bindings import BindingRepository


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

        If args contains BIND_<code>, complete the binding.
        Otherwise, show welcome message.

        Args:
            user_id: Platform user ID (chat_id)
            args: Command arguments (may contain bind code)
            context: Optional context

        Returns:
            Binding result or welcome message
        """
        # Check if this is a binding request via deep link
        if args.startswith("BIND_"):
            return await self._handle_binding(user_id, args[5:])

        # Normal welcome message
        steps = [
            "前往網頁註冊 / 登入",
            "點擊「綁定 Telegram」按鈕",
            "設定篩選條件，開始接收通知！",
        ]

        return CommandResult.ok(
            message="收取通知步驟",
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
                return CommandResult.ok(
                    message="綁定成功",
                    title="bind_success",
                )
            else:
                return CommandResult.fail("綁定碼無效或已過期")

        except Exception as e:
            logger.error(f"Binding failed: {e}")
            return CommandResult.fail("綁定失敗，請稍後再試")
