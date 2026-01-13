"""
Unit tests for src/channels/telegram/formatter.py
"""

import pytest

from src.channels.telegram.formatter import TelegramFormatter
from src.channels.commands.base import CommandResult

# Import fixtures
pytest_plugins = ["tests.fixtures.formatter"]


@pytest.fixture
def formatter():
    """Create a TelegramFormatter instance."""
    return TelegramFormatter()


# ============================================================
# format_object tests
# ============================================================


class TestFormatObject:
    """Tests for format_object method."""

    def test_format_full_object(self, formatter, sample_db_ready_object):
        """Full object should format correctly."""
        result = formatter.format_object(sample_db_ready_object)

        assert "台北市信義區精緻套房" in result
        assert "$15,000/月" in result
        assert "獨立套房" in result
        assert "10.5 坪" in result
        assert "2房1廳1衛" in result
        assert "3F/10F" in result
        assert "信義路五段" in result
        assert "信義安和站" in result
        assert "353公尺" in result
        assert "#近捷運" in result
        assert "#可養寵物" in result
        assert "https://rent.591.com.tw/12345678" in result

    def test_format_minimal_object(self, formatter, minimal_object):
        """Minimal object should format without errors."""
        result = formatter.format_object(minimal_object)

        assert "測試物件" in result
        assert "價格洽詢" in result  # price=0 shows this

    def test_format_escapes_html(self, formatter, object_with_special_chars):
        """HTML special characters should be escaped."""
        result = formatter.format_object(object_with_special_chars)

        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        assert "&amp;" in result

    def test_format_price_integer(self, formatter):
        """Integer price should be formatted with commas."""
        obj = {"title": "Test", "price": 12500, "url": "http://test"}
        result = formatter.format_object(obj)

        assert "$12,500/月" in result

    def test_format_price_zero(self, formatter):
        """Zero price should show '價格洽詢'."""
        obj = {"title": "Test", "price": 0, "url": "http://test"}
        result = formatter.format_object(obj)

        assert "價格洽詢" in result

    def test_format_no_surrounding(self, formatter):
        """Object without surrounding should not show distance."""
        obj = {
            "title": "Test",
            "price": 10000,
            "url": "http://test",
            "surrounding_desc": None,
        }
        result = formatter.format_object(obj)

        assert "🚇" not in result

    def test_format_no_tags(self, formatter):
        """Object without tags should not show hashtags."""
        obj = {"title": "Test", "price": 10000, "url": "http://test", "tags": []}
        result = formatter.format_object(obj)

        assert "#" not in result

    def test_format_contains_link(self, formatter, sample_db_ready_object):
        """Result should contain clickable link."""
        result = formatter.format_object(sample_db_ready_object)

        assert '<a href="https://rent.591.com.tw/12345678">' in result
        assert "查看詳情</a>" in result


# ============================================================
# _escape_html tests
# ============================================================


class TestEscapeHtml:
    """Tests for _escape_html method."""

    def test_escape_ampersand(self, formatter):
        """Ampersand should be escaped."""
        assert formatter._escape_html("A & B") == "A &amp; B"

    def test_escape_less_than(self, formatter):
        """Less than should be escaped."""
        assert formatter._escape_html("a < b") == "a &lt; b"

    def test_escape_greater_than(self, formatter):
        """Greater than should be escaped."""
        assert formatter._escape_html("a > b") == "a &gt; b"

    def test_escape_all_special_chars(self, formatter):
        """All special chars should be escaped."""
        result = formatter._escape_html("<script>alert('A & B')</script>")
        assert result == "&lt;script&gt;alert('A &amp; B')&lt;/script&gt;"

    def test_escape_empty_string(self, formatter):
        """Empty string should return empty."""
        assert formatter._escape_html("") == ""

    def test_escape_none(self, formatter):
        """None should return empty string."""
        assert formatter._escape_html(None) == ""

    def test_no_escape_normal_text(self, formatter):
        """Normal text should not be changed."""
        text = "這是正常的中文文字"
        assert formatter._escape_html(text) == text


# ============================================================
# format_command_result tests
# ============================================================


class TestFormatCommandResult:
    """Tests for format_command_result method."""

    def test_format_welcome(self, formatter):
        """Welcome message should format correctly."""
        result = CommandResult(
            success=True,
            title="welcome",
            message="",
            data={},
        )
        output = formatter.format_command_result(result)

        assert "歡迎使用 591 租屋小幫手" in output
        assert "管理頁面" in output

    def test_format_help(self, formatter):
        """Help message should format correctly."""
        result = CommandResult(
            success=True,
            title="help",
            message="",
            data={
                "steps": ["步驟一", "步驟二"],
                "commands": [
                    {"name": "清單", "desc": "顯示訂閱清單"},
                    {"name": "status", "desc": "查看狀態", "usage": ""},
                ],
            },
        )
        output = formatter.format_command_result(result)

        assert "使用說明" in output
        assert "步驟一" in output
        assert "清單" in output

    def test_format_error(self, formatter):
        """Error message should format correctly."""
        result = CommandResult(
            success=False,
            title="",
            message="",
            error="發生錯誤",
        )
        output = formatter.format_command_result(result)

        assert "❌" in output
        assert "發生錯誤" in output

    def test_format_list_subscriptions(self, formatter):
        """Subscription list should format correctly."""
        result = CommandResult(
            success=True,
            title="list_subscriptions",
            message="",
            data={
                "subscriptions": [
                    {
                        "id": 1,
                        "name": "台北套房",
                        "enabled": True,
                        "price_min": 10000,
                        "price_max": 20000,
                        "kind": [2],
                    },
                    {
                        "id": 2,
                        "name": "新北整層",
                        "enabled": False,
                        "price_min": 15000,
                        "price_max": 30000,
                        "kind": [1],
                    },
                ],
                "count": 2,
            },
        )
        output = formatter.format_command_result(result)

        assert "訂閱清單" in output
        assert "台北套房" in output
        assert "新北整層" in output
        assert "▶️" in output  # enabled
        assert "⏸️" in output  # disabled
        assert "共 2 個訂閱" in output

    def test_format_list_empty(self, formatter):
        """Empty list should format correctly."""
        result = CommandResult(
            success=True,
            title="list_empty",
            message="",
            data={},
        )
        output = formatter.format_command_result(result)

        assert "訂閱清單" in output
        assert "沒有任何訂閱" in output

    def test_format_status_bound(self, formatter):
        """Bound status should format correctly."""
        result = CommandResult(
            success=True,
            title="status_bound",
            message="",
            data={
                "service": "telegram",
                "service_id": "123456789",
                "enabled": True,
                "created_at": "2024-01-01T10:30:00",
            },
        )
        output = formatter.format_command_result(result)

        assert "綁定狀態" in output
        assert "Telegram" in output
        assert "123456789" in output
        assert "啟用中" in output

    def test_format_status_unbound(self, formatter):
        """Unbound status should format correctly."""
        result = CommandResult(
            success=True,
            title="status_unbound",
            message="",
            data={},
        )
        output = formatter.format_command_result(result)

        assert "綁定狀態" in output
        assert "尚未綁定" in output
