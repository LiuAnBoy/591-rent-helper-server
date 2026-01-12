"""
Notification Broadcaster Module.

Sends notifications to subscribed users via their bound channels.
"""

import asyncio
from typing import Optional

from loguru import logger
from telegram.constants import ParseMode

from config.settings import get_settings
from src.channels.telegram import TelegramBot, get_telegram_formatter
from src.modules.objects import RentalObject

broadcast_log = logger.bind(module="Broadcast")


class Broadcaster:
    """Broadcasts notifications to users via their bound channels."""

    def __init__(self, bot: Optional[TelegramBot] = None):
        """
        Initialize Broadcaster.

        Args:
            bot: TelegramBot instance (uses singleton if not provided)
        """
        self.settings = get_settings().telegram
        self._bot = bot
        self._telegram_formatter = get_telegram_formatter()

    @property
    def bot(self) -> TelegramBot:
        """Get TelegramBot instance."""
        if not self._bot:
            self._bot = TelegramBot.init(self.settings.bot_token)
        return self._bot

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    async def send_telegram_notification(
        self,
        chat_id: str,
        listing: RentalObject,
        subscription_name: Optional[str] = None,
    ) -> bool:
        """
        Send notification to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            listing: RentalObject to send
            subscription_name: Optional subscription name for context

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.bot.is_configured:
            broadcast_log.warning("Telegram bot not configured, cannot send notification")
            return False

        try:
            # Use formatter to create message
            message = self._telegram_formatter.format_listing(listing)

            # Add subscription context if provided
            if subscription_name:
                message = f"📌 <i>訂閱: {self._escape_html(subscription_name)}</i>\n\n{message}"

            # Send text message
            await self.bot.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )

            broadcast_log.info(f"Sent Telegram notification to {chat_id} for object {listing.id}")
            return True

        except Exception as e:
            broadcast_log.error(f"Failed to send Telegram notification to {chat_id}: {e}")
            return False

    async def send_notification(
        self,
        service: str,
        service_id: str,
        listing: RentalObject,
        subscription_name: Optional[str] = None,
    ) -> bool:
        """
        Send notification via the appropriate channel.

        Args:
            service: Service name (telegram, line, etc.)
            service_id: Service-specific user ID
            listing: RentalObject to send
            subscription_name: Optional subscription name for context

        Returns:
            True if sent successfully, False otherwise
        """
        if service == "telegram":
            return await self.send_telegram_notification(
                chat_id=service_id,
                listing=listing,
                subscription_name=subscription_name,
            )
        # Future: Add LINE, Discord, etc.
        # elif service == "line":
        #     return await self.send_line_notification(...)
        else:
            broadcast_log.warning(f"Unknown service: {service}")
            return False

    async def broadcast(
        self,
        matches: list[tuple[RentalObject, list[dict]]],
    ) -> dict:
        """
        Broadcast notifications for matched listings (concurrent).

        Args:
            matches: List of (listing, subscriptions) tuples from Checker

        Returns:
            Dict with broadcast results:
            - total: Total notifications attempted
            - success: Number of successful sends
            - failed: Number of failed sends
            - by_service: Breakdown by service
        """
        # Build list of notification tasks
        tasks = []
        task_info = []  # Track service for each task

        for listing, subscriptions in matches:
            for sub in subscriptions:
                service = sub.get("service")
                service_id = sub.get("service_id")
                sub_name = sub.get("name", "")

                if not service or not service_id:
                    broadcast_log.debug(f"Skipping subscription {sub.get('id')} - no binding")
                    continue

                task = self.send_notification(
                    service=service,
                    service_id=service_id,
                    listing=listing,
                    subscription_name=sub_name,
                )
                tasks.append(task)
                task_info.append(service)

        if not tasks:
            return {"total": 0, "success": 0, "failed": 0, "by_service": {}}

        # Run all notifications concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        success = 0
        failed = 0
        by_service: dict[str, dict] = {}

        for service, result in zip(task_info, results):
            if service not in by_service:
                by_service[service] = {"total": 0, "success": 0, "failed": 0}

            by_service[service]["total"] += 1

            if isinstance(result, Exception):
                broadcast_log.error(f"Notification failed: {result}")
                failed += 1
                by_service[service]["failed"] += 1
            elif result:
                success += 1
                by_service[service]["success"] += 1
            else:
                failed += 1
                by_service[service]["failed"] += 1

        total = len(tasks)
        broadcast_log.info(
            f"Broadcast complete: {success}/{total} sent, {failed} failed"
        )

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "by_service": by_service,
        }


# Singleton instance
_broadcaster: Optional[Broadcaster] = None


def get_broadcaster() -> Broadcaster:
    """Get Broadcaster singleton."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = Broadcaster()
    return _broadcaster


async def main():
    """Test the broadcaster."""
    from src.channels.telegram import get_telegram_formatter

    # Create a test listing
    test_listing = RentalObject(
        id=12345678,
        type=1,
        kind=2,
        kind_name="獨立套房",
        title="測試物件 - 近捷運優質套房",
        url="https://rent.591.com.tw/home/12345678",
        price="15,000",
        price_unit="元/月",
        floor_name="3F/5F",
        area=10.5,
        area_name="10.5坪",
        layout_str="1房1廳1衛",
        address="台北市大安區忠孝東路",
        region=1,
        section=5,
        tags=["近捷運", "新上架", "可養寵物"],
    )

    formatter = get_telegram_formatter()
    message = formatter.format_listing(test_listing)
    print("Formatted message:")
    print("-" * 40)
    print(message)
    print("-" * 40)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
