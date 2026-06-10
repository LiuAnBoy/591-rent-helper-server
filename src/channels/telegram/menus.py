"""Telegram inline menus for pause/resume notification control.

Pure builders: take the user's provider/subscription state and return an
``InlineKeyboardMarkup``. Kept IO-free so they are easy to unit test; the
handler supplies the data and wires the callbacks.

callback_data scheme (<= 64 bytes):
    notif:pause_user
    notif:resume_user
    notif:disable_sub:<id>
    notif:enable_sub:<id>
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

_MAX_LABEL = 24


def _truncate(name: str) -> str:
    """Trim a subscription name to keep button labels short."""
    return name if len(name) <= _MAX_LABEL else name[: _MAX_LABEL - 1] + "…"


def _settings_row(web_app_url: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton("⚙️ 詳細設定", web_app=WebAppInfo(url=web_app_url))]


def build_pause_menu(
    notify_enabled: bool, subs: list[dict], web_app_url: str
) -> InlineKeyboardMarkup:
    """Menu listing currently-active items the user can turn OFF.

    Args:
        notify_enabled: User-level notify state; the "暫停全部" button only shows
            when notifications are currently on.
        subs: The user's subscriptions; an "停用：<name>" button is shown for each
            currently-enabled one.
        web_app_url: Management page URL; "詳細設定" omitted when empty.
    """
    rows: list[list[InlineKeyboardButton]] = []
    if notify_enabled:
        rows.append(
            [InlineKeyboardButton("👤 暫停全部（使用者）", callback_data="notif:pause_user")]
        )
    for s in subs:
        if s.get("enabled"):
            rows.append(
                [
                    InlineKeyboardButton(
                        f"📋 停用：{_truncate(s['name'])}",
                        callback_data=f"notif:disable_sub:{s['id']}",
                    )
                ]
            )
    if web_app_url:
        rows.append(_settings_row(web_app_url))
    return InlineKeyboardMarkup(rows)


def build_resume_menu(
    notify_enabled: bool, subs: list[dict], web_app_url: str
) -> InlineKeyboardMarkup:
    """Menu listing currently-disabled items the user can turn ON.

    Args:
        notify_enabled: User-level notify state; the "開啟全部" button only shows
            when notifications are currently off.
        subs: The user's subscriptions; an "啟用：<name>" button is shown for each
            currently-disabled one.
        web_app_url: Management page URL; "詳細設定" omitted when empty.
    """
    rows: list[list[InlineKeyboardButton]] = []
    if not notify_enabled:
        rows.append(
            [InlineKeyboardButton("👤 開啟全部（使用者）", callback_data="notif:resume_user")]
        )
    for s in subs:
        if not s.get("enabled"):
            rows.append(
                [
                    InlineKeyboardButton(
                        f"📋 啟用：{_truncate(s['name'])}",
                        callback_data=f"notif:enable_sub:{s['id']}",
                    )
                ]
            )
    if web_app_url:
        rows.append(_settings_row(web_app_url))
    return InlineKeyboardMarkup(rows)
