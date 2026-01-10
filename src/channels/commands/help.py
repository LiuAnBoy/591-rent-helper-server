"""
Help Command Module.

Handles the /help command - shows usage instructions.
"""

from typing import Optional

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
        context: Optional[dict] = None,
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
            "在網站上註冊 / 登入帳號",
            "點擊「綁定 Telegram」按鈕完成綁定",
            "在網站建立訂閱條件",
            "當有符合條件的新物件時，會自動推播通知！",
        ]

        commands = [
            {"name": "清單", "desc": "查看訂閱清單"},
            {"name": "管理", "desc": "開啟管理頁面"},
        ]

        return CommandResult.ok(
            message="使用說明",
            title="help",
            steps=steps,
            commands=commands,
        )
