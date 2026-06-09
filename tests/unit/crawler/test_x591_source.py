"""
Unit tests for X591Source fetcher ownership / lifecycle.

Guards the fix for the bug where routing through get_*_fetcher() singletons let
an instant-notify source close the browser the scheduled checker was still
using. Each source must own fresh, independent fetchers and must never close an
injected one.
"""

import src.crawler.sources.x591.source as source_mod
from src.crawler.sources.x591.source import X591Source


class _RecordingFetcher:
    """Stand-in for ListFetcher / DetailFetcher; records start/close."""

    def __init__(self, **kwargs):
        self.started = False
        self.closed = False

    async def start(self):
        self.started = True

    async def close(self):
        self.closed = True


class TestX591SourceLifecycle:
    async def test_start_creates_fresh_independent_fetchers(self, monkeypatch):
        """Two sources get distinct fetchers (no shared singleton)."""
        monkeypatch.setattr(source_mod, "ListFetcher", _RecordingFetcher)
        monkeypatch.setattr(source_mod, "DetailFetcher", _RecordingFetcher)

        s1 = X591Source(redis=None)
        s2 = X591Source(redis=None)
        await s1.start()
        await s2.start()

        # Each source owns its own pair — not a process-wide singleton.
        assert s1._list_fetcher is not s2._list_fetcher
        assert s1._detail_fetcher is not s2._detail_fetcher
        assert s1._owns_list and s1._owns_detail
        assert s1._list_fetcher.started and s1._detail_fetcher.started

    async def test_close_closes_only_owned_fetchers(self, monkeypatch):
        """A source closes the fetchers it created."""
        monkeypatch.setattr(source_mod, "ListFetcher", _RecordingFetcher)
        monkeypatch.setattr(source_mod, "DetailFetcher", _RecordingFetcher)

        source = X591Source(redis=None)
        await source.start()
        owned_list, owned_detail = source._list_fetcher, source._detail_fetcher

        await source.close()

        assert owned_list.closed and owned_detail.closed

    async def test_injected_fetchers_are_never_closed(self):
        """Injected fetchers belong to the caller; the source must not close them."""
        injected_list = _RecordingFetcher()
        injected_detail = _RecordingFetcher()
        source = X591Source(
            redis=None,
            list_fetcher=injected_list,
            detail_fetcher=injected_detail,
        )

        await source.start()  # injected -> not replaced, ownership stays False
        await source.close()

        assert not source._owns_list and not source._owns_detail
        assert not injected_list.closed
        assert not injected_detail.closed
