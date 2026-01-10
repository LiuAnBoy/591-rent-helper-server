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
            {"name": "幫助", "desc": "查看幫助"},
            {"name": "bind", "desc": "綁定帳號", "usage": "<code>"},
            {"name": "清單", "desc": "查看訂閱清單"},
        ]

        return CommandResult.ok(
            message="Welcome to 591 Rental Notification Bot!",
            title="welcome",
            user_id=user_id,
            commands=commands,
        )
