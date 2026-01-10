"""
Telegram Formatter Module.

Formats messages for Telegram using HTML markup.
"""

from typing import Any, Optional

from src.channels.base import BaseFormatter
from src.channels.commands.base import CommandResult
from src.modules.objects import RentalObject


class TelegramFormatter(BaseFormatter):
    """Formats messages for Telegram platform."""

    def format_command_result(self, result: CommandResult) -> str:
        """
        Format command result for Telegram.

        Args:
            result: CommandResult from command execution

        Returns:
            HTML formatted message for Telegram
        """
        title = result.title or ""

        # Route to specific formatter based on title
        formatters = {
            "welcome": self._format_welcome,
            "help": self._format_help,
            "bind_success": self._format_bind_success,
            "status_bound": self._format_status_bound,
            "status_unbound": self._format_status_unbound,
            "list_subscriptions": self._format_list_subscriptions,
            "list_empty": self._format_list_empty,
        }

        formatter = formatters.get(title)
        if formatter:
            return formatter(result)

        # Default: error or simple message
        if not result.success:
            return f"❌ {self._escape_html(result.error or 'Unknown error')}"

        return self._escape_html(result.message)

    def _format_welcome(self, result: CommandResult) -> str:
        """Format welcome message."""
        commands = result.data.get("commands", [])

        lines = [
            "👋 歡迎使用 591 租屋通知機器人！",
            "",
            "📋 可用指令：",
        ]

        for cmd in commands:
            name = cmd["name"]
            usage = f" {cmd.get('usage', '')}" if cmd.get("usage") else ""
            # Don't add slash for Chinese command names
            prefix = "" if ord(name[0]) > 0x4E00 else "/"
            lines.append(f"{prefix}{name}{usage} - {cmd['desc']}")

        return "\n".join(lines)

    def _format_help(self, result: CommandResult) -> str:
        """Format help message."""
        steps = result.data.get("steps", [])
        commands = result.data.get("commands", [])

        lines = ["📖 使用說明", ""]

        for i, step in enumerate(steps, 1):
            emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"][i - 1] if i <= 5 else f"{i}."
            lines.append(f"{emoji} {step}")

        lines.extend(["", "📋 指令說明："])

        for cmd in commands:
            name = cmd["name"]
            usage = f" {cmd.get('usage', '')}" if cmd.get("usage") else ""
            # Don't add slash for Chinese command names
            prefix = "" if ord(name[0]) > 0x4E00 else "/"
            lines.append(f"{prefix}{name}{usage} - {cmd['desc']}")

        return "\n".join(lines)

    def _format_bind_success(self, result: CommandResult) -> str:
        """Format bind success message."""
        return "\n".join([
            "✅ 綁定成功！",
            "",
            "您現在可以接收租屋通知了。",
            "當有符合訂閱條件的新物件時，會自動推播到這裡。",
            "",
            "輸入 /status 查看綁定狀態",
            "輸入 /list 查看訂閱清單",
        ])

    def _format_status_bound(self, result: CommandResult) -> str:
        """Format bound status message."""
        service = result.data.get("service", "")
        service_id = result.data.get("service_id", "")
        enabled = result.data.get("enabled", False)
        created_at = result.data.get("created_at", "")

        status_icon = "✅" if enabled else "⏸️"
        status_text = "啟用中" if enabled else "已暫停"

        # Format date
        date_str = ""
        if created_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created_at)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = created_at[:16] if len(created_at) > 16 else created_at

        lines = [
            "📊 綁定狀態",
            "",
            f"🔗 服務: {service.title()}",
            f"📱 ID: <code>{service_id}</code>",
            f"{status_icon} 狀態: {status_text}",
        ]

        if date_str:
            lines.append(f"📅 綁定時間: {date_str}")

        lines.extend(["", "輸入 /list 查看訂閱清單"])

        return "\n".join(lines)

    def _format_status_unbound(self, result: CommandResult) -> str:
        """Format unbound status message."""
        return "\n".join([
            "📊 綁定狀態",
            "",
            "❌ 尚未綁定帳號",
            "",
            "請先在網站取得綁定碼，然後使用：",
            "/bind <code>",
        ])

    def _format_list_subscriptions(self, result: CommandResult) -> str:
        """Format subscription list message."""
        subscriptions = result.data.get("subscriptions", [])
        count = result.data.get("count", 0)

        lines = ["📋 訂閱清單", ""]

        kind_names = {1: "整層", 2: "獨套", 3: "分套", 4: "雅房"}

        for idx, sub in enumerate(subscriptions, 1):
            status = "✅" if sub.get("enabled") else "⏸️"
            name = sub.get("name", f"訂閱 {sub['id']}")

            # Build filter description
            filters = []
            price_min = sub.get("price_min")
            price_max = sub.get("price_max")
            if price_min or price_max:
                min_str = f"{price_min:,}" if price_min else "0"
                max_str = f"{price_max:,}" if price_max else "∞"
                filters.append(f"💰{min_str}-{max_str}")

            kind = sub.get("kind")
            if kind:
                if isinstance(kind, list):
                    kind_str = "/".join(kind_names.get(k, "") for k in kind if k in kind_names)
                else:
                    kind_str = kind_names.get(kind, "")
                if kind_str:
                    filters.append(kind_str)

            lines.append(f"{status} {idx}. {name}")
            if filters:
                lines.append(f"   {' '.join(filters)}")

        lines.append(f"\n共 {count} 個訂閱")

        return "\n".join(lines)

    def _format_list_empty(self, result: CommandResult) -> str:
        """Format empty list message."""
        return "\n".join([
            "📋 訂閱清單",
            "",
            "目前沒有任何訂閱",
            "",
            "請至網站建立訂閱條件",
        ])

    def format_listing(self, listing: Any) -> str:
        """
        Format a rental listing for Telegram notification.

        Args:
            listing: RentalObject to format

        Returns:
            HTML formatted listing message
        """
        if not isinstance(listing, RentalObject):
            return str(listing)

        # Price formatting
        price_display = f"${listing.price}/月" if listing.price else "價格洽詢"

        lines = [
            f"🏠 <b>{self._escape_html(listing.title)}</b>",
            "",
            f"💰 <b>{price_display}</b>",
        ]

        if listing.kind_name:
            lines.append(f"🏷️ {listing.kind_name}")

        if listing.area:
            lines.append(f"📐 {listing.area} 坪")

        if listing.layout_str:
            lines.append(f"🛏️ {listing.layout_str}")

        if listing.floor_name:
            lines.append(f"🏢 {listing.floor_name}")

        if listing.address:
            lines.append(f"📍 {self._escape_html(listing.address)}")

        if listing.surrounding and listing.surrounding.desc:
            distance = listing.surrounding.distance or ""
            lines.append(f"🚇 {listing.surrounding.desc} {distance}")

        if listing.tags:
            tags_str = " ".join(f"#{tag}" for tag in listing.tags[:5])
            lines.append(f"\n{tags_str}")

        if listing.url:
            lines.append(f'\n🔗 <a href="{listing.url}">查看詳情</a>')

        return "\n".join(lines)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )


# Singleton instance
_formatter: Optional[TelegramFormatter] = None


def get_telegram_formatter() -> TelegramFormatter:
    """Get TelegramFormatter singleton."""
    global _formatter
    if _formatter is None:
        _formatter = TelegramFormatter()
    return _formatter
