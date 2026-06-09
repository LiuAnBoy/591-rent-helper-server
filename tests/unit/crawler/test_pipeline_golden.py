"""
Golden (characterization) tests for the full 591 raw -> DBReadyData pipeline.

These pin the *exact* output of the end-to-end transform chain
(``combine_raw_data`` / ``combine_with_list_only`` -> ``transform_to_db_ready``)
for a known raw input. Their purpose is to act as a regression net for the
Phase 2 "Source-ification" refactor: when the 591 combiner/transformers move
into ``src/crawler/sources/x591/``, these tests prove the moved code still
produces byte-identical ``DBReadyData`` (only import paths should change).

Inputs are inlined on purpose: a golden test owns its input so the
input<->output pairing is locked together and cannot silently drift if a
shared fixture is edited elsewhere.

Note on ordering: ``tags``, ``options`` and ``other`` are derived via
``list(set(...))``, so their order is not stable across runs (PYTHONHASHSEED).
They are compared as sets; every other field is compared exactly.
"""

from src.crawler.combiner import combine_raw_data, combine_with_list_only
from src.utils.transformers import transform_to_db_ready

# Fields whose order is non-deterministic (set-derived) -> compare as sets.
_SET_FIELDS = ("tags", "options", "other")


def _assert_db_ready_equals(actual: dict, expected: dict) -> None:
    """Compare a DBReadyData dict against a golden dict.

    Set-derived fields are compared order-insensitively; all other fields
    (and the overall key set) are compared exactly.
    """
    # Same shape: pinning the key set guards the DBReadyData contract itself.
    assert set(actual.keys()) == set(expected.keys())

    for field in _SET_FIELDS:
        assert sorted(actual[field]) == sorted(expected[field]), (
            f"set field {field!r}: {actual[field]!r} != {expected[field]!r}"
        )

    actual_rest = {k: v for k, v in actual.items() if k not in _SET_FIELDS}
    expected_rest = {k: v for k, v in expected.items() if k not in _SET_FIELDS}
    assert actual_rest == expected_rest


# Inlined raw inputs (the "golden" inputs) ---------------------------------

_LIST_RAW = {
    "region": 1,
    "section": "7",
    "id": "12345678",
    "url": "https://rent.591.com.tw/12345678",
    "title": "台北市信義區套房",
    "price_raw": "15,000元/月",
    "tags": ["近捷運", "有陽台"],
    "kind_name": "獨立套房",
    "layout_raw": "",
    "area_raw": "10坪",
    "floor_raw": "3F/10F",
    "address_raw": "信義區-信義路",
}

_DETAIL_RAW = {
    "id": 12345678,
    "title": "台北市信義區精緻套房",
    "price_raw": "16,000元/月",
    "tags": ["可養寵物", "有電梯"],
    "address_raw": "台北市信義區信義路五段",
    "region": "1",
    "section": "7",
    "kind": "2",
    "floor_raw": "3F/10F",
    "layout_raw": "2房1廳1衛",
    "area_raw": "12坪",
    "gender_raw": None,
    "shape_raw": "電梯大樓",
    "fitment_raw": "新裝潢",
    "options": ["冷氣", "洗衣機"],
    "surrounding_type": "metro",
    "surrounding_raw": "距信義安和站353公尺",
}


class TestPipelineGolden:
    """End-to-end raw -> DBReadyData golden output."""

    def test_list_plus_detail_golden(self):
        """Full pipeline (list + detail merged) produces the exact DBReadyData.

        Exercises Detail-over-List priority (title/price/address/area from
        detail), code mappings (shape/fitment/options/other), surrounding
        parsing, and source/source_id identity.
        """
        result = transform_to_db_ready(combine_raw_data(_LIST_RAW, _DETAIL_RAW))

        expected = {
            "source": "591",
            "source_id": "12345678",
            "url": "https://rent.591.com.tw/12345678",
            "title": "台北市信義區精緻套房",  # Detail priority
            "price": 16000,  # Detail priority
            "price_unit": "元/月",
            "region": 1,
            "section": 7,
            "kind": 2,
            "kind_name": "獨立套房",
            "address": "台北市信義區信義路五段",  # Detail priority
            "floor": 3,
            "floor_str": "3F/10F",
            "total_floor": 10,
            "is_rooftop": False,
            "layout": 2,
            "layout_str": "2房1廳1衛",
            "bathroom": 1,
            "area": 12.0,  # Detail priority
            "shape": 2,  # 電梯大樓
            "fitment": 99,  # 新裝潢 -> 99 (新)
            "gender": "all",
            "pet_allowed": True,
            "options": ["washer", "cold"],
            "other": ["pet", "balcony_1", "lift", "near_subway"],
            "tags": ["有電梯", "有陽台", "可養寵物", "近捷運"],
            "surrounding_type": "metro",
            "surrounding_desc": "信義安和站",
            "surrounding_distance": 353,
            "has_detail": True,
        }

        _assert_db_ready_equals(result, expected)

    def test_list_only_golden(self):
        """List-only pipeline produces the exact DBReadyData.

        Exercises the list-only branch: detail-only fields stay None/empty,
        ``has_detail`` is False, kind is still derived from kind_name, and the
        list address/price/title are used.
        """
        result = transform_to_db_ready(combine_with_list_only(_LIST_RAW))

        expected = {
            "source": "591",
            "source_id": "12345678",
            "url": "https://rent.591.com.tw/12345678",
            "title": "台北市信義區套房",  # List value (no detail)
            "price": 15000,  # List value
            "price_unit": "元/月",
            "region": 1,
            "section": 7,
            "kind": 2,  # derived from kind_name "獨立套房"
            "kind_name": "獨立套房",
            "address": "信義區信義路",
            "floor": 3,
            "floor_str": "3F/10F",
            "total_floor": 10,
            "is_rooftop": False,
            "layout": None,
            "layout_str": "",
            "bathroom": None,
            "area": 10.0,
            "shape": None,
            "fitment": None,
            "gender": "all",
            "pet_allowed": False,
            "options": [],
            "other": ["balcony_1", "near_subway"],
            "tags": ["近捷運", "有陽台"],
            "surrounding_type": None,
            "surrounding_desc": None,
            "surrounding_distance": None,
            "has_detail": False,
        }

        _assert_db_ready_equals(result, expected)
