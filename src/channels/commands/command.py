"""
Command List Module.

Handles the command list - shows available commands.
"""

from src.channels.commands.base import BaseCommand, CommandResult


class CommandListCommand(BaseCommand):
    """Command list - shows available commands."""

    name = "指令"
    description = "Show commands"
    usage = ""

    async def execute(
        self,
        user_id: str,
        args: str,
        context: dict | None = None,
    ) -> CommandResult:
        """
        Execute command list.

        Args:
            user_id: Platform user ID
            args: Command arguments (unused)
            context: Optional context

        Returns:
            List of available commands
        """
        commands = [
            {"name": "清單", "desc": "訂閱清單"},
            {"name": "幫助", "desc": "顯示說明"},
            {"name": "開始通知", "desc": "恢復接收通知"},
            {"name": "暫停通知", "desc": "暫停接收通知"},
        ]

        return CommandResult.ok(
            message="可用指令",
            title="command_list",
            commands=commands,
        )
