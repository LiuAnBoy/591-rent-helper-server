"""Tests for TelegramHandler callback routing (ownership + cross-layer toast).

The callback handler is the highest-risk new surface (R1: never trust the id in
callback_data). These drive ``_handle_callback`` with a fake bot + monkeypatched
repositories/service, asserting the toast and that mutations only happen for
owned subscriptions.
"""

from types import SimpleNamespace

import pytest

from src.channels.telegram.handler import TelegramHandler


class FakeBot:
    def __init__(self):
        self.answers: list = []
        self.edits: list = []
        self.sent: list = []

    async def answer_callback(self, callback_query_id, text=None):
        self.answers.append(text)
        return True

    async def edit_reply_markup(self, chat_id, message_id, reply_markup):
        self.edits.append((chat_id, message_id, reply_markup))
        return True

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))
        return True


def _make_cq(data, *, user_id=123, chat_id=123):
    return SimpleNamespace(
        id="cq1",
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat_id=chat_id, message_id=5),
    )


def _patch_common(monkeypatch, *, existing_sub, set_enabled_calls, notify_enabled=True):
    class FakeProvRepo:
        def __init__(self, pool):
            pass

        async def find_by_provider(self, provider, provider_id):
            return SimpleNamespace(user_id=7, notify_enabled=notify_enabled)

    monkeypatch.setattr("src.modules.providers.UserProviderRepository", FakeProvRepo)

    class FakeSubRepo:
        def __init__(self, pool):
            pass

        async def get_by_id(self, sub_id):
            return existing_sub

        async def get_by_user(self, user_id, enabled_only=False):
            return []

    monkeypatch.setattr("src.modules.subscriptions.SubscriptionRepository", FakeSubRepo)

    async def fake_set_enabled(repo, existing, enabled):
        set_enabled_calls.append((existing["id"], enabled))

    monkeypatch.setattr(
        "src.modules.subscriptions.service.set_enabled", fake_set_enabled
    )


@pytest.fixture
def handler():
    bot = FakeBot()
    h = TelegramHandler(bot=bot, pool=object())
    return h, bot


async def test_enable_sub_rejects_non_owner(handler, monkeypatch):
    """A sub owned by another user is refused; no mutation happens."""
    h, bot = handler
    calls: list = []
    _patch_common(
        monkeypatch,
        existing_sub={"id": 9, "user_id": 999, "enabled": False},
        set_enabled_calls=calls,
        notify_enabled=True,
    )

    await h._handle_callback(_make_cq("notif:enable_sub:9"))

    assert bot.answers == ["無權限"]
    assert calls == []  # never mutated


async def test_enable_sub_blocked_when_user_notify_off(handler, monkeypatch):
    """Hierarchy guard: can't modify a sub while user-level notify is off."""
    h, bot = handler
    calls: list = []
    _patch_common(
        monkeypatch,
        existing_sub={"id": 9, "user_id": 7, "enabled": False},
        set_enabled_calls=calls,
        notify_enabled=False,
    )

    await h._handle_callback(_make_cq("notif:enable_sub:9"))

    assert bot.answers == ["請先開啟使用者通知"]
    assert calls == []  # blocked before mutation


async def test_malformed_sub_callback_is_rejected(handler, monkeypatch):
    """Malformed callback_data (no / non-numeric id) -> '無效操作', no mutation."""
    h, bot = handler
    calls: list = []
    _patch_common(
        monkeypatch,
        existing_sub={"id": 1, "user_id": 7, "enabled": False},
        set_enabled_calls=calls,
    )

    await h._handle_callback(_make_cq("notif:disable_sub"))  # missing id
    await h._handle_callback(_make_cq("notif:enable_sub:abc"))  # non-numeric

    assert bot.answers == ["無效操作", "無效操作"]
    assert calls == []  # never mutated


async def test_unbound_user_gets_prompt(handler, monkeypatch):
    """An unbound user (no provider) is told to bind, no mutation."""
    h, bot = handler

    class NoProvRepo:
        def __init__(self, pool):
            pass

        async def find_by_provider(self, provider, provider_id):
            return None

    monkeypatch.setattr("src.modules.providers.UserProviderRepository", NoProvRepo)

    await h._handle_callback(_make_cq("notif:pause_user"))

    assert bot.answers == ["尚未綁定帳號"]
