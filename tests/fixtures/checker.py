"""
Mock data fixtures for checker tests.
"""

import pytest


@pytest.fixture
def checker_sample_object():
    """Sample object for matching tests."""
    return {
        "id": 12345678,
        "title": "台北市信義區套房",
        "price": 15000,
        "kind": 2,  # 獨立套房
        "section": 7,  # 信義區
        "shape": 2,  # 電梯大樓
        "area": 10.5,
        "layout": 2,  # 2房
        "bathroom": 1,
        "floor": 3,
        "is_rooftop": False,
        "fitment": 99,  # 新裝潢
        "gender": "all",
        "pet_allowed": True,
        "other": ["near_subway", "balcony"],
        "options": ["cold", "washer", "icebox"],
    }


@pytest.fixture
def checker_sample_subscription():
    """Sample subscription for matching tests."""
    return {
        "id": 1,
        "region": 1,
        "price_min": 10000,
        "price_max": 20000,
        "kind": [1, 2],  # 整層 or 獨套
        "section": [7, 8],  # 信義區 or 松山區
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


@pytest.fixture
def checker_strict_subscription():
    """Subscription with all criteria set."""
    return {
        "id": 2,
        "region": 1,
        "price_min": 12000,
        "price_max": 18000,
        "kind": [2],  # 獨套 only
        "section": [7],  # 信義區 only
        "shape": [2],  # 電梯大樓 only
        "area_min": 8,
        "area_max": 15,
        "layout": [2, 3],  # 2-3房
        "bathroom": [1, 2],
        "floor_min": 2,
        "floor_max": 10,
        "fitment": [99, 4],  # 新裝潢 or 高檔裝潢
        "exclude_rooftop": True,
        "gender": None,
        "pet_required": True,
        "other": ["near_subway"],
        "options": ["cold"],
    }
