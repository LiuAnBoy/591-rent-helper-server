"""Tests for the pause/resume notification menus (pure builders)."""

from src.channels.telegram.menus import build_pause_menu, build_resume_menu


def _btn_texts(markup):
    return [b.text for row in markup.inline_keyboard for b in row]


def _callback_datas(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_pause_menu_shows_user_and_enabled_subs():
    subs = [{"id": 1, "name": "套房", "enabled": True}]
    markup = build_pause_menu(notify_enabled=True, subs=subs, web_app_url="https://x")
    texts = _btn_texts(markup)
    assert any("使用者" in t for t in texts)
    assert any("套房" in t for t in texts)
    assert any("詳細設定" in t for t in texts)
    assert "notif:pause_user" in _callback_datas(markup)
    assert "notif:disable_sub:1" in _callback_datas(markup)


def test_pause_menu_hides_user_when_notify_off():
    markup = build_pause_menu(notify_enabled=False, subs=[], web_app_url="https://x")
    assert not any("使用者" in t for t in _btn_texts(markup))


def test_pause_menu_skips_disabled_subs():
    subs = [{"id": 2, "name": "整層", "enabled": False}]
    markup = build_pause_menu(notify_enabled=True, subs=subs, web_app_url="https://x")
    assert not any("整層" in t for t in _btn_texts(markup))


def test_resume_menu_lists_disabled_subs_when_user_on():
    subs = [{"id": 2, "name": "整層", "enabled": False}]
    markup = build_resume_menu(notify_enabled=True, subs=subs, web_app_url="https://x")
    assert any("整層" in t for t in _btn_texts(markup))
    assert "notif:enable_sub:2" in _callback_datas(markup)


def test_resume_menu_when_user_off_only_shows_user_button():
    """Hierarchy guard: while user notify is off, sub toggles are hidden."""
    subs = [{"id": 2, "name": "整層", "enabled": False}]
    markup = build_resume_menu(notify_enabled=False, subs=subs, web_app_url="https://x")
    assert "notif:resume_user" in _callback_datas(markup)
    assert "notif:enable_sub:2" not in _callback_datas(markup)
    assert not any("整層" in t for t in _btn_texts(markup))


def test_pause_menu_when_user_off_hides_sub_buttons():
    """Hierarchy guard: user already off -> no user button, no sub buttons."""
    subs = [{"id": 1, "name": "套房", "enabled": True}]
    markup = build_pause_menu(notify_enabled=False, subs=subs, web_app_url="https://x")
    assert "notif:disable_sub:1" not in _callback_datas(markup)
    assert not any("套房" in t for t in _btn_texts(markup))


def test_resume_menu_hides_user_when_already_on():
    markup = build_resume_menu(notify_enabled=True, subs=[], web_app_url="https://x")
    assert not any("使用者" in t for t in _btn_texts(markup))


def test_long_name_truncated():
    subs = [{"id": 1, "name": "超" * 50, "enabled": True}]
    markup = build_pause_menu(notify_enabled=True, subs=subs, web_app_url="")
    label = [t for t in _btn_texts(markup) if "超" in t][0]
    assert "…" in label and len(label) < 60


def test_no_web_app_url_omits_settings_button():
    markup = build_pause_menu(notify_enabled=True, subs=[], web_app_url="")
    assert not any("詳細設定" in t for t in _btn_texts(markup))
