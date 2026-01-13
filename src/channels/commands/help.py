"""
Help Command Module.

Handles the /help command - shows usage instructions.
"""

from src.channels.commands.base import BaseCommand, CommandResult


class HelpCommand(BaseCommand):
    """Help command - shows usage instructions."""

    name = "help"
    description = "Show help"
    usage = "/help"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: dict | None = None,
    ) -> CommandResult:
        """
        Execute /help command.

        Args:
            user_id: Platform user ID
            args: Command arguments (unused)
            context: Optional context

        Returns:
            Help message with step-by-step instructions
        """
        steps = [
            "點擊下方按鈕進入管理頁面",
            "設定篩選條件",
            "當有符合條件的新物件時，會自動推播通知！",
        ]

        commands = [
            {"name": "清單", "desc": "查看訂閱清單"},
            {"name": "開始通知", "desc": "恢復接收通知"},
            {"name": "暫停通知", "desc": "暫停接收通知"},
        ]

        return CommandResult.ok(
            message="使用說明",
            title="help",
            steps=steps,
            commands=commands,
            show_webapp_button=True,
        )
