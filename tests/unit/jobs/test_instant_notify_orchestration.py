"""
Characterization tests for InstantNotifier (immediate notify on subscribe).

Like the checker orchestration tests, these pin the *observable behavior* of
``notify_for_subscription`` -> ``_notify_from_redis`` -> ``_match_and_notify``
by faking the (inline-created) collaborators and asserting on the calls they
receive plus the returned {checked, matched, notified} dict.

Purpose: regression net for the Phase 2 rewrite, which swaps the inline
DetailFetcher + manual combine block for a Source.fetch_detail call and keys the
detail merge map by (source, source_id). Asserting on observable outcomes keeps
these valid across that change.

The matcher and transform pipeline are REAL (only I/O faked); fixtures are
crafted to genuinely match wide_sub through the real logic.
"""

import pytest

import src.jobs.instant_notify as instant_notify_mod
from src.crawler.sources.x591.source import X591Source
from src.jobs.instant_notify import InstantNotifier


def wide_sub(sub_id: int = 1) -> dict:
    """A subscription that matches the make_std_object fixtures."""
    return {
        "id": sub_id,
        "name": "測試訂閱",
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


def make_std_object(source_id, *, has_detail=True, price=15000, section=7, kind=2):
    """A standardized (DBReadyData-shaped) object as cached in Redis."""
    return {
        "source": "591",
        "source_id": str(source_id),
        "url": f"https://rent.591.com.tw/{source_id}",
        "title": "信義區套房",
        "price": price,
        "price_unit": "元/月",
        "region": 1,
        "section": section,
        "kind": kind,
        "kind_name": "獨立套房",
        "address": "信義區信義路",
        "floor": 3,
        "floor_str": "3F/10F",
        "total_floor": 10,
        "is_rooftop": False,
        "layout": 2,
        "layout_str": "2房1廳1衛",
        "bathroom": 1,
        "area": 10.0,
        "shape": 2,
        "fitment": 99,
        "gender": "all",
        "pet_allowed": False,
        "options": [],
        "other": [],
        "tags": [],
        "surrounding_type": None,
        "surrounding_desc": None,
        "surrounding_distance": None,
        "has_detail": has_detail,
    }


def make_detail(source_id):
    """DetailRawData for backfilling a has_detail=False object."""
    return {
        "id": source_id,
        "title": "信義區套房",
        "price_raw": "15,000元/月",
        "tags": [],
        "address_raw": "信義區信義路",
        "region": "1",
        "section": "7",
        "kind": "2",
        "floor_raw": "3F/10F",
        "layout_raw": "2房1廳1衛",
        "area_raw": "12坪",  # distinct from the cached stub's area (10.0) to prove merge
        "gender_raw": None,
        "shape_raw": "電梯大樓",
        "fitment_raw": "新裝潢",
        "options": [],
        "surrounding_type": None,
        "surrounding_raw": None,
    }


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class FakeRedis:
    def __init__(self, region_objects=None):
        # region_objects: None -> Redis miss; else list of std objects
        self._region_objects = region_objects
        self.set_calls = []
        self.updated = []
        self.marked_initialized = []

    async def get_region_objects(self, region):
        return self._region_objects

    async def set_region_objects(self, region, objects):
        self.set_calls.append((region, objects))

    async def update_region_objects(self, region, objects):
        self.updated.append((region, objects))

    async def mark_subscription_initialized(self, sub_id):
        self.marked_initialized.append(sub_id)


class FakePostgres:
    pool = None


class FakeBroadcaster:
    def __init__(self, success=True):
        self._success = success
        self.sent = []

    async def send_notification(self, provider, provider_id, obj, subscription_name):
        self.sent.append(
            {
                "provider": provider,
                "provider_id": provider_id,
                "obj": obj,
                "subscription_name": subscription_name,
            }
        )
        return {"success": self._success}


class FakeRepo:
    """Stand-in for ObjectRepository(pool)."""

    db_objects: list = []
    updated_batches: list = []

    def __init__(self, pool):
        pass

    async def get_latest_by_region(self, region, count):
        return list(FakeRepo.db_objects)

    async def update_batch_with_detail(self, objects):
        FakeRepo.updated_batches.append(objects)
        return len(objects)


class FakeDetailFetcher:
    """Detail fetcher fake injected into the X591Source.

    The source calls fetch_details_batch_raw with int ids, so ``details`` is
    keyed by int.
    """

    details: dict = {}
    fetched_ids = None

    async def start(self):
        pass

    async def close(self):
        pass

    async def fetch_details_batch_raw(self, ids):
        FakeDetailFetcher.fetched_ids = list(ids)
        found = {i: FakeDetailFetcher.details[i] for i in ids if i in FakeDetailFetcher.details}
        return found, 0, 0


class FakeListFetcher:
    """List fetcher fake; present so X591Source.start() builds no real fetcher.

    Instant notify never calls fetch_list, so this is only here to satisfy the
    source's dependency wiring.
    """

    async def start(self):
        pass

    async def close(self):
        pass

    async def fetch_objects_raw(self, region, sort, first_row):
        return []


@pytest.fixture(autouse=True)
def _patch_inline_collaborators(monkeypatch):
    """Inject a fake-backed source + repo; reset shared fake state."""
    FakeRepo.db_objects = []
    FakeRepo.updated_batches = []
    FakeDetailFetcher.details = {}
    FakeDetailFetcher.fetched_ids = None

    def fake_get_source(key, redis):
        return X591Source(
            redis=redis,
            list_fetcher=FakeListFetcher(),
            detail_fetcher=FakeDetailFetcher(),
        )

    monkeypatch.setattr(instant_notify_mod, "ObjectRepository", FakeRepo)
    monkeypatch.setattr(instant_notify_mod, "get_source", fake_get_source)
    # The rate-limit sleep now lives in the source.
    monkeypatch.setattr(
        "src.crawler.sources.x591.source.asyncio.sleep",
        _async_noop,
    )


async def _async_noop(*args, **kwargs):
    return None


def build_notifier(*, region_objects=None, broadcaster=None):
    notifier = InstantNotifier()
    notifier._postgres = FakePostgres()
    notifier._redis = FakeRedis(region_objects)
    notifier._broadcaster = broadcaster or FakeBroadcaster()
    return notifier


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


class TestInstantNotify:
    async def test_redis_hit_detailed_match_notifies(self):
        """A cached has_detail object that matches is notified immediately."""
        notifier = build_notifier(region_objects=[make_std_object(111)])

        result = await notifier.notify_for_subscription(
            user_id=1, subscription=wide_sub(), service="telegram", service_id="chat-1"
        )

        assert result == {"checked": 1, "matched": 1, "notified": 1}
        assert len(notifier._broadcaster.sent) == 1
        assert notifier._broadcaster.sent[0]["obj"]["source_id"] == "111"
        # Already detailed -> no detail fetch.
        assert FakeDetailFetcher.fetched_ids is None
        # Subscription marked initialized.
        assert notifier._redis.marked_initialized == [1]

    async def test_object_without_detail_is_backfilled_then_matched(self):
        """A has_detail=False cached object gets detail fetched, then matches."""
        FakeDetailFetcher.details = {111: make_detail(111)}
        notifier = build_notifier(
            region_objects=[make_std_object(111, has_detail=False)]
        )

        result = await notifier.notify_for_subscription(
            user_id=1, subscription=wide_sub(), service="telegram", service_id="chat-1"
        )

        assert FakeDetailFetcher.fetched_ids == [111]
        assert len(FakeRepo.updated_batches) == 1  # detail persisted
        # Verify the fetched detail content was actually merged, not just the
        # has_detail flag flipped: area 12.0 comes from the detail (12坪), while
        # the cached stub had area 10.0.
        persisted = FakeRepo.updated_batches[0][0]
        assert persisted["source_id"] == "111"
        assert persisted["has_detail"] is True
        assert persisted["area"] == 12.0
        assert result["matched"] == 1
        assert result["notified"] == 1

    async def test_prefilter_skips_out_of_range(self):
        """An object outside the price filter is pre-filtered out (no detail, no notify)."""
        notifier = build_notifier(
            region_objects=[make_std_object(111, price=50000)]  # > price_max
        )

        result = await notifier.notify_for_subscription(
            user_id=1, subscription=wide_sub(), service="telegram", service_id="chat-1"
        )

        assert result == {"checked": 1, "matched": 0, "notified": 0}
        assert FakeDetailFetcher.fetched_ids is None
        assert notifier._broadcaster.sent == []

    async def test_match_without_service_id_does_not_notify(self):
        """A match still counts but sends nothing when service_id is missing."""
        notifier = build_notifier(region_objects=[make_std_object(111)])

        result = await notifier.notify_for_subscription(
            user_id=1, subscription=wide_sub(), service="telegram", service_id=None
        )

        assert result["matched"] == 1
        assert result["notified"] == 0
        assert notifier._broadcaster.sent == []

    async def test_redis_miss_loads_from_db_and_populates_cache(self):
        """On a Redis miss, objects load from DB and the cache is populated."""
        FakeRepo.db_objects = [make_std_object(111)]
        notifier = build_notifier(region_objects=None)  # Redis miss

        result = await notifier.notify_for_subscription(
            user_id=1, subscription=wide_sub(), service="telegram", service_id="chat-1"
        )

        assert len(notifier._redis.set_calls) == 1  # cache populated
        cached_region, cached_payload = notifier._redis.set_calls[0]
        assert cached_region == 1
        assert [o["source_id"] for o in cached_payload] == ["111"]
        assert result["matched"] == 1
        assert result["notified"] == 1

    async def test_no_objects_anywhere_returns_zero(self):
        """Redis miss + empty DB -> nothing checked/matched/notified."""
        FakeRepo.db_objects = []
        notifier = build_notifier(region_objects=None)

        result = await notifier.notify_for_subscription(
            user_id=1, subscription=wide_sub(), service="telegram", service_id="chat-1"
        )

        assert result == {"checked": 0, "matched": 0, "notified": 0}
        assert notifier._broadcaster.sent == []
