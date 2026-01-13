"""
Start Command Module.

Handles the /start command - shows welcome message.
"""

from src.channels.commands.base import BaseCommand, CommandResult


class StartCommand(BaseCommand):
    """Welcome command - shows introduction with Web App button."""

    name = "start"
    description = "Start using the bot"
    usage = "/start"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: dict | None = None,
    ) -> CommandResult:
        """
        Execute /start command.

        Shows welcome message with Web App login button.

        Args:
            user_id: Platform user ID (chat_id)
            args: Command arguments (unused)
            context: Optional context

        Returns:
            Welcome message
        """
        return CommandResult.ok(
            message="歡迎使用 591 租屋小幫手",
            title="welcome",
        )
