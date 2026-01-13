"""
Shared pytest fixtures for all tests.
"""

import pytest


# ============================================================
# Sample Data Fixtures
# ============================================================


@pytest.fixture
def sample_list_raw_data() -> dict:
    """Sample ListRawData for testing."""
    return {
        "id": 12345678,
        "title": "台北市信義區獨立套房",
        "url": "https://rent.591.com.tw/12345678",
        "region": 1,
        "section": 7,
        "kind": 1,
        "kind_name": "獨立套房",
        "price_raw": "15,000",
        "price_unit": "元/月",
        "floor_raw": "3F/10F",
        "area_raw": "10坪",
        "address_raw": "台北市信義區信義路五段",
        "tags": ["近捷運", "有陽台", "可養寵物"],
    }


@pytest.fixture
def sample_detail_raw_data() -> dict:
    """Sample DetailRawData for testing."""
    return {
        "id": 12345678,
        "title": "台北市信義區獨立套房",
        "tags": ["近捷運", "有陽台", "可養寵物"],
        "shape_raw": "公寓",
        "fitment_raw": "簡易裝潢",
        "layout_raw": "2房1廳1衛",
        "area_raw": "10坪",
        "floor_raw": "3F/10F",
        "address_raw": "信義區信義路五段",
        "surrounding_type": "捷運",
        "surrounding_raw": "距信義安和站353公尺",
        "gender_raw": "男女皆可",
        "options": ["冷氣", "洗衣機", "冰箱"],
    }


@pytest.fixture
def sample_combined_data(sample_list_raw_data, sample_detail_raw_data) -> dict:
    """Sample combined data (list + detail merged)."""
    combined = {**sample_list_raw_data}
    combined.update(sample_detail_raw_data)
    return combined


@pytest.fixture
def sample_subscription() -> dict:
    """Sample subscription for testing."""
    return {
        "id": 1,
        "user_id": 100,
        "region": 1,
        "enabled": True,
        "price_min": 10000,
        "price_max": 20000,
        "kind": [1, 2],
        "floor_min": 2,
        "floor_max": 10,
        "section": None,
        "gender": None,
        "pet_required": False,
        "other": [],
        "options": [],
    }


@pytest.fixture
def sample_object() -> dict:
    """Sample object (DB format) for testing."""
    return {
        "id": 12345678,
        "title": "台北市信義區獨立套房",
        "url": "https://rent.591.com.tw/12345678",
        "region": 1,
        "section": 7,
        "kind": 1,
        "kind_name": "獨立套房",
        "price": 15000,
        "price_unit": "元/月",
        "floor": 3,
        "floor_str": "3F/10F",
        "total_floor": 10,
        "is_rooftop": False,
        "layout": 2,
        "layout_str": "2房1廳1衛",
        "bathroom": 1,
        "area": 10.0,
        "shape": 1,
        "fitment": 2,
        "gender": "all",
        "pet_allowed": True,
        "options": ["冷氣", "洗衣機", "冰箱"],
        "other": ["balcony", "nearMRT"],
        "tags": ["近捷運", "有陽台", "可養寵物"],
        "surrounding_type": "捷運",
        "surrounding_desc": "信義安和站",
        "surrounding_distance": 353,
        "address": "信義區信義路五段",
    }


# ============================================================
# Tag Fixtures
# ============================================================


@pytest.fixture
def tags_with_pet() -> list[str]:
    """Tags that include pet allowed."""
    return ["近捷運", "可養寵物", "有陽台"]


@pytest.fixture
def tags_without_pet() -> list[str]:
    """Tags without pet info."""
    return ["近捷運", "有陽台", "有電梯"]


@pytest.fixture
def tags_empty() -> list[str]:
    """Empty tags list."""
    return []


# ============================================================
# Price Fixtures
# ============================================================


@pytest.fixture
def price_cases() -> list[tuple[str | None, int]]:
    """Test cases for price transformation: (input, expected)."""
    return [
        ("15,000", 15000),
        ("8000", 8000),
        ("1,234,567", 1234567),
        ("0", 0),
        (None, 0),
        ("", 0),
    ]


# ============================================================
# Floor Fixtures
# ============================================================


@pytest.fixture
def floor_cases() -> list[tuple[str | None, tuple]]:
    """Test cases for floor parsing: (input, (floor, total, is_rooftop))."""
    return [
        ("3F/10F", (3, 10, False)),
        ("1F/5F", (1, 5, False)),
        ("頂樓加蓋/5F", (6, 5, True)),
        ("B1/10F", (-1, 10, False)),
        ("整棟", (None, None, False)),
        (None, (None, None, False)),
    ]
