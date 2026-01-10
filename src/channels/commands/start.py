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
        commands = [
            {"name": "start", "desc": "開始使用"},
            {"name": "bind", "desc": "綁定帳號", "usage": "[綁定碼]"},
            {"name": "清單", "desc": "訂閱清單"},
            {"name": "幫助", "desc": "顯示說明"},
            {"name": "管理", "desc": "管理頁面"},
        ]

        return CommandResult.ok(
            message="Welcome to 591 Rental Notification Bot!",
            title="welcome",
            user_id=user_id,
            commands=commands,
        )
