"""
Mock data fixtures for formatter tests.
"""

import pytest


@pytest.fixture
def sample_db_ready_object():
    """Sample DBReadyData object for formatting tests."""
    return {
        "id": 12345678,
        "url": "https://rent.591.com.tw/12345678",
        "title": "台北市信義區精緻套房",
        "price": 15000,
        "kind_name": "獨立套房",
        "area": 10.5,
        "layout_str": "2房1廳1衛",
        "floor_str": "3F/10F",
        "address": "台北市信義區信義路五段",
        "surrounding_desc": "信義安和站",
        "surrounding_distance": 353,
        "tags": ["近捷運", "可養寵物", "有陽台"],
    }


@pytest.fixture
def minimal_object():
    """Minimal object with only required fields."""
    return {
        "id": 123,
        "url": "https://rent.591.com.tw/123",
        "title": "測試物件",
        "price": 0,
    }


@pytest.fixture
def object_with_special_chars():
    """Object with HTML special characters."""
    return {
        "id": 456,
        "url": "https://rent.591.com.tw/456",
        "title": "測試 <script>alert('XSS')</script> 物件",
        "price": 10000,
        "address": "台北市 & 新北市",
    }
