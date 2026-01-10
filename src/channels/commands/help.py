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
            "在網站上註冊帳號",
            "從網站取得綁定碼",
            "使用 /bind <綁定碼> 連結帳號",
            "在網站建立訂閱條件",
            "當有符合條件的新物件時，會自動推播通知！",
        ]

        commands = [
            {"name": "bind", "desc": "輸入綁定碼連結帳號", "usage": "<code>"},
            {"name": "status", "desc": "查看綁定狀態"},
            {"name": "清單", "desc": "查看訂閱清單"},
        ]

        return CommandResult.ok(
            message="使用說明",
            title="help",
            steps=steps,
            commands=commands,
        )
