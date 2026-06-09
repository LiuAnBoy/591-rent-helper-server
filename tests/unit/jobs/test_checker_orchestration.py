"""
Characterization tests for Checker.check() orchestration.

These pin the *observable behavior* of the crawl orchestration — what gets
fetched, pre-filtered, detail-fetched, saved, marked seen, matched and
broadcast — by driving a real Checker with fake (injected) dependencies and
asserting on the calls those fakes receive plus the returned result dict.

Purpose: act as the regression net for the Phase 2 Source-ification rewrite,
which extracts the list/detail/transform orchestration out of check() into an
X591Source and moves pre-filter to run on standardized data. Because these
tests assert on the observable boundary (dependency calls + result), not on
check()'s internal structure or intermediate data shapes, they stay valid
across that rewrite.

The matcher and transform pipeline are REAL here (only I/O is faked), so the
fixtures are crafted to genuinely match / not-match through the real logic.
"""

import pytest

from src.crawler.sources.x591.source import X591Source
from src.jobs.checker import Checker


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Skip the real rate-limit sleeps (now in the source) so tests stay fast."""

    async def _instant(*args, **kwargs):
        return None

    monkeypatch.setattr("src.crawler.sources.x591.source.asyncio.sleep", _instant)

# --------------------------------------------------------------------------
# Raw data builders (shapes mirror 591 ListRawData / DetailRawData)
# --------------------------------------------------------------------------


def make_list_item(
    obj_id: int,
    *,
    section: int = 7,
    kind_name: str = "獨立套房",
    price_raw: str = "15,000元/月",
    area_raw: str = "10坪",
    floor_raw: str = "3F/10F",
    title: str = "信義區套房",
    address_raw: str = "信義區-信義路",
    tags: list[str] | None = None,
    layout_raw: str = "",
) -> dict:
    """Build a ListRawData dict for a region-1 信義區 listing."""
    return {
        "region": 1,
        "section": section,  # real list parser yields an int section (or None)
        "id": str(obj_id),
        "url": f"https://rent.591.com.tw/{obj_id}",
        "title": title,
        "price_raw": price_raw,
        "tags": tags or [],
        "kind_name": kind_name,
        "layout_raw": layout_raw,
        "area_raw": area_raw,
        "floor_raw": floor_raw,
        "address_raw": address_raw,
    }


def make_detail(
    obj_id: int,
    *,
    section: str = "7",
    kind: str = "2",
    price_raw: str = "15,000元/月",
    area_raw: str = "10坪",
    floor_raw: str = "3F/10F",
    title: str = "信義區精緻套房",
) -> dict:
    """Build a DetailRawData dict consistent with make_list_item defaults."""
    return {
        "id": obj_id,
        "title": title,
        "price_raw": price_raw,
        "tags": [],
        "address_raw": "台北市信義區信義路",
        "region": "1",
        "section": section,
        "kind": kind,
        "floor_raw": floor_raw,
        "layout_raw": "2房1廳1衛",
        "area_raw": area_raw,
        "gender_raw": None,
        "shape_raw": "電梯大樓",
        "fitment_raw": "新裝潢",
        "options": [],
        "surrounding_type": None,
        "surrounding_raw": None,
    }


def wide_sub(sub_id: int = 1) -> dict:
    """A subscription that matches the default 信義區 套房 fixtures."""
    return {
        "id": sub_id,
        "region": 1,
        "price_min": 10000,
        "price_max": 20000,
        "kind": [2],
        "section": [7],
        "shape": None,
        "area_min": None,
        "area_max": None,
        "layout": None,
        "bathroom": None,
        "floor_min": None,
        "floor_max": None,
        "fitment": None,
        "exclude_rooftop": False,
        "gender": None,
        "pet_required": False,
        "other": [],
        "options": [],
    }


# --------------------------------------------------------------------------
# Fake dependencies (record calls; no real I/O)
# --------------------------------------------------------------------------


class FakeRedis:
    def __init__(self, *, subs=None, new_ids=None, uninitialized_ids=None):
        self._subs = subs or []
        # new_ids: None -> treat every queried id as new; else a set of int ids
        self._new_ids = new_ids
        self._uninitialized_ids = set(uninitialized_ids or [])
        self.added_seen: list[tuple[int, set]] = []
        self.marked_initialized: list[int] = []
        self.updated_objects: list[tuple[int, list]] = []

    async def get_new_ids(self, region, ids):
        if self._new_ids is None:
            return set(ids)
        return {i for i in ids if i in self._new_ids}

    async def add_seen_ids(self, region, ids):
        self.added_seen.append((region, set(ids)))

    async def get_subscriptions_by_region(self, region):
        return list(self._subs)

    async def get_uninitialized_subscriptions(self, subs):
        return [s for s in subs if s["id"] in self._uninitialized_ids]

    async def mark_subscription_initialized(self, sub_id):
        self.marked_initialized.append(sub_id)

    async def update_region_objects(self, region, objects):
        self.updated_objects.append((region, objects))


class FakePostgres:
    def __init__(self):
        self.finished: list[dict] = []
        self.pool = None

    async def start_crawler_run(self, region):
        return 1

    async def finish_crawler_run(self, **kwargs):
        self.finished.append(kwargs)


class FakeListFetcher:
    def __init__(self, pages: dict[int, list]):
        # pages: first_row offset -> list of ListRawData
        self._pages = pages
        self.calls: list[int] = []

    async def fetch_objects_raw(self, region, sort, first_row):
        self.calls.append(first_row)
        return self._pages.get(first_row, [])


class FakeDetailFetcher:
    def __init__(self, details=None, not_found=0, failed=0):
        self._details = details or {}
        self._not_found = not_found
        self._failed = failed
        self.fetched_ids: list[int] | None = None

    async def fetch_details_batch_raw(self, ids):
        self.fetched_ids = list(ids)
        found = {i: self._details[i] for i in ids if i in self._details}
        return found, self._not_found, self._failed


class FakeRepo:
    def __init__(self):
        self.saved_batches: list[list] = []

    async def save_batch(self, objects):
        self.saved_batches.append(objects)
        return len(objects)


class FakeBroadcaster:
    def __init__(self):
        self.broadcasts: list[list] = []
        self.admin_calls: list[dict] = []

    async def broadcast(self, grouped):
        self.broadcasts.append(grouped)
        return {
            "total": len(grouped),
            "success": len(grouped),
            "failed": 0,
            "failures": [],
        }

    async def notify_admin(self, **kwargs):
        self.admin_calls.append(kwargs)


def build_checker(
    *,
    pages,
    redis,
    details=None,
    detail_not_found=0,
    detail_failed=0,
    broadcaster=None,
    enable_broadcast=True,
):
    """Wire a Checker with a real X591Source over faked fetchers + repo pre-set."""
    list_fetcher = FakeListFetcher(pages)
    detail_fetcher = FakeDetailFetcher(details, detail_not_found, detail_failed)
    postgres = FakePostgres()
    repo = FakeRepo()
    bc = broadcaster if broadcaster is not None else FakeBroadcaster()
    # Real source over fake fetchers: exercises the actual pagination / early-stop
    # / detail-merge logic that now lives in X591Source.
    source = X591Source(
        redis=redis, list_fetcher=list_fetcher, detail_fetcher=detail_fetcher
    )
    checker = Checker(
        postgres=postgres,
        redis=redis,
        source=source,
        broadcaster=bc,
        enable_broadcast=enable_broadcast,
    )
    # Pre-set so _ensure_connections does not build a real ObjectRepository.
    checker._object_repo = repo
    return checker, {
        "list_fetcher": list_fetcher,
        "detail_fetcher": detail_fetcher,
        "source": source,
        "postgres": postgres,
        "repo": repo,
        "broadcaster": bc,
        "redis": redis,
    }


def saved_by_source_id(repo: FakeRepo) -> dict:
    """Flatten saved batches into {source_id: object}."""
    out = {}
    for batch in repo.saved_batches:
        for obj in batch:
            out[obj["source_id"]] = obj
    return out


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


class TestCheckOrchestration:
    async def test_empty_page1_fails_run_and_alerts(self):
        """Page 1 returns nothing -> failed crawler run + admin alert, fetched=0."""
        redis = FakeRedis(subs=[wide_sub()])
        checker, deps = build_checker(pages={0: []}, redis=redis)

        result = await checker.check(region=1)

        assert result["fetched"] == 0
        assert result["new_count"] == 0
        assert deps["postgres"].finished[-1]["status"] == "failed"
        assert any(
            c.get("error_type")
            and "LIST_FETCH" in str(c["error_type"])
            for c in deps["broadcaster"].admin_calls
        )
        # No detail fetch attempted.
        assert deps["detail_fetcher"].fetched_ids is None

    async def test_early_stop_when_page_has_old_items(self):
        """A page containing any already-seen id stops pagination (no page 2)."""
        redis = FakeRedis(subs=[wide_sub()], new_ids={111})  # 999 is old
        checker, deps = build_checker(
            pages={0: [make_list_item(111), make_list_item(999)]},
            redis=redis,
            details={111: make_detail(111)},
        )

        result = await checker.check(region=1)

        assert deps["list_fetcher"].calls == [0]  # page 2 never fetched
        assert result["fetched"] == 2
        assert result["new_count"] == 1

    async def test_fetches_page2_when_all_new(self):
        """A fully-new first page triggers fetching the second page."""
        redis = FakeRedis(subs=[wide_sub()], new_ids={111, 222})
        checker, deps = build_checker(
            pages={
                0: [make_list_item(111)],
                30: [make_list_item(222)],
            },
            redis=redis,
            details={111: make_detail(111), 222: make_detail(222)},
        )

        await checker.check(region=1)

        assert deps["list_fetcher"].calls == [0, 30]

    async def test_prefilter_limits_detail_fetch(self):
        """Only listings that might match a sub get a detail fetch."""
        redis = FakeRedis(subs=[wide_sub()], new_ids={111, 222})
        checker, deps = build_checker(
            pages={
                0: [
                    make_list_item(111),  # 15,000 -> in range, candidate
                    make_list_item(222, price_raw="50,000元/月"),  # out of range
                ],
                30: [],
            },
            redis=redis,
            details={111: make_detail(111)},
        )

        result = await checker.check(region=1)

        assert deps["detail_fetcher"].fetched_ids == [111]
        assert result["pre_filter_input"] == 2
        assert result["pre_filter_output"] == 1
        assert result["pre_filter_skipped"] == 1

    async def test_prefilter_respects_non_price_criterion(self):
        """A non-price quick criterion (area) also gates the detail fetch.

        Guards the upcoming move of pre-filter onto standardized data: if a
        non-price condition silently regressed, this 10坪 item would wrongly
        pass an area_min=20 filter and trigger a detail fetch.
        """
        sub = wide_sub()
        sub["area_min"] = 20  # our 10坪 listing is below the minimum -> skip
        redis = FakeRedis(subs=[sub], new_ids={111})
        checker, deps = build_checker(
            pages={0: [make_list_item(111), make_list_item(999)]},
            redis=redis,
            details={111: make_detail(111)},
        )

        result = await checker.check(region=1)

        assert deps["detail_fetcher"].fetched_ids is None
        assert result["pre_filter_output"] == 0
        assert result["pre_filter_skipped"] == 1

    async def test_unknown_section_is_not_prefiltered_out(self):
        """A listing whose section didn't parse must still get a detail fetch.

        On the list page section is often None; after standardization it becomes
        the 0 unknown-sentinel. With a section subscription filter, the object
        must NOT be dropped at pre-filter (detail may resolve the section) — the
        old raw pre-filter let unknown sections through.
        """
        redis = FakeRedis(subs=[wide_sub()], new_ids={111})  # wide_sub: section [7]
        checker, deps = build_checker(
            pages={0: [make_list_item(111, section=None), make_list_item(999)]},
            redis=redis,
            details={111: make_detail(111)},  # detail resolves section -> 7
        )

        result = await checker.check(region=1)

        assert deps["detail_fetcher"].fetched_ids == [111]
        assert result["pre_filter_output"] == 1

    async def test_all_new_objects_saved_with_correct_has_detail(self):
        """Candidates are saved has_detail=True; non-candidates has_detail=False."""
        redis = FakeRedis(subs=[wide_sub()], new_ids={111, 222})
        checker, deps = build_checker(
            pages={
                0: [
                    make_list_item(111),  # candidate -> detail
                    make_list_item(222, price_raw="50,000元/月"),  # skipped
                ],
                30: [],
            },
            redis=redis,
            details={111: make_detail(111)},
        )

        await checker.check(region=1)

        saved = saved_by_source_id(deps["repo"])
        assert saved["111"]["has_detail"] is True
        assert saved["222"]["has_detail"] is False
        # Seen set updated with both new source ids.
        assert deps["redis"].added_seen == [(1, {"111", "222"})]

    async def test_initialized_sub_match_is_broadcast(self):
        """An initialized sub matching a detailed object triggers a broadcast."""
        redis = FakeRedis(subs=[wide_sub()], new_ids={111})  # uninitialized_ids empty
        checker, deps = build_checker(
            pages={0: [make_list_item(111), make_list_item(999)]},
            redis=redis,
            details={111: make_detail(111)},
        )

        result = await checker.check(region=1)

        assert len(result["matches"]) == 1
        assert len(deps["broadcaster"].broadcasts) == 1
        grouped = deps["broadcaster"].broadcasts[0]
        # grouped: list of (obj, subs) tuples — verify both the object identity
        # and that the matching subscription is grouped under it.
        assert len(grouped) == 1
        obj, subs = grouped[0]
        assert obj["source_id"] == "111"
        assert [s["id"] for s in subs] == [1]

    async def test_uninitialized_sub_not_notified_but_marked(self):
        """First-scan (uninitialized) subs are baseline-marked, never notified."""
        redis = FakeRedis(
            subs=[wide_sub()], new_ids={111}, uninitialized_ids={1}
        )
        checker, deps = build_checker(
            pages={0: [make_list_item(111), make_list_item(999)]},
            redis=redis,
            details={111: make_detail(111)},
        )

        result = await checker.check(region=1)

        assert result["matches"] == []
        assert deps["broadcaster"].broadcasts == []
        assert result["initialized_subs"] == [1]
        assert 1 in deps["redis"].marked_initialized

    async def test_no_subscriptions_skips_detail_but_saves(self):
        """With no subs, detail fetch is skipped but new objects are still saved."""
        redis = FakeRedis(subs=[], new_ids={111})
        checker, deps = build_checker(
            pages={0: [make_list_item(111), make_list_item(999)]},
            redis=redis,
        )

        result = await checker.check(region=1)

        assert deps["detail_fetcher"].fetched_ids is None
        saved = saved_by_source_id(deps["repo"])
        assert saved["111"]["has_detail"] is False
        assert result["pre_filter_skipped"] == result["pre_filter_input"]

    async def test_successful_run_recorded(self):
        """A normal run finishes the crawler_run as success with counts."""
        redis = FakeRedis(subs=[wide_sub()], new_ids={111})
        checker, deps = build_checker(
            pages={0: [make_list_item(111), make_list_item(999)]},
            redis=redis,
            details={111: make_detail(111)},
        )

        await checker.check(region=1)

        finished = deps["postgres"].finished[-1]
        assert finished["status"] == "success"
        assert finished["total_fetched"] == 2
        assert finished["new_objects"] == 1
