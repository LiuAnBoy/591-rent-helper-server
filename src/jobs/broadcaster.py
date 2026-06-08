"""
Notification Broadcaster Module.

Sends notifications to subscribed users via their bound channels.
"""

import asyncio
from datetime import datetime
from enum import Enum

from loguru import logger
from telegram.constants import ParseMode

from config.settings import get_settings
from src.channels.telegram import TelegramBot, get_telegram_formatter
from src.modules.objects import RentalObject

broadcast_log = logger.bind(module="Broadcast")

# Region code to name mapping
REGION_NAMES = {
    1: "台北市",
    3: "新北市",
}


class ErrorType(Enum):
    """Crawler error types for admin notifications."""

    LIST_FETCH_FAILED = ("LIST_FETCH_FAILED", "列表頁抓取失敗", "🔴")
    DETAIL_FETCH_FAILED = ("DETAIL_FETCH_FAILED", "詳情頁抓取失敗", "🟡")
    FIELD_MISSING = ("FIELD_MISSING", "物件欄位解析失敗", "🟡")
    DB_ERROR = ("DB_ERROR", "資料庫錯誤", "🔴")
    REDIS_ERROR = ("REDIS_ERROR", "Redis 錯誤", "🔴")
    BROADCAST_ERROR = ("BROADCAST_ERROR", "推播發送失敗", "🟡")
    UNKNOWN_ERROR = ("UNKNOWN_ERROR", "未知錯誤", "🔴")

    def __init__(self, code: str, description: str, severity: str):
        self.code = code
        self.description = description
        self.severity = severity


class Broadcaster:
    """Broadcasts notifications to users via their bound channels."""

    # Retry policy: try a notification up to 3 times, 60s apart, before giving
    # up (and reporting it as a failure for the admin alert + notification log).
    MAX_SEND_ATTEMPTS = 3
    RETRY_INTERVAL_SECONDS = 60

    def __init__(self, bot: TelegramBot | None = None):
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
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    async def send_telegram_notification(
        self,
        chat_id: str,
        obj: RentalObject | dict,
        subscription_name: str | None = None,
    ) -> dict:
        """
        Send notification to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            obj: RentalObject or dict (DBReadyData) to send
            subscription_name: Optional subscription name for context

        Returns:
            Dict with result: {"success": bool, "error": str | None}
        """
        if not self.bot.is_configured:
            broadcast_log.warning(
                "Telegram bot not configured, cannot send notification"
            )
            return {"success": False, "error": "Bot not configured"}

        try:
            # Use formatter to create message (supports both RentalObject and dict)
            message = self._telegram_formatter.format_object(obj)

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

            # Get object ID for logging
            obj_id = obj["id"] if isinstance(obj, dict) else obj.id
            broadcast_log.info(
                f"Sent Telegram notification to {chat_id} for object {obj_id}"
            )
            return {"success": True, "error": None}

        except Exception as e:
            broadcast_log.error(
                f"Failed to send Telegram notification to {chat_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    async def send_notification(
        self,
        provider: str,
        provider_id: str,
        obj: RentalObject | dict,
        subscription_name: str | None = None,
    ) -> dict:
        """
        Send notification via the appropriate channel.

        Args:
            provider: Provider name (telegram, line, etc.)
            provider_id: Provider-specific user ID
            obj: RentalObject or dict (DBReadyData) to send
            subscription_name: Optional subscription name for context

        Returns:
            Dict with result: {"success": bool, "error": str | None}
        """
        if provider == "telegram":
            return await self.send_telegram_notification(
                chat_id=provider_id,
                obj=obj,
                subscription_name=subscription_name,
            )
        # Future: Add LINE, Discord, etc.
        # elif provider == "line":
        #     return await self.send_line_notification(...)
        else:
            broadcast_log.warning(f"Unknown provider: {provider}")
            return {"success": False, "error": f"Unknown provider: {provider}"}

    async def notify_admin(
        self,
        error_type: ErrorType,
        region: int | None = None,
        details: str | None = None,
    ) -> bool:
        """
        Send error notification to admin.

        Args:
            error_type: Type of error
            region: Region code (optional)
            details: Additional error details (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        admin_id = self.settings.admin_id
        if not admin_id:
            broadcast_log.debug("No admin_id configured, skipping error notification")
            return False

        if not self.bot.is_configured:
            broadcast_log.warning(
                "Telegram bot not configured, cannot send admin notification"
            )
            return False

        # Build message
        region_name = REGION_NAMES.get(region, f"Region {region}") if region else "N/A"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message = (
            f"⚠️ <b>爬蟲警告</b>\n\n"
            f"類型: <code>{error_type.code}</code>\n"
            f"說明: {error_type.description} {error_type.severity}\n"
            f"區域: {region_name}\n"
            f"時間: {timestamp}"
        )

        if details:
            message += f"\n\n詳情:\n<pre>{self._escape_html(details)}</pre>"

        try:
            await self.bot.bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode=ParseMode.HTML,
            )
            broadcast_log.info(f"Sent admin notification: {error_type.code}")
            return True
        except Exception as e:
            broadcast_log.error(f"Failed to send admin notification: {e}")
            return False

    async def _send_with_retry(
        self,
        semaphore: "asyncio.Semaphore",
        provider: str,
        provider_id: str,
        obj: RentalObject | dict,
        subscription_name: str | None,
    ) -> dict:
        """
        Send one notification, retrying up to MAX_SEND_ATTEMPTS times.

        Sleeps RETRY_INTERVAL_SECONDS between attempts and releases the
        concurrency slot during the wait so other notifications are not blocked.

        Returns:
            The last send result ({"success": bool, "error": str | None}).
        """
        result = {"success": False, "error": "not attempted"}
        for attempt in range(self.MAX_SEND_ATTEMPTS):
            async with semaphore:
                result = await self.send_notification(
                    provider=provider,
                    provider_id=provider_id,
                    obj=obj,
                    subscription_name=subscription_name,
                )
            if result.get("success"):
                return result

            if attempt < self.MAX_SEND_ATTEMPTS - 1:
                broadcast_log.warning(
                    f"Notify {provider_id} failed "
                    f"(attempt {attempt + 1}/{self.MAX_SEND_ATTEMPTS}), "
                    f"retrying in {self.RETRY_INTERVAL_SECONDS}s: {result.get('error')}"
                )
                await asyncio.sleep(self.RETRY_INTERVAL_SECONDS)

        return result

    async def broadcast(
        self,
        matches: list[tuple[RentalObject, list[dict]]],
    ) -> dict:
        """
        Broadcast notifications for matched objects (concurrent).

        Args:
            matches: List of (obj, subscriptions) tuples from Checker

        Returns:
            Dict with broadcast results:
            - total: Total notifications attempted
            - success: Number of successful sends
            - failed: Number of failed sends
            - details: List of per-notification results for DB logging
            - failures: List of failure details for admin notification
        """
        # Build list of notification tasks
        tasks = []
        task_meta = []  # Track metadata for each task
        # Dedupe so the same object is not sent twice to the same recipient
        # when a user has multiple overlapping subscriptions on one binding.
        sent_targets: set[tuple] = set()

        for obj, subscriptions in matches:
            obj_id = obj["id"] if isinstance(obj, dict) else obj.id
            for sub in subscriptions:
                provider = sub.get("service")
                provider_id = sub.get("service_id")
                sub_name = sub.get("name", "")
                sub_id = sub.get("id")

                if not provider or not provider_id:
                    broadcast_log.debug(
                        f"Skipping subscription {sub_id} - no binding"
                    )
                    continue

                target = (provider, provider_id, obj_id)
                if target in sent_targets:
                    broadcast_log.debug(
                        f"Skipping duplicate notification to {provider_id} "
                        f"for object {obj_id}"
                    )
                    continue
                sent_targets.add(target)

                tasks.append(
                    {
                        "provider": provider,
                        "provider_id": provider_id,
                        "obj": obj,
                        "subscription_name": sub_name,
                    }
                )
                task_meta.append({
                    "object_id": obj_id,
                    "subscription_id": sub_id,
                    "provider": provider,
                    "provider_id": provider_id,
                })

        if not tasks:
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "details": [],
                "failures": [],
            }

        # Limit concurrent notifications (Telegram rate limit ~30/sec, use 10 to be safe)
        MAX_CONCURRENT = 10
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        # Run notifications (each with bounded retry) under the concurrency limit
        results = await asyncio.gather(
            *[self._send_with_retry(semaphore, **plan) for plan in tasks],
            return_exceptions=True,
        )

        # Process results
        success = 0
        failed = 0
        details = []
        failures = []

        for meta, result in zip(task_meta, results, strict=True):
            if isinstance(result, Exception):
                error_msg = str(result)
                broadcast_log.error(
                    f"Notification failed for {meta['provider_id']}: {error_msg}"
                )
                failed += 1
                details.append({**meta, "status": "failed", "error_message": error_msg})
                failures.append({
                    "provider_id": meta["provider_id"],
                    "error": error_msg,
                })
            elif result.get("success"):
                success += 1
                details.append({**meta, "status": "success", "error_message": None})
            else:
                error_msg = result.get("error", "Unknown error")
                failed += 1
                details.append({**meta, "status": "failed", "error_message": error_msg})
                failures.append({
                    "provider_id": meta["provider_id"],
                    "error": error_msg,
                })

        total = len(tasks)
        broadcast_log.info(
            f"Broadcast complete: {success}/{total} sent, {failed} failed"
        )

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "details": details,
            "failures": failures,
        }


# Singleton instance
_broadcaster: Broadcaster | None = None


def get_broadcaster() -> Broadcaster:
    """Get Broadcaster singleton."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = Broadcaster()
    return _broadcaster


async def main():
    """Test the broadcaster."""
    from src.channels.telegram import get_telegram_formatter

    # Create a test object
    test_object = RentalObject(
        id=12345678,
        kind=2,
        kind_name="獨立套房",
        title="測試物件 - 近捷運優質套房",
        url="https://rent.591.com.tw/home/12345678",
        price="15,000",
        price_unit="元/月",
        floor_name="3F/5F",
        area=10.5,
        layoutStr="1房1廳1衛",
        address="台北市大安區忠孝東路",
        regionid=1,
        sectionid=5,
        tags=["近捷運", "新上架", "可養寵物"],
    )

    formatter = get_telegram_formatter()
    message = formatter.format_object(test_object)
    print("Formatted message:")
    print("-" * 40)
    print(message)
    print("-" * 40)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
