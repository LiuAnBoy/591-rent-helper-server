"""
Telegram Formatter Module.

Formats messages for Telegram using HTML markup.
"""

from typing import Any

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
            "manage": self._format_manage,
            "command_list": self._format_command_list,
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
        lines = [
            "👋 歡迎使用 591 租屋小幫手！",
            "",
            "📋 接收通知技巧：",
            "1️⃣ 點擊下方按鈕進入管理頁面",
            "2️⃣ 設定篩選條件",
            "完成以上步驟就可以等待收到物件通知囉 🎉",
            "",
            "💡 輸入 暫停通知 或 開始通知 控制通知開關",
            "💡 輸入 幫助 或 指令 查看更多資訊",
        ]

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
        web_url = result.data.get("web_url")

        lines = [
            "✅ 綁定成功！",
            "",
            "您現在可以接收租屋通知了。",
            "當有符合訂閱條件的新物件時，會自動推播到這裡。",
            "",
            "輸入 清單 查看訂閱清單",
        ]

        if web_url:
            lines.extend(
                [
                    "",
                    f'🔗 <a href="{web_url}">前往網站設定篩選條件</a>',
                ]
            )

        return "\n".join(lines)

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
        return "\n".join(
            [
                "📊 綁定狀態",
                "",
                "❌ 尚未綁定帳號",
                "",
                "請先在網站取得綁定碼，然後使用：",
                "/bind <code>",
            ]
        )

    def _format_list_subscriptions(self, result: CommandResult) -> str:
        """Format subscription list message."""
        subscriptions = result.data.get("subscriptions", [])
        count = result.data.get("count", 0)

        lines = ["📋 訂閱清單", ""]

        kind_names = {1: "整層", 2: "獨套", 3: "分套", 4: "雅房"}

        for idx, sub in enumerate(subscriptions, 1):
            status = "▶️" if sub.get("enabled") else "⏸️"
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
                    kind_str = "/".join(
                        kind_names.get(k, "") for k in kind if k in kind_names
                    )
                else:
                    kind_str = kind_names.get(kind, "")
                if kind_str:
                    filters.append(kind_str)

            lines.append(f"{status} {idx}. {name}")
            if filters:
                lines.append(f"   {' '.join(filters)}")

        lines.append(f"\n共 {count} 個訂閱")
        lines.append("")
        lines.append("▶️ = 啟用中")
        lines.append("⏸️ = 已暫停")

        return "\n".join(lines)

    def _format_list_empty(self, result: CommandResult) -> str:
        """Format empty list message."""
        return "\n".join(
            [
                "📋 訂閱清單",
                "",
                "目前沒有任何訂閱",
            ]
        )

    def _format_manage(self, result: CommandResult) -> str:
        """Format manage message."""
        return "請點擊下方按鈕開啟管理頁面"

    def _format_command_list(self, result: CommandResult) -> str:
        """Format command list message."""
        commands = result.data.get("commands", [])

        lines = ["📋 可用指令：", ""]

        for cmd in commands:
            name = cmd["name"]
            lines.append(f"{name} - {cmd['desc']}")

        return "\n".join(lines)

    def format_object(self, obj: Any) -> str:
        """
        Format a rental object for Telegram notification.

        Args:
            obj: RentalObject or dict (DBReadyData) to format

        Returns:
            HTML formatted object message
        """
        # Support both RentalObject and dict (DBReadyData)
        if isinstance(obj, dict):
            # Dict access for DBReadyData
            title = obj.get("title", "")
            price = obj.get("price", "")
            kind_name = obj.get("kind_name", "")
            area = obj.get("area")
            layout_str = obj.get("layout_str", "")
            floor_str = obj.get("floor_str", "")
            address = obj.get("address", "")
            surrounding_desc = obj.get("surrounding_desc", "")
            surrounding_distance = obj.get("surrounding_distance")
            tags = obj.get("tags", [])
            url = obj.get("url", "")
        elif isinstance(obj, RentalObject):
            # Attribute access for RentalObject
            title = obj.title
            price = obj.price
            kind_name = obj.kind_name
            area = obj.area
            layout_str = obj.layout_str
            floor_str = obj.floor_name  # RentalObject uses floor_name
            address = obj.address
            surrounding_desc = obj.surrounding.desc if obj.surrounding else ""
            surrounding_distance = obj.surrounding.distance if obj.surrounding else None
            tags = obj.tags
            url = obj.url
        else:
            return str(obj)

        # Price formatting
        if isinstance(price, int):
            price_display = f"${price:,}/月" if price else "價格洽詢"
        else:
            price_display = f"${price}/月" if price else "價格洽詢"

        lines = [
            f"🏠 <b>{self._escape_html(title)}</b>",
            "",
            f"💰 <b>{price_display}</b>",
        ]

        if kind_name:
            lines.append(f"🏷️ {kind_name}")

        if area:
            lines.append(f"📐 {area} 坪")

        if layout_str:
            lines.append(f"🛏️ {layout_str}")

        if floor_str:
            lines.append(f"🏢 {floor_str}")

        if address:
            lines.append(f"📍 {self._escape_html(address)}")

        if surrounding_desc:
            distance_str = (
                f" {surrounding_distance}公尺" if surrounding_distance else ""
            )
            lines.append(f"🚇 {surrounding_desc}{distance_str}")

        if tags:
            tags_str = " ".join(f"#{tag}" for tag in tags)
            lines.append(f"\n{tags_str}")

        if url:
            lines.append(f'\n🔗 <a href="{url}">查看詳情</a>')

        return "\n".join(lines)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Singleton instance
_formatter: TelegramFormatter | None = None


def get_telegram_formatter() -> TelegramFormatter:
    """Get TelegramFormatter singleton."""
    global _formatter
    if _formatter is None:
        _formatter = TelegramFormatter()
    return _formatter
