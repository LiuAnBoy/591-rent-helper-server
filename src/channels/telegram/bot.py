"""
Telegram Bot Module.

Manages Telegram bot instance and message sending.
"""

import os
from typing import Optional

from loguru import logger
from telegram import Bot
from telegram.constants import ParseMode


class TelegramBot:
    """Telegram bot wrapper for sending messages."""

    _instance: Optional["TelegramBot"] = None
    _bot: Optional[Bot] = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def init(cls, token: Optional[str] = None) -> "TelegramBot":
        """
        Initialize the bot instance.

        Args:
            token: Telegram bot token (uses env var if not provided)

        Returns:
            TelegramBot instance
        """
        instance = cls()
        if instance._bot is None:
            bot_token = token or os.getenv("TELEGRAM_BOT_TOKEN")
            if not bot_token:
                logger.warning("TELEGRAM_BOT_TOKEN not set")
                return instance

            instance._bot = Bot(token=bot_token)
            logger.info("Telegram bot initialized")

        return instance

    @classmethod
    def get_instance(cls) -> Optional["TelegramBot"]:
        """Get the singleton instance."""
        return cls._instance

    @property
    def bot(self) -> Optional[Bot]:
        """Get the underlying Bot instance."""
        return self._bot

    @property
    def is_configured(self) -> bool:
        """Check if bot is configured."""
        return self._bot is not None

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: str = ParseMode.MARKDOWN,
        disable_web_page_preview: bool = False,
    ) -> bool:
        """
        Send a text message.

        Args:
            chat_id: Target chat ID
            text: Message text
            parse_mode: Parse mode (Markdown, HTML)
            disable_web_page_preview: Disable link preview

        Returns:
            True if sent successfully
        """
        if not self._bot:
            logger.warning("Bot not configured, cannot send message")
            return False

        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False

    async def send_photo(
        self,
        chat_id: int | str,
        photo_url: str,
        caption: Optional[str] = None,
        parse_mode: str = ParseMode.MARKDOWN,
    ) -> bool:
        """
        Send a photo.

        Args:
            chat_id: Target chat ID
            photo_url: Photo URL
            caption: Photo caption
            parse_mode: Parse mode for caption

        Returns:
            True if sent successfully
        """
        if not self._bot:
            logger.warning("Bot not configured, cannot send photo")
            return False

        try:
            await self._bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=caption,
                parse_mode=parse_mode,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send photo to {chat_id}: {e}")
            return False

    async def send_listing_notification(
        self,
        chat_id: int | str,
        title: str,
        price: int,
        address: str,
        url: str,
        subscription_name: str,
        photo_url: Optional[str] = None,
    ) -> bool:
        """
        Send a rental listing notification.

        Args:
            chat_id: Target chat ID
            title: Listing title
            price: Monthly rent
            address: Address
            url: Listing URL
            subscription_name: Subscription name that matched
            photo_url: Optional photo URL

        Returns:
            True if sent successfully
        """
        text = (
            f"🏠 *新物件通知*\n\n"
            f"📋 {title}\n"
            f"💰 ${price:,}/月\n"
            f"📍 {address}\n\n"
            f"🔔 訂閱: {subscription_name}\n"
            f"🔗 [查看詳情]({url})"
        )

        if photo_url:
            return await self.send_photo(
                chat_id=chat_id,
                photo_url=photo_url,
                caption=text,
            )
        else:
            return await self.send_message(
                chat_id=chat_id,
                text=text,
            )
