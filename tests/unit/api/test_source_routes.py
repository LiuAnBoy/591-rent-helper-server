"""Route-level tests for source catalog + per-subscription source toggle.

The project has no TestClient/auth harness, so these call the route coroutine
functions directly with a fake user + monkeypatched repository/service —
matching the codebase's "drive real code with fakes" style.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.routes.subscriptions as subs_routes
from src.api.routes.sources import list_sources


async def test_list_sources_returns_catalog():
    result = await list_sources()
    assert result == {"items": [{"key": "591", "name": "591 租屋網"}]}


class FakeRepo:
    def __init__(self, existing):
        self._existing = existing

    async def get_by_id(self, sub_id):
        return self._existing


def _patch_repo(monkeypatch, existing):
    async def fake_get_repo():
        return FakeRepo(existing)

    monkeypatch.setattr(subs_routes, "get_repository", fake_get_repo)


def _patch_notify_on(monkeypatch):
    """Bypass the user-notify hierarchy guard (treat user-level notify as on)."""

    async def ok(user_id):
        return None

    monkeypatch.setattr(subs_routes, "_assert_user_notify_on", ok)


async def test_set_source_unknown_source_400(monkeypatch):
    _patch_repo(monkeypatch, {"id": 1, "user_id": 1})
    user = SimpleNamespace(id=1)
    with pytest.raises(HTTPException) as exc:
        await subs_routes.set_subscription_source(
            1, subs_routes.SourceToggle(source="nope", enabled=False), user
        )
    assert exc.value.status_code == 400


async def test_set_source_not_found_404(monkeypatch):
    _patch_repo(monkeypatch, None)
    user = SimpleNamespace(id=1)
    with pytest.raises(HTTPException) as exc:
        await subs_routes.set_subscription_source(
            1, subs_routes.SourceToggle(source="591", enabled=False), user
        )
    assert exc.value.status_code == 404


async def test_set_source_not_owner_403(monkeypatch):
    _patch_repo(monkeypatch, {"id": 1, "user_id": 999})
    user = SimpleNamespace(id=1)
    with pytest.raises(HTTPException) as exc:
        await subs_routes.set_subscription_source(
            1, subs_routes.SourceToggle(source="591", enabled=False), user
        )
    assert exc.value.status_code == 403


async def test_set_source_success_returns_state(monkeypatch):
    _patch_repo(monkeypatch, {"id": 1, "user_id": 1, "enabled": True})
    _patch_notify_on(monkeypatch)

    async def fake_set_source_enabled(repo, existing, source, enabled):
        return {"id": 1, "enabled": True, "disabled_sources": ["591"]}

    monkeypatch.setattr(
        "src.modules.subscriptions.service.set_source_enabled",
        fake_set_source_enabled,
    )
    user = SimpleNamespace(id=1)
    result = await subs_routes.set_subscription_source(
        1, subs_routes.SourceToggle(source="591", enabled=False), user
    )
    assert result == {
        "success": True,
        "enabled": True,
        "disabled_sources": ["591"],
    }


async def test_set_source_blocked_when_user_notify_off_403(monkeypatch):
    """Hierarchy guard: user-level notify off -> 403 before any mutation."""
    _patch_repo(monkeypatch, {"id": 1, "user_id": 1, "enabled": True})

    async def deny(user_id):
        raise HTTPException(status_code=403, detail="請先開啟使用者通知")

    monkeypatch.setattr(subs_routes, "_assert_user_notify_on", deny)
    user = SimpleNamespace(id=1)
    with pytest.raises(HTTPException) as exc:
        await subs_routes.set_subscription_source(
            1, subs_routes.SourceToggle(source="591", enabled=False), user
        )
    assert exc.value.status_code == 403


async def test_set_source_blocked_when_subscription_disabled_403(monkeypatch):
    """Hierarchy guard: subscription disabled -> can't edit its sources (403)."""
    _patch_repo(monkeypatch, {"id": 1, "user_id": 1, "enabled": False})
    _patch_notify_on(monkeypatch)
    user = SimpleNamespace(id=1)
    with pytest.raises(HTTPException) as exc:
        await subs_routes.set_subscription_source(
            1, subs_routes.SourceToggle(source="591", enabled=False), user
        )
    assert exc.value.status_code == 403


async def test_set_source_vanished_during_update_404(monkeypatch):
    """If the row is deleted between ownership check and update -> 404, not 500."""
    _patch_repo(monkeypatch, {"id": 1, "user_id": 1, "enabled": True})
    _patch_notify_on(monkeypatch)

    async def fake_set_source_enabled(repo, existing, source, enabled):
        return None

    monkeypatch.setattr(
        "src.modules.subscriptions.service.set_source_enabled",
        fake_set_source_enabled,
    )
    user = SimpleNamespace(id=1)
    with pytest.raises(HTTPException) as exc:
        await subs_routes.set_subscription_source(
            1, subs_routes.SourceToggle(source="591", enabled=True), user
        )
    assert exc.value.status_code == 404
