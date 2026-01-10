"""
Start Command Module.

Handles the /start command - shows welcome message.
"""

from typing import Optional

from src.channels.commands.base import BaseCommand, CommandResult


class StartCommand(BaseCommand):
    """Welcome command - shows introduction and available commands."""

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

        Args:
            user_id: Platform user ID
            args: Command arguments (unused)
            context: Optional context

        Returns:
            Welcome message with user ID and available commands
        """
        steps = [
            "請先前往網頁註冊",
            "登入並綁定 Telegram",
            "回到這裡輸入 /bind [綁定碼]",
            "回到網頁設定篩選條件",
        ]

        return CommandResult.ok(
            message="收取通知步驟",
            title="welcome",
            user_id=user_id,
            steps=steps,
        )
