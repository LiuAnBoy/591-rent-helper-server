"""
Unit tests for src/utils/parsers/
"""

import pytest

from src.utils.parsers.floor import parse_floor, parse_is_rooftop
from src.utils.parsers.layout import (
    parse_layout_str,
    parse_layout_num,
    parse_bathroom_num,
)
from src.utils.parsers.rule import parse_rule
from src.utils.parsers.shape import parse_shape, get_shape_name
from src.utils.parsers.fitment import parse_fitment


# ============================================================
# parse_floor tests
# ============================================================


class TestParseFloor:
    """Tests for parse_floor function."""

    def test_normal_floor(self):
        floor, total, is_rooftop = parse_floor("3F/5F")
        assert floor == 3
        assert total == 5
        assert is_rooftop is False

    def test_first_floor(self):
        floor, total, is_rooftop = parse_floor("1F/10F")
        assert floor == 1
        assert total == 10
        assert is_rooftop is False

    def test_top_floor(self):
        floor, total, is_rooftop = parse_floor("10F/10F")
        assert floor == 10
        assert total == 10
        assert is_rooftop is False

    def test_rooftop_addition(self):
        floor, total, is_rooftop = parse_floor("頂層加蓋/5F")
        assert floor == 0
        assert total == 5
        assert is_rooftop is True

    def test_rooftop_variant(self):
        floor, total, is_rooftop = parse_floor("頂樓加蓋/4F")
        assert floor == 0
        assert total == 4
        assert is_rooftop is True

    def test_basement_b1(self):
        floor, total, is_rooftop = parse_floor("B1/10F")
        assert floor == -1
        assert total == 10
        assert is_rooftop is False

    def test_basement_b2(self):
        floor, total, is_rooftop = parse_floor("B2/8F")
        assert floor == -2
        assert total == 8
        assert is_rooftop is False

    def test_whole_building(self):
        floor, total, is_rooftop = parse_floor("整棟")
        assert floor is None
        assert total is None
        assert is_rooftop is False

    def test_none_input(self):
        floor, total, is_rooftop = parse_floor(None)
        assert floor is None
        assert total is None
        assert is_rooftop is False

    def test_empty_string(self):
        floor, total, is_rooftop = parse_floor("")
        assert floor is None
        assert total is None
        assert is_rooftop is False

    def test_lowercase_f(self):
        floor, total, is_rooftop = parse_floor("3f/5f")
        assert floor == 3
        assert total == 5


# ============================================================
# parse_is_rooftop tests
# ============================================================


class TestParseIsRooftop:
    """Tests for parse_is_rooftop function."""

    def test_rooftop_type1(self):
        assert parse_is_rooftop("頂層加蓋/4F") is True

    def test_rooftop_type2(self):
        assert parse_is_rooftop("頂樓加蓋/4F") is True

    def test_normal_floor(self):
        assert parse_is_rooftop("4F/5F") is False

    def test_none_input(self):
        assert parse_is_rooftop(None) is False

    def test_empty_string(self):
        assert parse_is_rooftop("") is False

    def test_partial_match_no_roof(self):
        # Has "頂" but no "加蓋"
        assert parse_is_rooftop("頂樓/5F") is False


# ============================================================
# parse_layout_str tests
# ============================================================


class TestParseLayoutStr:
    """Tests for parse_layout_str function."""

    def test_full_layout(self):
        assert parse_layout_str("2房1廳1衛") == "2房1廳1衛"

    def test_layout_in_text(self):
        result = parse_layout_str("這是一間3房2廳2衛的房子")
        assert result == "3房2廳2衛"

    def test_room_only(self):
        assert parse_layout_str("1房") == "1房"

    def test_room_and_hall(self):
        assert parse_layout_str("2房1廳") == "2房1廳"

    def test_none_input(self):
        assert parse_layout_str(None) is None

    def test_empty_string(self):
        assert parse_layout_str("") is None

    def test_no_layout_match(self):
        assert parse_layout_str("開放格局") is None


# ============================================================
# parse_layout_num tests
# ============================================================


class TestParseLayoutNum:
    """Tests for parse_layout_num function."""

    def test_full_layout(self):
        assert parse_layout_num("2房1廳1衛") == 2

    def test_studio(self):
        assert parse_layout_num("1房1衛") == 1

    def test_large_layout(self):
        assert parse_layout_num("5房3廳3衛") == 5

    def test_none_input(self):
        assert parse_layout_num(None) is None

    def test_empty_string(self):
        assert parse_layout_num("") is None

    def test_no_room_match(self):
        assert parse_layout_num("開放格局") is None


# ============================================================
# parse_bathroom_num tests
# ============================================================


class TestParseBathroomNum:
    """Tests for parse_bathroom_num function."""

    def test_full_layout(self):
        assert parse_bathroom_num("2房1廳1衛") == 1

    def test_multiple_bathrooms(self):
        assert parse_bathroom_num("3房2廳2衛") == 2

    def test_no_bathroom_in_string(self):
        # "1房" has no bathroom info
        assert parse_bathroom_num("1房") is None

    def test_none_input(self):
        assert parse_bathroom_num(None) is None

    def test_empty_string(self):
        assert parse_bathroom_num("") is None


# ============================================================
# parse_rule tests
# ============================================================


class TestParseRule:
    """Tests for parse_rule function."""

    def test_male_only(self):
        result = parse_rule("限男生")
        assert result["gender"] == "boy"
        assert result["pet_allowed"] is False

    def test_female_only(self):
        result = parse_rule("限女生")
        assert result["gender"] == "girl"
        assert result["pet_allowed"] is False

    def test_all_gender(self):
        result = parse_rule("男女皆可")
        assert result["gender"] == "all"
        assert result["pet_allowed"] is False

    def test_pet_allowed(self):
        result = parse_rule("可養寵物")
        assert result["gender"] == "all"
        assert result["pet_allowed"] is True

    def test_male_with_pet(self):
        result = parse_rule("限男生，可養寵物")
        assert result["gender"] == "boy"
        assert result["pet_allowed"] is True

    def test_female_with_pet(self):
        result = parse_rule("限女生，可養寵物")
        assert result["gender"] == "girl"
        assert result["pet_allowed"] is True

    def test_none_input(self):
        result = parse_rule(None)
        assert result["gender"] == "all"
        assert result["pet_allowed"] is False

    def test_empty_string(self):
        result = parse_rule("")
        assert result["gender"] == "all"
        assert result["pet_allowed"] is False


# ============================================================
# parse_shape tests
# ============================================================


class TestParseShape:
    """Tests for parse_shape function."""

    def test_apartment(self):
        assert parse_shape("公寓") == 1

    def test_elevator_building(self):
        assert parse_shape("電梯大樓") == 2

    def test_townhouse(self):
        assert parse_shape("透天厝") == 3

    def test_townhouse_short(self):
        assert parse_shape("透天") == 3

    def test_villa(self):
        assert parse_shape("別墅") == 4

    def test_shape_in_text(self):
        assert parse_shape("這是一間電梯大樓的套房") == 2

    def test_unknown_shape(self):
        assert parse_shape("未知類型") is None

    def test_none_input(self):
        assert parse_shape(None) is None

    def test_empty_string(self):
        assert parse_shape("") is None


# ============================================================
# get_shape_name tests
# ============================================================


class TestGetShapeName:
    """Tests for get_shape_name function."""

    def test_apartment_code(self):
        # Code 1 maps to "公寓"
        assert get_shape_name(1) == "公寓"

    def test_elevator_code(self):
        assert get_shape_name(2) == "電梯大樓"

    def test_townhouse_code(self):
        # Code 3 might map to "透天厝" or "透天" depending on dict order
        result = get_shape_name(3)
        assert result in ["透天厝", "透天"]

    def test_villa_code(self):
        assert get_shape_name(4) == "別墅"

    def test_none_code(self):
        assert get_shape_name(None) is None

    def test_unknown_code(self):
        assert get_shape_name(99) is None


# ============================================================
# parse_fitment tests
# ============================================================


class TestParseFitment:
    """Tests for parse_fitment function."""

    def test_new_decoration(self):
        assert parse_fitment("新裝潢") == 99

    def test_within_three_years(self):
        assert parse_fitment("三年內") == 99

    def test_mid_range(self):
        assert parse_fitment("中檔") == 3

    def test_mid_range_full(self):
        assert parse_fitment("中檔裝潢") == 3

    def test_high_end(self):
        assert parse_fitment("高檔") == 4

    def test_high_end_full(self):
        assert parse_fitment("高檔裝潢") == 4

    def test_luxury(self):
        assert parse_fitment("豪華裝潢") == 4

    def test_fitment_in_text(self):
        assert parse_fitment("這是新裝潢的房子") == 99

    def test_unknown_fitment(self):
        assert parse_fitment("簡易裝潢") is None

    def test_none_input(self):
        assert parse_fitment(None) is None

    def test_empty_string(self):
        assert parse_fitment("") is None

    def test_dash_placeholder(self):
        assert parse_fitment("--") is None
