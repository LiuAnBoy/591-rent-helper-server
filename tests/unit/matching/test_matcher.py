"""
Unit tests for src/matching/matcher.py
"""

from src.matching.matcher import (
    extract_floor_number,
    match_floor,
    match_floor_quick,
    match_kind_quick,
    match_layout_quick,
    match_object_to_subscription,
    match_quick,
    match_region,
    match_section_quick,
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


class TestMatchRegion:
    """Tests for match_region function."""

    def test_no_filter_matches_all(self):
        """No region filter should match any object."""
        assert match_region(1, None) is True
        assert match_region("1", None) is True
        assert match_region(None, None) is True

    def test_matching_region(self):
        """Object with matching region should match."""
        assert match_region(1, 1) is True
        assert match_region("1", 1) is True

    def test_non_matching_region(self):
        """Object with different region should not match."""
        assert match_region(2, 1) is False
        assert match_region("2", 1) is False

    def test_none_region_matches(self):
        """None object region should match (conservative)."""
        assert match_region(None, 1) is True


class TestMatchSectionQuick:
    """Tests for match_section_quick function."""

    def test_no_filter_matches_all(self):
        """No section filter should match any object."""
        assert match_section_quick("5", None) is True
        assert match_section_quick("5", []) is True
        assert match_section_quick(None, None) is True

    def test_matching_section(self):
        """Object with matching section should match."""
        assert match_section_quick("5", ["5"]) is True
        assert match_section_quick("5", ["3", "5", "7"]) is True

    def test_non_matching_section(self):
        """Object with different section should not match."""
        assert match_section_quick("5", ["3"]) is False
        assert match_section_quick("5", ["3", "7"]) is False

    def test_none_section_matches(self):
        """None or empty section should match (conservative)."""
        assert match_section_quick(None, ["5"]) is True
        assert match_section_quick("", ["5"]) is True


class TestMatchKindQuick:
    """Tests for match_kind_quick function."""

    def test_no_filter_matches_all(self):
        """No kind filter should match any object."""
        assert match_kind_quick("整層住家", None) is True
        assert match_kind_quick("整層住家", []) is True

    def test_matching_kind(self):
        """Object with matching kind should match."""
        # 整層住家 = 1, 獨立套房 = 2, 分租套房 = 3, 雅房 = 4
        assert match_kind_quick("整層住家", [1]) is True
        assert match_kind_quick("獨立套房", [2]) is True
        assert match_kind_quick("整層住家", [1, 2, 3]) is True

    def test_non_matching_kind(self):
        """Object with different kind should not match."""
        assert match_kind_quick("整層住家", [2]) is False
        assert match_kind_quick("獨立套房", [1, 3, 4]) is False

    def test_none_kind_matches(self):
        """None or empty kind_name should match (conservative)."""
        assert match_kind_quick(None, [1]) is True
        assert match_kind_quick("", [1]) is True

    def test_unknown_kind_matches(self):
        """Unknown kind name should match (conservative)."""
        assert match_kind_quick("未知類型", [1]) is True


class TestMatchLayoutQuick:
    """Tests for match_layout_quick function."""

    def test_no_filter_matches_all(self):
        """No layout filter should match any object."""
        assert match_layout_quick("2房1廳", None) is True
        assert match_layout_quick("2房1廳", []) is True

    def test_matching_layout(self):
        """Object with matching layout should match."""
        assert match_layout_quick("2房1廳", [2]) is True
        assert match_layout_quick("3房2廳1衛", [3]) is True
        assert match_layout_quick("2房1廳", [1, 2, 3]) is True

    def test_non_matching_layout(self):
        """Object with different layout should not match."""
        assert match_layout_quick("2房1廳", [3]) is False
        assert match_layout_quick("3房2廳", [1, 2]) is False

    def test_4plus_layout(self):
        """Layout 4 should match 4+ rooms."""
        assert match_layout_quick("4房2廳", [4]) is True
        assert match_layout_quick("5房3廳", [4]) is True
        assert match_layout_quick("6房3廳", [4]) is True
        assert match_layout_quick("3房2廳", [4]) is False

    def test_none_layout_matches(self):
        """None or empty layout should match (套房/雅房)."""
        assert match_layout_quick(None, [2]) is True
        assert match_layout_quick("", [2]) is True


class TestMatchFloorQuick:
    """Tests for match_floor_quick function."""

    def test_no_filter_matches_all(self):
        """No floor filter should match any object."""
        assert match_floor_quick("3F/10F", None, None) is True
        assert match_floor_quick(None, None, None) is True

    def test_matching_floor(self):
        """Object with matching floor should match."""
        assert match_floor_quick("5F/10F", 3, 8) is True
        assert match_floor_quick("3F/10F", 3, 8) is True
        assert match_floor_quick("8F/10F", 3, 8) is True

    def test_floor_below_min(self):
        """Object with floor below min should not match."""
        assert match_floor_quick("2F/10F", 3, 8) is False

    def test_floor_above_max(self):
        """Object with floor above max should not match."""
        assert match_floor_quick("10F/10F", 3, 8) is False

    def test_basement_floor(self):
        """Basement floor should be treated as floor 0."""
        assert match_floor_quick("B1/5F", 1, 5) is False
        assert match_floor_quick("B1/5F", 0, 5) is True

    def test_floor_min_only(self):
        """Should work with only min filter."""
        assert match_floor_quick("5F/10F", 3, None) is True
        assert match_floor_quick("2F/10F", 3, None) is False

    def test_floor_max_only(self):
        """Should work with only max filter."""
        assert match_floor_quick("5F/10F", None, 8) is True
        assert match_floor_quick("10F/10F", None, 8) is False

    def test_none_floor_matches(self):
        """None or empty floor should match (conservative)."""
        assert match_floor_quick(None, 3, 8) is True
        assert match_floor_quick("", 3, 8) is True


class TestMatchQuickEnhanced:
    """Tests for enhanced match_quick with new filters."""

    def test_region_filter(self):
        """match_quick should filter by region."""
        obj = {"region": 1, "price": 15000, "area": 12.0}
        assert match_quick(obj, {"region": 1}) is True
        assert match_quick(obj, {"region": 2}) is False

    def test_section_filter(self):
        """match_quick should filter by section."""
        obj = {"section": "5", "price": 15000, "area": 12.0}
        assert match_quick(obj, {"section": ["5", "7"]}) is True
        assert match_quick(obj, {"section": ["3", "7"]}) is False

    def test_kind_filter_with_code(self):
        """match_quick should filter by kind code (DBReadyData)."""
        obj = {"kind": 1, "price": 15000, "area": 12.0}
        assert match_quick(obj, {"kind": [1]}) is True
        assert match_quick(obj, {"kind": [2, 3]}) is False

    def test_kind_filter_with_name(self):
        """match_quick should filter by kind_name (ListRawData)."""
        obj = {"kind_name": "整層住家", "price": 15000, "area": 12.0}
        assert match_quick(obj, {"kind": [1]}) is True
        assert match_quick(obj, {"kind": [2, 3]}) is False

    def test_layout_filter_with_value(self):
        """match_quick should filter by layout value (DBReadyData)."""
        obj = {"layout": 2, "price": 15000, "area": 12.0}
        assert match_quick(obj, {"layout": [2]}) is True
        assert match_quick(obj, {"layout": [3]}) is False

    def test_layout_filter_with_raw(self):
        """match_quick should filter by layout_raw (ListRawData)."""
        obj = {"layout_raw": "2房1廳", "price": 15000, "area": 12.0}
        assert match_quick(obj, {"layout": [2]}) is True
        assert match_quick(obj, {"layout": [3]}) is False

    def test_floor_filter_with_value(self):
        """match_quick should filter by floor value (DBReadyData)."""
        obj = {"floor": 5, "price": 15000, "area": 12.0}
        assert match_quick(obj, {"floor_min": 3, "floor_max": 8}) is True
        assert match_quick(obj, {"floor_min": 6}) is False

    def test_floor_filter_with_raw(self):
        """match_quick should filter by floor_raw (ListRawData)."""
        obj = {"floor_raw": "5F/10F", "price": 15000, "area": 12.0}
        assert match_quick(obj, {"floor_min": 3, "floor_max": 8}) is True
        assert match_quick(obj, {"floor_min": 6}) is False

    def test_all_filters_combined(self):
        """match_quick should apply all filters."""
        obj = {
            "region": 1,
            "section": "5",
            "kind_name": "整層住家",
            "layout_raw": "2房1廳",
            "floor_raw": "5F/10F",
            "price_raw": "15,000元/月",
            "area_raw": "12坪",
        }
        sub = {
            "region": 1,
            "section": ["5"],
            "kind": [1],
            "layout": [2],
            "floor_min": 3,
            "floor_max": 8,
            "price_min": 10000,
            "price_max": 20000,
            "area_min": 10,
            "area_max": 15,
        }
        assert match_quick(obj, sub) is True

    def test_fails_on_first_mismatch(self):
        """match_quick should fail fast on first mismatch."""
        obj = {
            "region": 2,  # Wrong region
            "section": "5",
            "kind_name": "整層住家",
            "price": 15000,
        }
        sub = {"region": 1, "section": ["5"], "kind": [1]}
        assert match_quick(obj, sub) is False
