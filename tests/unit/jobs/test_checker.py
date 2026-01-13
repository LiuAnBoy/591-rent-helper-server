"""
Unit tests for src/jobs/checker.py
"""

import pytest

from src.jobs.checker import Checker

# Import fixtures
pytest_plugins = ["tests.fixtures.checker"]


# ============================================================
# Checker instance for testing pure methods
# ============================================================


@pytest.fixture
def checker():
    """Create a Checker instance for testing pure methods."""
    return Checker(enable_broadcast=False)


# ============================================================
# _match_object_to_subscription tests
# ============================================================


class TestMatchObjectToSubscription:
    """Tests for _match_object_to_subscription method."""

    def test_basic_match(self, checker, checker_sample_object, checker_sample_subscription):
        """Object should match subscription with basic criteria."""
        result = checker._match_object_to_subscription(checker_sample_object, checker_sample_subscription)
        assert result is True

    def test_price_in_range(self, checker, checker_sample_object):
        """Object with price in range should match."""
        sub = {"price_min": 10000, "price_max": 20000}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_price_below_min(self, checker, checker_sample_object):
        """Object with price below min should not match."""
        sub = {"price_min": 20000}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_price_above_max(self, checker, checker_sample_object):
        """Object with price above max should not match."""
        sub = {"price_max": 10000}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_kind_match(self, checker, checker_sample_object):
        """Object with matching kind should match."""
        sub = {"kind": [1, 2, 3]}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_kind_no_match(self, checker, checker_sample_object):
        """Object with non-matching kind should not match."""
        sub = {"kind": [1, 3]}  # 整層 or 分套, not 獨套
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_section_match(self, checker, checker_sample_object):
        """Object with matching section should match."""
        sub = {"section": [7, 8]}  # 信義區 or 松山區
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_section_no_match(self, checker, checker_sample_object):
        """Object with non-matching section should not match."""
        sub = {"section": [1, 2]}  # 中正區 or 大同區
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_shape_match(self, checker, checker_sample_object):
        """Object with matching shape should match."""
        sub = {"shape": [2]}  # 電梯大樓
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_shape_no_match(self, checker, checker_sample_object):
        """Object with non-matching shape should not match."""
        sub = {"shape": [1, 3]}  # 公寓 or 透天厝
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_area_in_range(self, checker, checker_sample_object):
        """Object with area in range should match."""
        sub = {"area_min": 8, "area_max": 15}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_area_below_min(self, checker, checker_sample_object):
        """Object with area below min should not match."""
        sub = {"area_min": 12}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_area_above_max(self, checker, checker_sample_object):
        """Object with area above max should not match."""
        sub = {"area_max": 8}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_layout_match(self, checker, checker_sample_object):
        """Object with matching layout should match."""
        sub = {"layout": [1, 2, 3]}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_layout_no_match(self, checker, checker_sample_object):
        """Object with non-matching layout should not match."""
        sub = {"layout": [3, 4]}  # 3房 or 4房+
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_layout_4plus_match(self, checker, checker_sample_object):
        """Layout 4 means 4+ rooms."""
        obj = {**checker_sample_object, "layout": 5}
        sub = {"layout": [4]}  # 4房以上
        assert checker._match_object_to_subscription(obj, sub) is True

    def test_bathroom_match(self, checker, checker_sample_object):
        """Object with matching bathroom should match."""
        sub = {"bathroom": [1, 2]}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_bathroom_no_match(self, checker, checker_sample_object):
        """Object with non-matching bathroom should not match."""
        sub = {"bathroom": [2, 3]}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_floor_in_range(self, checker, checker_sample_object):
        """Object with floor in range should match."""
        sub = {"floor_min": 2, "floor_max": 10}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_floor_below_min(self, checker, checker_sample_object):
        """Object with floor below min should not match."""
        sub = {"floor_min": 5}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_floor_above_max(self, checker, checker_sample_object):
        """Object with floor above max should not match."""
        sub = {"floor_max": 2}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_fitment_match(self, checker, checker_sample_object):
        """Object with matching fitment should match."""
        sub = {"fitment": [99, 4]}  # 新裝潢 or 高檔裝潢
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_fitment_no_match(self, checker, checker_sample_object):
        """Object with non-matching fitment should not match."""
        sub = {"fitment": [3, 4]}  # 中檔裝潢 or 高檔裝潢
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_exclude_rooftop_filters_rooftop(self, checker, checker_sample_object):
        """Rooftop object should be filtered when exclude_rooftop is True."""
        obj = {**checker_sample_object, "is_rooftop": True}
        sub = {"exclude_rooftop": True}
        assert checker._match_object_to_subscription(obj, sub) is False

    def test_exclude_rooftop_allows_normal(self, checker, checker_sample_object):
        """Normal object should pass when exclude_rooftop is True."""
        sub = {"exclude_rooftop": True}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_gender_boy_matches_boy(self, checker, checker_sample_object):
        """Male subscription matches male-only object."""
        obj = {**checker_sample_object, "gender": "boy"}
        sub = {"gender": "boy"}
        assert checker._match_object_to_subscription(obj, sub) is True

    def test_gender_boy_matches_all(self, checker, checker_sample_object):
        """Male subscription matches all-gender object."""
        obj = {**checker_sample_object, "gender": "all"}
        sub = {"gender": "boy"}
        assert checker._match_object_to_subscription(obj, sub) is True

    def test_gender_boy_not_matches_girl(self, checker, checker_sample_object):
        """Male subscription does not match female-only object."""
        obj = {**checker_sample_object, "gender": "girl"}
        sub = {"gender": "boy"}
        assert checker._match_object_to_subscription(obj, sub) is False

    def test_gender_girl_matches_girl(self, checker, checker_sample_object):
        """Female subscription matches female-only object."""
        obj = {**checker_sample_object, "gender": "girl"}
        sub = {"gender": "girl"}
        assert checker._match_object_to_subscription(obj, sub) is True

    def test_pet_required_matches_pet_allowed(self, checker, checker_sample_object):
        """Pet required subscription matches pet-allowed object."""
        sub = {"pet_required": True}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_pet_required_not_matches_no_pet(self, checker, checker_sample_object):
        """Pet required subscription does not match no-pet object."""
        obj = {**checker_sample_object, "pet_allowed": False}
        sub = {"pet_required": True}
        assert checker._match_object_to_subscription(obj, sub) is False

    def test_other_features_match(self, checker, checker_sample_object):
        """Object with required features should match."""
        sub = {"other": ["near_subway"]}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_other_features_no_match(self, checker, checker_sample_object):
        """Object without required features should not match."""
        sub = {"other": ["parking"]}  # 車位
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_options_match(self, checker, checker_sample_object):
        """Object with required options should match."""
        sub = {"options": ["cold", "washer"]}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_options_no_match(self, checker, checker_sample_object):
        """Object without required options should not match."""
        sub = {"options": ["tv", "sofa"]}  # 電視, 沙發
        assert checker._match_object_to_subscription(checker_sample_object, sub) is False

    def test_checker_strict_subscription_match(self, checker, checker_sample_object, checker_strict_subscription):
        """Object should match strict subscription when all criteria met."""
        result = checker._match_object_to_subscription(checker_sample_object, checker_strict_subscription)
        assert result is True

    def test_empty_subscription_matches_all(self, checker, checker_sample_object):
        """Empty subscription should match any object."""
        sub = {}
        assert checker._match_object_to_subscription(checker_sample_object, sub) is True

    def test_none_values_in_object(self, checker):
        """Object with None price raises TypeError (known limitation)."""
        obj = {
            "id": 123,
            "price": None,
            "kind": None,
            "section": None,
            "floor": None,
            "gender": None,
            "pet_allowed": None,
        }
        sub = {"price_min": 10000}
        # Note: Current implementation raises TypeError when price is None
        # This is a known limitation - objects should always have valid price
        with pytest.raises(TypeError):
            checker._match_object_to_subscription(obj, sub)


# ============================================================
# _match_floor tests
# ============================================================


class TestMatchFloor:
    """Tests for _match_floor method."""

    def test_floor_in_range(self, checker):
        """Floor in range should match."""
        assert checker._match_floor(5, floor_min=2, floor_max=10) is True

    def test_floor_at_min(self, checker):
        """Floor at min should match."""
        assert checker._match_floor(2, floor_min=2, floor_max=10) is True

    def test_floor_at_max(self, checker):
        """Floor at max should match."""
        assert checker._match_floor(10, floor_min=2, floor_max=10) is True

    def test_floor_below_min(self, checker):
        """Floor below min should not match."""
        assert checker._match_floor(1, floor_min=2, floor_max=10) is False

    def test_floor_above_max(self, checker):
        """Floor above max should not match."""
        assert checker._match_floor(11, floor_min=2, floor_max=10) is False

    def test_floor_min_only(self, checker):
        """Floor with only min should match if above."""
        assert checker._match_floor(5, floor_min=2, floor_max=None) is True
        assert checker._match_floor(1, floor_min=2, floor_max=None) is False

    def test_floor_max_only(self, checker):
        """Floor with only max should match if below."""
        assert checker._match_floor(5, floor_min=None, floor_max=10) is True
        assert checker._match_floor(11, floor_min=None, floor_max=10) is False

    def test_floor_none_matches_all(self, checker):
        """None floor should match any range."""
        assert checker._match_floor(None, floor_min=2, floor_max=10) is True

    def test_no_range_matches_all(self, checker):
        """No range should match any floor."""
        assert checker._match_floor(5, floor_min=None, floor_max=None) is True

    def test_basement_floor(self, checker):
        """Basement floor (negative) should match properly."""
        assert checker._match_floor(-1, floor_min=-2, floor_max=2) is True
        assert checker._match_floor(-1, floor_min=1, floor_max=10) is False


# ============================================================
# _extract_floor_number tests
# ============================================================


class TestExtractFloorNumber:
    """Tests for _extract_floor_number method."""

    def test_normal_floor(self, checker):
        """Normal floor string should extract correctly."""
        assert checker._extract_floor_number("3F/10F") == 3

    def test_first_floor(self, checker):
        """First floor should extract correctly."""
        assert checker._extract_floor_number("1F/5F") == 1

    def test_high_floor(self, checker):
        """High floor should extract correctly."""
        assert checker._extract_floor_number("25F/30F") == 25

    def test_basement_b1(self, checker):
        """B1 should return 0."""
        assert checker._extract_floor_number("B1/10F") == 0

    def test_basement_b2(self, checker):
        """B2 should return 0."""
        assert checker._extract_floor_number("B2/8F") == 0

    def test_lowercase_b(self, checker):
        """Lowercase b should work."""
        assert checker._extract_floor_number("b1/10F") == 0

    def test_no_number(self, checker):
        """String without number should return None."""
        assert checker._extract_floor_number("頂樓加蓋") is None

    def test_empty_string(self, checker):
        """Empty string should return None."""
        assert checker._extract_floor_number("") is None
