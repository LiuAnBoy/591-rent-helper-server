"""Characterization tests for the subscription mutation service.

Drive the real service with a fake repository and patched side-effects
(``sync_subscription_to_redis`` / instant-notify), asserting on the observable
boundary: which repo calls happen, how Redis sync is invoked (was_disabled), and
whether a re-enable fires an instant notify.
"""

import asyncio

import src.modules.subscriptions.service as service


class FakeRepo:
    def __init__(self, *, provider_sub=None, updated_row=None):
        self.updated: list = []
        self.set_source_calls: list = []
        self._provider_sub = provider_sub
        self._updated_row = updated_row

    async def update(self, sub_id, data):
        self.updated.append((sub_id, data))
        return {"id": sub_id, **data}

    async def get_by_id_with_provider(self, sub_id):
        return self._provider_sub

    async def set_source_enabled(self, sub_id, source, enabled):
        self.set_source_calls.append((sub_id, source, enabled))
        return self._updated_row


def _patch_sync(monkeypatch, sink):
    async def fake_sync(sub, was_disabled=False):
        sink.append(was_disabled)

    monkeypatch.setattr(service, "sync_subscription_to_redis", fake_sync)


async def test_set_enabled_reenable_syncs_and_notifies(monkeypatch):
    """Disabled -> enabled: sync with was_disabled=True and fire instant notify."""
    synced: list = []
    notified: list = []
    _patch_sync(monkeypatch, synced)

    async def fake_notify(**kwargs):
        notified.append(kwargs)

    monkeypatch.setattr(
        "src.jobs.instant_notify.notify_for_new_subscription", fake_notify
    )

    repo = FakeRepo(
        provider_sub={
            "id": 1,
            "user_id": 7,
            "enabled": True,
            "service": "telegram",
            "service_id": "c1",
            "region": 1,
        }
    )
    existing = {"id": 1, "enabled": False, "region": 1}

    await service.set_enabled(repo, existing, True)

    assert repo.updated == [(1, {"enabled": True})]
    assert synced == [True]
    await asyncio.sleep(0)  # let the create_task notify run
    assert len(notified) == 1
    assert notified[0]["service_id"] == "c1"


async def test_set_enabled_disable_syncs_without_notify(monkeypatch):
    """Enabled -> disabled: sync with was_disabled=False, no instant notify."""
    synced: list = []
    notified: list = []
    _patch_sync(monkeypatch, synced)
    monkeypatch.setattr(
        "src.jobs.instant_notify.notify_for_new_subscription",
        lambda **k: notified.append(k),
    )

    repo = FakeRepo(
        provider_sub={
            "id": 1,
            "user_id": 7,
            "enabled": False,
            "service": "telegram",
            "service_id": "c1",
            "region": 1,
        }
    )
    existing = {"id": 1, "enabled": True, "region": 1}

    await service.set_enabled(repo, existing, False)

    assert repo.updated == [(1, {"enabled": False})]
    assert synced == [False]
    await asyncio.sleep(0)
    assert notified == []


async def test_set_source_enabled_updates_sources_and_syncs(monkeypatch):
    """Only edits disabled_sources; resyncs Redis (no enabled coupling/notify)."""
    synced: list = []
    _patch_sync(monkeypatch, synced)

    repo = FakeRepo(
        provider_sub={
            "id": 1,
            "user_id": 7,
            "enabled": True,
            "service": None,
            "service_id": None,
            "region": 1,
        },
        updated_row={"id": 1, "enabled": True, "disabled_sources": ["591"]},
    )
    existing = {"id": 1, "enabled": True, "region": 1}

    res = await service.set_source_enabled(repo, existing, "591", False)

    assert res == {"id": 1, "enabled": True, "disabled_sources": ["591"]}
    assert repo.set_source_calls == [(1, "591", False)]
    assert synced == [False]  # resynced so the guard sees the new array; not a re-enable
