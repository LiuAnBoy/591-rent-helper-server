"""
Telegram Handler Module.

Routes incoming Telegram updates to appropriate command handlers.
"""

import os

from asyncpg import Pool
from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.constants import ParseMode

from src.channels.commands import COMMANDS, BaseCommand, parse_command
from src.channels.telegram.bot import TelegramBot
from src.channels.telegram.formatter import TelegramFormatter, get_telegram_formatter

tg_log = logger.bind(module="TelegramBot")


class TelegramHandler:
    """Handler for routing Telegram updates to commands."""

    # Service identifier for this channel
    SERVICE_NAME = "telegram"

    def __init__(self, bot: TelegramBot, pool: Pool | None = None):
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
            tg_log.debug(f"Registered command: {name}")

        tg_log.info(f"Registered {len(self._commands)} commands")

    async def handle_update(self, update: Update) -> bool:
        """
        Handle an incoming Telegram update.

        Args:
            update: Telegram Update object

        Returns:
            True if handled successfully
        """
        # Inline-button presses arrive as callback queries (no message).
        if update.callback_query:
            return await self._handle_callback(update.callback_query)

        if not update.message:
            tg_log.debug("Update has no message, skipping")
            return True

        chat_id = update.message.chat_id
        text = update.message.text or ""
        user = update.message.from_user

        username = user.username or str(user.id) if user else "unknown"
        tg_log.info(f"Received message from {username}: {text}")

        # Try to parse as command (supports /cmd, cmd, 中文指令)
        parsed = parse_command(text)

        if parsed:
            command_name, args = parsed
            return await self._execute_command(chat_id, command_name, args)
        else:
            return await self._handle_text(chat_id, text)

    async def _execute_command(
        self, chat_id: int, command_name: str, args: str
    ) -> bool:
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

                # Add inline keyboard for specific commands (notify menus need
                # the user's live state, so they are resolved asynchronously).
                if result.title in ("notify_pause_menu", "notify_resume_menu"):
                    reply_markup = await self._build_notify_menu(
                        chat_id, result.title
                    )
                else:
                    reply_markup = self._get_reply_markup(result.title)

                await self._bot.send_message(
                    chat_id,
                    response,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
                return True
            except Exception as e:
                tg_log.error(f"Command {command_name} error: {e}")
                await self._bot.send_message(chat_id, "❌ 指令執行失敗，請稍後再試")
                return False
        else:
            await self._bot.send_message(
                chat_id,
                "❓ 未知指令\n\n輸入 /help 查看可用指令",
            )
            return True

    def _get_reply_markup(self, title: str) -> InlineKeyboardMarkup | None:
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
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📱 開啟管理頁面", web_app=WebAppInfo(url=web_app_url)
                    )
                ]
            ]
            return InlineKeyboardMarkup(keyboard)

        if title in ("help", "list_subscriptions", "list_empty"):
            keyboard = [
                [
                    InlineKeyboardButton(
                        "📱 開啟管理頁面", web_app=WebAppInfo(url=web_app_url)
                    )
                ]
            ]
            return InlineKeyboardMarkup(keyboard)

        return None

    async def _build_notify_menu(
        self, chat_id: int, title: str
    ) -> InlineKeyboardMarkup | None:
        """Build the pause/resume menu from the user's live state.

        Args:
            chat_id: Telegram chat id (== provider_id for private chats).
            title: "notify_pause_menu" or "notify_resume_menu".

        Returns:
            The inline keyboard, or None if the user is not bound.
        """
        if not self._pool:
            return None

        from src.channels.telegram.menus import build_pause_menu, build_resume_menu
        from src.modules.providers import UserProviderRepository
        from src.modules.subscriptions import SubscriptionRepository

        prov_repo = UserProviderRepository(self._pool)
        provider = await prov_repo.find_by_provider(
            provider=self.SERVICE_NAME, provider_id=str(chat_id)
        )
        if not provider:
            return None

        sub_repo = SubscriptionRepository(self._pool)
        subs = await sub_repo.get_by_user(provider.user_id)
        web_app_url = os.getenv("WEB_APP_URL", "")

        if title == "notify_pause_menu":
            return build_pause_menu(provider.notify_enabled, subs, web_app_url)
        return build_resume_menu(provider.notify_enabled, subs, web_app_url)

    async def _handle_callback(self, cq) -> bool:
        """Route a ``notif:*`` callback: verify ownership, mutate, toast, refresh.

        Args:
            cq: Telegram CallbackQuery.

        Returns:
            True (always handled).
        """
        from src.channels.commands.notify import apply_user_notify
        from src.modules.providers import UserProviderRepository
        from src.modules.subscriptions import SubscriptionRepository
        from src.modules.subscriptions.service import set_enabled

        data = cq.data or ""
        chat_id = cq.message.chat_id if cq.message else None
        from_id = str(cq.from_user.id)

        if not data.startswith("notif:") or not self._pool:
            await self._bot.answer_callback(cq.id)
            return True

        prov_repo = UserProviderRepository(self._pool)
        provider = await prov_repo.find_by_provider(
            provider=self.SERVICE_NAME, provider_id=from_id
        )
        if not provider:
            await self._bot.answer_callback(cq.id, "尚未綁定帳號")
            return True

        sub_repo = SubscriptionRepository(self._pool)
        # callback_data is client-supplied; never assume its shape.
        parts = data.split(":")
        action = parts[1] if len(parts) >= 2 else ""
        toast = ""

        if action == "pause_user":
            await apply_user_notify(self._pool, self.SERVICE_NAME, from_id, False)
            toast = "已暫停使用者通知"
        elif action == "resume_user":
            res = await apply_user_notify(self._pool, self.SERVICE_NAME, from_id, True)
            toast = (
                "已開啟使用者通知"
                if res["has_enabled_subs"]
                else "已開啟使用者通知，但你目前沒有任何啟用中的訂閱，請至少啟用一個訂閱"
            )
        elif action in ("disable_sub", "enable_sub"):
            if len(parts) < 3 or not parts[2].isdigit():
                await self._bot.answer_callback(cq.id, "無效操作")
                return True
            # Hierarchy guard: can't modify a subscription while user-level
            # notify is off — turn that on first.
            if not provider.notify_enabled:
                await self._bot.answer_callback(cq.id, "請先開啟使用者通知")
                return True
            sub_id = int(parts[2])
            existing = await sub_repo.get_by_id(sub_id)
            # R1: never trust the id in callback_data — verify ownership server-side.
            if not existing or existing["user_id"] != provider.user_id:
                await self._bot.answer_callback(cq.id, "無權限")
                return True

            want = action == "enable_sub"
            if existing["enabled"] == want:
                toast = "狀態未變更"
            else:
                await set_enabled(sub_repo, existing, want)
                toast = "已啟用，有新物件會立即通知你" if want else "已停用此訂閱"
        else:
            await self._bot.answer_callback(cq.id)
            return True

        await self._bot.answer_callback(cq.id, toast)
        await self._refresh_menu_after(chat_id, cq.message, action)
        return True

    async def _refresh_menu_after(self, chat_id, message, action: str) -> None:
        """Rebuild and edit the menu after an action; resend on edit failure."""
        if chat_id is None or message is None:
            return
        if action in ("pause_user", "disable_sub"):
            title, text = "notify_pause_menu", "選擇要暫停的項目："
        else:
            title, text = "notify_resume_menu", "選擇要恢復的項目："

        markup = await self._build_notify_menu(chat_id, title)
        if markup is None:
            return
        ok = await self._bot.edit_reply_markup(chat_id, message.message_id, markup)
        if not ok:
            await self._bot.send_message(chat_id, text, reply_markup=markup)

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
