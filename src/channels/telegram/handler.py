"""
Telegram Handler Module.

Routes incoming Telegram updates to appropriate command handlers.
"""

from typing import Optional

import os

from asyncpg import Pool
from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode

from src.channels.telegram.bot import TelegramBot
from src.channels.telegram.formatter import TelegramFormatter, get_telegram_formatter
from src.channels.commands import COMMANDS, BaseCommand, parse_command


class TelegramHandler:
    """Handler for routing Telegram updates to commands."""

    # Service identifier for this channel
    SERVICE_NAME = "telegram"

    def __init__(self, bot: TelegramBot, pool: Optional[Pool] = None):
        """
        Initialize handler.

        Args:
            bot: TelegramBot instance
            pool: Database connection pool
        """
        self._bot = bot
        self._pool = pool
        self._commands: dict[str, BaseCommand] = {}
        self._formatter: TelegramFormatter = get_telegram_formatter()

        # Register all commands
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all available commands."""
        for name, command_class in COMMANDS.items():
            self._commands[name] = command_class(pool=self._pool)
            logger.debug(f"Registered command: {name}")

        logger.info(f"Registered {len(self._commands)} commands")

    async def handle_update(self, update: Update) -> bool:
        """
        Handle an incoming Telegram update.

        Args:
            update: Telegram Update object

        Returns:
            True if handled successfully
        """
        if not update.message:
            logger.debug("Update has no message, skipping")
            return True

        chat_id = update.message.chat_id
        text = update.message.text or ""
        user = update.message.from_user

        username = user.username or str(user.id) if user else "unknown"
        logger.info(f"Received message from {username}: {text}")

        # Try to parse as command (supports /cmd, cmd, 中文指令)
        parsed = parse_command(text)

        if parsed:
            command_name, args = parsed
            return await self._execute_command(chat_id, command_name, args)
        else:
            return await self._handle_text(chat_id, text)

    async def _execute_command(self, chat_id: int, command_name: str, args: str) -> bool:
        """
        Execute a command.

        Args:
            chat_id: Telegram chat ID
            command_name: Command name (without /)
            args: Command arguments

        Returns:
            True if handled successfully
        """
        command = self._commands.get(command_name)

        if command:
            try:
                # Build context with service info
                context = {"service": self.SERVICE_NAME}

                # Execute command
                result = await command.execute(str(chat_id), args, context)

                # Format result using Telegram formatter
                response = self._formatter.format_command_result(result)

                # Add inline keyboard for specific commands
                reply_markup = self._get_reply_markup(result.title)

                await self._bot.send_message(
                    chat_id,
                    response,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
                return True
            except Exception as e:
                logger.error(f"Command {command_name} error: {e}")
                await self._bot.send_message(
                    chat_id, "❌ 指令執行失敗，請稍後再試"
                )
                return False
        else:
            await self._bot.send_message(
                chat_id,
                "❓ 未知指令\n\n輸入 /help 查看可用指令",
            )
            return True

    def _get_reply_markup(self, title: str) -> Optional[InlineKeyboardMarkup]:
        """
        Get inline keyboard markup for specific command results.

        Args:
            title: Command result title

        Returns:
            InlineKeyboardMarkup or None
        """
        web_app_url = os.getenv("WEB_APP_URL", "")
        if not web_app_url:
            return None

        # Commands that need a button
        if title == "welcome":
            keyboard = [[
                InlineKeyboardButton(
                    "📱 開啟管理頁面",
                    web_app=WebAppInfo(url=web_app_url)
                )
            ]]
            return InlineKeyboardMarkup(keyboard)

        if title in ("list_subscriptions", "list_empty", "manage"):
            keyboard = [[
                InlineKeyboardButton(
                    "📱 開啟管理頁面",
                    web_app=WebAppInfo(url=web_app_url)
                )
            ]]
            return InlineKeyboardMarkup(keyboard)

        return None

    async def _handle_text(self, chat_id: int, text: str) -> bool:
        """
        Handle a non-command text message.

        Args:
            chat_id: Telegram chat ID
            text: Message text

        Returns:
            True if handled successfully
        """
        await self._bot.send_message(
            chat_id,
            "💡 請使用指令與我互動\n\n輸入 幫助 查看可用指令",
        )
        return True
