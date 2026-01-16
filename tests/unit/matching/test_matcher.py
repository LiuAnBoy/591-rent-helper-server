"""
Unit tests for src/matching/matcher.py
"""

import pytest

from src.matching.matcher import (
    extract_floor_number,
    match_floor,
    match_object_to_subscription,
    match_quick,
    parse_area_value,
    parse_price_value,
)

# Import fixtures
pytest_plugins = ["tests.fixtures.checker"]


# ============================================================
# extract_floor_number tests
# ============================================================


class TestExtractFloorNumber:
    """Tests for extract_floor_number function."""

    def test_normal_floor(self):
        """Normal floor string should extract correctly."""
        assert extract_floor_number("3F/10F") == 3

    def test_first_floor(self):
        """First floor should extract correctly."""
        assert extract_floor_number("1F/5F") == 1

    def test_high_floor(self):
        """High floor should extract correctly."""
        assert extract_floor_number("25F/30F") == 25

    def test_basement_b1(self):
        """B1 should return 0."""
        assert extract_floor_number("B1/10F") == 0

    def test_basement_b2(self):
        """B2 should return 0."""
        assert extract_floor_number("B2/8F") == 0

    def test_lowercase_b(self):
        """Lowercase b should work."""
        assert extract_floor_number("b1/10F") == 0

    def test_no_number(self):
        """String without number should return None."""
        assert extract_floor_number("頂樓加蓋") is None

    def test_empty_string(self):
        """Empty string should return None."""
        assert extract_floor_number("") is None


# ============================================================
# match_floor tests
# ============================================================


class TestMatchFloor:
    """Tests for match_floor function."""

    def test_floor_in_range(self):
        """Floor in range should match."""
        assert match_floor(5, floor_min=2, floor_max=10) is True

    def test_floor_at_min(self):
        """Floor at min should match."""
        assert match_floor(2, floor_min=2, floor_max=10) is True

    def test_floor_at_max(self):
        """Floor at max should match."""
        assert match_floor(10, floor_min=2, floor_max=10) is True

    def test_floor_below_min(self):
        """Floor below min should not match."""
        assert match_floor(1, floor_min=2, floor_max=10) is False

    def test_floor_above_max(self):
        """Floor above max should not match."""
        assert match_floor(11, floor_min=2, floor_max=10) is False

    def test_floor_min_only(self):
        """Floor with only min should match if above."""
        assert match_floor(5, floor_min=2, floor_max=None) is True
        assert match_floor(1, floor_min=2, floor_max=None) is False

    def test_floor_max_only(self):
        """Floor with only max should match if below."""
        assert match_floor(5, floor_min=None, floor_max=10) is True
        assert match_floor(11, floor_min=None, floor_max=10) is False

    def test_floor_none_matches_all(self):
        """None floor should match any range."""
        assert match_floor(None, floor_min=2, floor_max=10) is True

    def test_no_range_matches_all(self):
        """No range should match any floor."""
        assert match_floor(5, floor_min=None, floor_max=None) is True

    def test_basement_floor(self):
        """Basement floor (negative) should match properly."""
        assert match_floor(-1, floor_min=-2, floor_max=2) is True
        assert match_floor(-1, floor_min=1, floor_max=10) is False


# ============================================================
# match_object_to_subscription tests
# ============================================================


class TestMatchObjectToSubscription:
    """Tests for match_object_to_subscription function."""

    def test_basic_match(self, checker_sample_object, checker_sample_subscription):
        """Object should match subscription with basic criteria."""
        result = match_object_to_subscription(
            checker_sample_object, checker_sample_subscription
        )
        assert result is True

    def test_price_in_range(self, checker_sample_object):
        """Object with price in range should match."""
        sub = {"price_min": 10000, "price_max": 20000}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_price_below_min(self, checker_sample_object):
        """Object with price below min should not match."""
        sub = {"price_min": 20000}
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_price_above_max(self, checker_sample_object):
        """Object with price above max should not match."""
        sub = {"price_max": 10000}
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_kind_match(self, checker_sample_object):
        """Object with matching kind should match."""
        sub = {"kind": [1, 2, 3]}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_kind_no_match(self, checker_sample_object):
        """Object with non-matching kind should not match."""
        sub = {"kind": [1, 3]}  # 整層 or 分套, not 獨套
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_section_match(self, checker_sample_object):
        """Object with matching section should match."""
        sub = {"section": [7, 8]}  # 信義區 or 松山區
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_section_no_match(self, checker_sample_object):
        """Object with non-matching section should not match."""
        sub = {"section": [1, 2]}  # 中正區 or 大同區
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_shape_match(self, checker_sample_object):
        """Object with matching shape should match."""
        sub = {"shape": [2]}  # 電梯大樓
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_shape_no_match(self, checker_sample_object):
        """Object with non-matching shape should not match."""
        sub = {"shape": [1, 3]}  # 公寓 or 透天厝
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_area_in_range(self, checker_sample_object):
        """Object with area in range should match."""
        sub = {"area_min": 8, "area_max": 15}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_area_below_min(self, checker_sample_object):
        """Object with area below min should not match."""
        sub = {"area_min": 12}
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_area_above_max(self, checker_sample_object):
        """Object with area above max should not match."""
        sub = {"area_max": 8}
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_layout_match(self, checker_sample_object):
        """Object with matching layout should match."""
        sub = {"layout": [1, 2, 3]}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_layout_no_match(self, checker_sample_object):
        """Object with non-matching layout should not match."""
        sub = {"layout": [3, 4]}  # 3房 or 4房+
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_layout_4plus_match(self, checker_sample_object):
        """Layout 4 means 4+ rooms."""
        obj = {**checker_sample_object, "layout": 5}
        sub = {"layout": [4]}  # 4房以上
        assert match_object_to_subscription(obj, sub) is True

    def test_bathroom_match(self, checker_sample_object):
        """Object with matching bathroom should match."""
        sub = {"bathroom": [1, 2]}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_bathroom_no_match(self, checker_sample_object):
        """Object with non-matching bathroom should not match."""
        sub = {"bathroom": [2, 3]}
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_floor_in_range(self, checker_sample_object):
        """Object with floor in range should match."""
        sub = {"floor_min": 2, "floor_max": 10}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_floor_below_min(self, checker_sample_object):
        """Object with floor below min should not match."""
        sub = {"floor_min": 5}
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_floor_above_max(self, checker_sample_object):
        """Object with floor above max should not match."""
        sub = {"floor_max": 2}
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_fitment_match(self, checker_sample_object):
        """Object with matching fitment should match."""
        sub = {"fitment": [99, 4]}  # 新裝潢 or 高檔裝潢
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_fitment_no_match(self, checker_sample_object):
        """Object with non-matching fitment should not match."""
        sub = {"fitment": [3, 4]}  # 中檔裝潢 or 高檔裝潢
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_exclude_rooftop_filters_rooftop(self, checker_sample_object):
        """Rooftop object should be filtered when exclude_rooftop is True."""
        obj = {**checker_sample_object, "is_rooftop": True}
        sub = {"exclude_rooftop": True}
        assert match_object_to_subscription(obj, sub) is False

    def test_exclude_rooftop_allows_normal(self, checker_sample_object):
        """Normal object should pass when exclude_rooftop is True."""
        sub = {"exclude_rooftop": True}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_gender_boy_matches_boy(self, checker_sample_object):
        """Male subscription matches male-only object."""
        obj = {**checker_sample_object, "gender": "boy"}
        sub = {"gender": "boy"}
        assert match_object_to_subscription(obj, sub) is True

    def test_gender_boy_matches_all(self, checker_sample_object):
        """Male subscription matches all-gender object."""
        obj = {**checker_sample_object, "gender": "all"}
        sub = {"gender": "boy"}
        assert match_object_to_subscription(obj, sub) is True

    def test_gender_boy_not_matches_girl(self, checker_sample_object):
        """Male subscription does not match female-only object."""
        obj = {**checker_sample_object, "gender": "girl"}
        sub = {"gender": "boy"}
        assert match_object_to_subscription(obj, sub) is False

    def test_gender_girl_matches_girl(self, checker_sample_object):
        """Female subscription matches female-only object."""
        obj = {**checker_sample_object, "gender": "girl"}
        sub = {"gender": "girl"}
        assert match_object_to_subscription(obj, sub) is True

    def test_pet_required_matches_pet_allowed(self, checker_sample_object):
        """Pet required subscription matches pet-allowed object."""
        sub = {"pet_required": True}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_pet_required_not_matches_no_pet(self, checker_sample_object):
        """Pet required subscription does not match no-pet object."""
        obj = {**checker_sample_object, "pet_allowed": False}
        sub = {"pet_required": True}
        assert match_object_to_subscription(obj, sub) is False

    def test_other_features_match(self, checker_sample_object):
        """Object with required features should match."""
        sub = {"other": ["near_subway"]}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_other_features_no_match(self, checker_sample_object):
        """Object without required features should not match."""
        sub = {"other": ["parking"]}  # 車位
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_options_match(self, checker_sample_object):
        """Object with required options should match."""
        sub = {"options": ["cold", "washer"]}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_options_no_match(self, checker_sample_object):
        """Object without required options should not match."""
        sub = {"options": ["tv", "sofa"]}  # 電視, 沙發
        assert match_object_to_subscription(checker_sample_object, sub) is False

    def test_strict_subscription_match(
        self, checker_sample_object, checker_strict_subscription
    ):
        """Object should match strict subscription when all criteria met."""
        result = match_object_to_subscription(
            checker_sample_object, checker_strict_subscription
        )
        assert result is True

    def test_empty_subscription_matches_all(self, checker_sample_object):
        """Empty subscription should match any object."""
        sub = {}
        assert match_object_to_subscription(checker_sample_object, sub) is True

    def test_none_values_in_object(self):
        """Object with None price should match (conservative approach)."""
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
        # None price cannot be compared, so we assume match (conservative)
        assert match_object_to_subscription(obj, sub) is True


# ============================================================
# parse_price_value tests
# ============================================================


class TestParsePriceValue:
    """Tests for parse_price_value function."""

    def test_integer_input(self):
        """Integer input should return as-is."""
        assert parse_price_value(10000) == 10000

    def test_simple_string(self):
        """Simple number string should parse."""
        assert parse_price_value("10000") == 10000

    def test_string_with_commas(self):
        """String with commas should parse."""
        assert parse_price_value("10,000") == 10000

    def test_string_with_unit(self):
        """String with unit should parse."""
        assert parse_price_value("8,500元/月") == 8500

    def test_range_takes_lower(self):
        """Range should return lower bound."""
        assert parse_price_value("15000-20000元/月") == 15000
        assert parse_price_value("15,000~20,000") == 15000

    def test_negotiable_returns_none(self):
        """Negotiable price returns None."""
        assert parse_price_value("面議") is None

    def test_none_input(self):
        """None input returns None."""
        assert parse_price_value(None) is None

    def test_empty_string(self):
        """Empty string returns None."""
        assert parse_price_value("") is None


# ============================================================
# parse_area_value tests
# ============================================================


class TestParseAreaValue:
    """Tests for parse_area_value function."""

    def test_float_input(self):
        """Float input should return as-is."""
        assert parse_area_value(25.5) == 25.5

    def test_int_input(self):
        """Int input should return as float."""
        assert parse_area_value(10) == 10.0

    def test_simple_string(self):
        """Simple number string should parse."""
        assert parse_area_value("25.5") == 25.5

    def test_string_with_unit(self):
        """String with unit should parse."""
        assert parse_area_value("25.5坪") == 25.5

    def test_string_with_prefix(self):
        """String with prefix should parse."""
        assert parse_area_value("約10坪") == 10.0

    def test_range_takes_lower(self):
        """Range should return lower bound."""
        assert parse_area_value("10~15坪") == 10.0
        assert parse_area_value("10-15坪") == 10.0

    def test_none_input(self):
        """None input returns None."""
        assert parse_area_value(None) is None

    def test_empty_string(self):
        """Empty string returns None."""
        assert parse_area_value("") is None


# ============================================================
# match_quick tests
# ============================================================


class TestMatchQuick:
    """Tests for match_quick function."""

    def test_empty_subscription_matches(self):
        """Empty subscription should match any object."""
        obj = {"price": 15000, "area": 10.0}
        assert match_quick(obj, {}) is True

    def test_price_in_range(self):
        """Object with price in range should match."""
        obj = {"price": 15000}
        sub = {"price_min": 10000, "price_max": 20000}
        assert match_quick(obj, sub) is True

    def test_price_below_min(self):
        """Object with price below min should not match."""
        obj = {"price": 8000}
        sub = {"price_min": 10000}
        assert match_quick(obj, sub) is False

    def test_price_above_max(self):
        """Object with price above max should not match."""
        obj = {"price": 25000}
        sub = {"price_max": 20000}
        assert match_quick(obj, sub) is False

    def test_area_in_range(self):
        """Object with area in range should match."""
        obj = {"area": 12.0}
        sub = {"area_min": 10, "area_max": 15}
        assert match_quick(obj, sub) is True

    def test_area_below_min(self):
        """Object with area below min should not match."""
        obj = {"area": 8.0}
        sub = {"area_min": 10}
        assert match_quick(obj, sub) is False

    def test_area_above_max(self):
        """Object with area above max should not match."""
        obj = {"area": 20.0}
        sub = {"area_max": 15}
        assert match_quick(obj, sub) is False

    def test_raw_price_string(self):
        """Should handle raw price string from list data."""
        obj = {"price_raw": "15,000元/月"}
        sub = {"price_min": 10000, "price_max": 20000}
        assert match_quick(obj, sub) is True

    def test_raw_area_string(self):
        """Should handle raw area string from list data."""
        obj = {"area_raw": "約12坪"}
        sub = {"area_min": 10, "area_max": 15}
        assert match_quick(obj, sub) is True

    def test_combined_criteria(self):
        """Should check both price and area."""
        obj = {"price": 15000, "area": 12.0}
        sub = {"price_min": 10000, "price_max": 20000, "area_min": 10, "area_max": 15}
        assert match_quick(obj, sub) is True

    def test_fails_if_either_fails(self):
        """Should fail if either price or area fails."""
        obj = {"price": 15000, "area": 20.0}  # area too large
        sub = {"price_min": 10000, "price_max": 20000, "area_max": 15}
        assert match_quick(obj, sub) is False

    def test_none_price_matches(self):
        """None price should match (conservative)."""
        obj = {"price": None, "area": 12.0}
        sub = {"price_min": 10000}
        assert match_quick(obj, sub) is True

    def test_none_area_matches(self):
        """None area should match (conservative)."""
        obj = {"price": 15000, "area": None}
        sub = {"area_min": 10}
        assert match_quick(obj, sub) is True
