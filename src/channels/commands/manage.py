"""
Manage Command Module.

Handles the manage command - opens web management page.
"""

from typing import Optional

from src.channels.commands.base import BaseCommand, CommandResult


class ManageCommand(BaseCommand):
    """Manage command - shows link to web management page."""

    name = "管理"
    description = "Open management page"
    usage = ""

    async def execute(
        self,
        user_id: str,
        args: str,
        context: Optional[dict] = None,
    ) -> CommandResult:
        """
        Execute manage command.

        Args:
            user_id: Platform user ID
            args: Command arguments (unused)
            context: Optional context

        Returns:
            Message with management link button
        """
        return CommandResult.ok(
            message="請點擊下方按鈕開啟管理頁面",
            title="manage",
        )
