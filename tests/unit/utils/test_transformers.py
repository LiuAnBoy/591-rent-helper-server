"""
Unit tests for src/utils/transformers.py
"""

import pytest

from src.utils.transformers import (
    transform_id,
    transform_price,
    transform_floor,
    transform_layout,
    transform_area,
    transform_address,
    transform_shape,
    transform_fitment,
    transform_gender,
    transform_pet_allowed,
    transform_options,
    transform_other,
    transform_surrounding,
    transform_to_db_ready,
)


# ============================================================
# transform_id tests
# ============================================================


class TestTransformId:
    """Tests for transform_id function."""

    def test_normal_id(self):
        assert transform_id("12345678") == 12345678

    def test_id_with_leading_zeros(self):
        assert transform_id("00123456") == 123456

    def test_large_id(self):
        assert transform_id("99999999") == 99999999


# ============================================================
# transform_price tests
# ============================================================


class TestTransformPrice:
    """Tests for transform_price function."""

    def test_normal_price_with_unit(self):
        price, unit = transform_price("8,499元/月")
        assert price == 8499
        assert unit == "元/月"

    def test_price_without_comma(self):
        price, unit = transform_price("8000元/月")
        assert price == 8000
        assert unit == "元/月"

    def test_price_with_multiple_commas(self):
        price, unit = transform_price("1,234,567元/月")
        assert price == 1234567

    def test_price_with_space(self):
        price, unit = transform_price("15,000 元/月")
        assert price == 15000
        assert unit == "元/月"

    def test_empty_price(self):
        price, unit = transform_price("")
        assert price == 0
        assert unit == ""

    def test_none_price(self):
        price, unit = transform_price(None)
        assert price == 0
        assert unit == ""

    def test_non_numeric(self):
        price, unit = transform_price("含")
        assert price == 0
        assert unit == ""


# ============================================================
# transform_floor tests
# ============================================================


class TestTransformFloor:
    """Tests for transform_floor function."""

    def test_normal_floor(self):
        floor, total, is_rooftop = transform_floor("3F/10F")
        assert floor == 3
        assert total == 10
        assert is_rooftop is False

    def test_first_floor(self):
        floor, total, is_rooftop = transform_floor("1F/5F")
        assert floor == 1
        assert total == 5
        assert is_rooftop is False

    def test_top_floor(self):
        floor, total, is_rooftop = transform_floor("10F/10F")
        assert floor == 10
        assert total == 10
        assert is_rooftop is False

    def test_rooftop(self):
        floor, total, is_rooftop = transform_floor("頂樓加蓋/5F")
        assert is_rooftop is True

    def test_basement(self):
        floor, total, is_rooftop = transform_floor("B1/10F")
        assert floor == -1
        assert total == 10
        assert is_rooftop is False

    def test_basement_b2(self):
        floor, total, is_rooftop = transform_floor("B2/8F")
        assert floor == -2

    def test_whole_building(self):
        floor, total, is_rooftop = transform_floor("整棟")
        assert floor is None
        assert total is None
        assert is_rooftop is False

    def test_none_floor(self):
        floor, total, is_rooftop = transform_floor(None)
        assert floor is None
        assert total is None
        assert is_rooftop is False

    def test_empty_floor(self):
        floor, total, is_rooftop = transform_floor("")
        assert floor is None
        assert total is None


# ============================================================
# transform_layout tests
# ============================================================


class TestTransformLayout:
    """Tests for transform_layout function."""

    def test_normal_layout(self):
        layout, layout_str, bathroom = transform_layout("2房1廳1衛")
        assert layout == 2
        assert bathroom == 1

    def test_studio(self):
        layout, layout_str, bathroom = transform_layout("1房1衛")
        assert layout == 1
        assert bathroom == 1

    def test_large_layout(self):
        layout, layout_str, bathroom = transform_layout("5房2廳3衛")
        assert layout == 5
        assert bathroom == 3

    def test_none_layout(self):
        layout, layout_str, bathroom = transform_layout(None)
        assert layout is None
        assert layout_str is None
        assert bathroom is None

    def test_empty_layout(self):
        layout, layout_str, bathroom = transform_layout("")
        assert layout is None


# ============================================================
# transform_area tests
# ============================================================


class TestTransformArea:
    """Tests for transform_area function."""

    def test_normal_area(self):
        assert transform_area("10坪") == 10.0

    def test_decimal_area(self):
        assert transform_area("12.5坪") == 12.5

    def test_area_without_unit(self):
        assert transform_area("15") == 15.0

    def test_large_area(self):
        assert transform_area("100坪") == 100.0

    def test_none_area(self):
        assert transform_area(None) is None

    def test_empty_area(self):
        assert transform_area("") is None


# ============================================================
# transform_address tests
# ============================================================


class TestTransformAddress:
    """Tests for transform_address function."""

    def test_normal_address(self):
        # Function keeps the full address, doesn't strip city
        result = transform_address("台北市信義區信義路五段")
        assert result == "台北市信義區信義路五段"

    def test_address_without_city(self):
        result = transform_address("信義區信義路五段")
        assert result == "信義區信義路五段"

    def test_new_taipei(self):
        result = transform_address("新北市板橋區中山路")
        assert result == "新北市板橋區中山路"

    def test_none_address(self):
        assert transform_address(None) is None

    def test_empty_address(self):
        assert transform_address("") is None


# ============================================================
# transform_shape tests
# ============================================================


class TestTransformShape:
    """Tests for transform_shape function."""

    def test_apartment(self):
        assert transform_shape("公寓") == 1

    def test_mansion(self):
        assert transform_shape("電梯大樓") == 2

    def test_townhouse(self):
        assert transform_shape("透天厝") == 3

    def test_villa(self):
        assert transform_shape("別墅") == 4

    def test_unknown_shape(self):
        assert transform_shape("未知類型") is None

    def test_none_shape(self):
        assert transform_shape(None) is None


# ============================================================
# transform_fitment tests
# ============================================================


class TestTransformFitment:
    """Tests for transform_fitment function."""

    def test_new_fitment(self):
        # 新裝潢 = 99
        assert transform_fitment("新裝潢") == 99

    def test_middle_fitment(self):
        # 中檔裝潢 = 3
        assert transform_fitment("中檔裝潢") == 3

    def test_high_fitment(self):
        # 高檔裝潢 = 4
        assert transform_fitment("高檔裝潢") == 4

    def test_unknown_fitment(self):
        # 簡易裝潢 is not in mapping
        assert transform_fitment("簡易裝潢") is None

    def test_none_fitment(self):
        assert transform_fitment(None) is None

    def test_empty_fitment(self):
        assert transform_fitment("--") is None


# ============================================================
# transform_gender tests
# ============================================================


class TestTransformGender:
    """Tests for transform_gender function."""

    def test_all_gender(self):
        assert transform_gender("男女皆可") == "all"

    def test_male_only(self):
        assert transform_gender("限男生") == "boy"

    def test_female_only(self):
        assert transform_gender("限女生") == "girl"

    def test_none_gender(self):
        assert transform_gender(None) == "all"

    def test_empty_gender(self):
        assert transform_gender("") == "all"

    def test_unknown_gender(self):
        # Any unrecognized string defaults to "all"
        assert transform_gender("不限") == "all"


# ============================================================
# transform_pet_allowed tests
# ============================================================


class TestTransformPetAllowed:
    """Tests for transform_pet_allowed function."""

    def test_pet_allowed(self):
        assert transform_pet_allowed(["近捷運", "可養寵物", "有陽台"]) is True

    def test_pet_not_mentioned(self):
        assert transform_pet_allowed(["近捷運", "有陽台"]) is False

    def test_empty_tags(self):
        assert transform_pet_allowed([]) is False

    def test_partial_match_not_allowed(self):
        # "可養寵" (3 chars) should not match, must be "可養寵物" (4 chars)
        assert transform_pet_allowed(["可養寵"]) is False

    def test_exact_match(self):
        assert transform_pet_allowed(["可養寵物"]) is True


# ============================================================
# transform_options tests
# ============================================================


class TestTransformOptions:
    """Tests for transform_options function."""

    def test_normal_options(self):
        # Returns code names, not Chinese names
        result = transform_options(["冷氣", "洗衣機", "冰箱"])
        assert "cold" in result
        assert "washer" in result
        assert "icebox" in result

    def test_empty_options(self):
        assert transform_options([]) == []

    def test_unknown_option(self):
        # Unknown options are ignored
        result = transform_options(["未知設備"])
        assert result == []


# ============================================================
# transform_other tests
# ============================================================


class TestTransformOther:
    """Tests for transform_other function."""

    def test_near_mrt(self):
        result = transform_other(["近捷運"])
        assert "near_subway" in result

    def test_balcony(self):
        result = transform_other(["有陽台"])
        assert any("balcony" in x for x in result)

    def test_empty_tags(self):
        assert transform_other([]) == []

    def test_multiple_features(self):
        result = transform_other(["近捷運", "有陽台", "有電梯"])
        assert isinstance(result, list)
        assert len(result) > 0


# ============================================================
# transform_surrounding tests
# ============================================================


class TestTransformSurrounding:
    """Tests for transform_surrounding function."""

    def test_normal_surrounding(self):
        desc, distance = transform_surrounding("距信義安和站353公尺")
        assert desc == "信義安和站"
        assert distance == 353

    def test_long_station_name(self):
        desc, distance = transform_surrounding("距行善仁愛路口站500公尺")
        assert desc == "行善仁愛路口站"
        assert distance == 500

    def test_short_distance(self):
        desc, distance = transform_surrounding("距台北車站50公尺")
        assert desc == "台北車站"
        assert distance == 50

    def test_none_surrounding(self):
        desc, distance = transform_surrounding(None)
        assert desc is None
        assert distance is None

    def test_empty_surrounding(self):
        desc, distance = transform_surrounding("")
        assert desc is None
        assert distance is None

    def test_invalid_format(self):
        desc, distance = transform_surrounding("附近有捷運站")
        assert desc is None
        assert distance is None


# ============================================================
# transform_to_db_ready tests
# ============================================================


class TestTransformToDbReady:
    """Tests for transform_to_db_ready function."""

    def test_full_transform(self, sample_combined_data):
        result = transform_to_db_ready(sample_combined_data)

        assert result["id"] == 12345678
        assert result["title"] == "台北市信義區獨立套房"
        assert result["region"] == 1
        assert isinstance(result["price"], int)
        assert isinstance(result["pet_allowed"], bool)

    def test_minimal_data(self):
        minimal = {
            "id": 123,
            "title": "測試物件",
            "region": 1,
            "section": 1,
            "kind": 1,
            "kind_name": "套房",
        }
        result = transform_to_db_ready(minimal)

        assert result["id"] == 123
        assert result["price"] == 0
        assert result["pet_allowed"] is False

    def test_result_has_all_required_fields(self, sample_combined_data):
        result = transform_to_db_ready(sample_combined_data)

        required_fields = [
            "id", "url", "title", "price", "price_unit",
            "region", "section", "kind", "kind_name", "address",
            "floor", "floor_str", "total_floor", "is_rooftop",
            "layout", "layout_str", "bathroom", "area", "shape",
            "fitment", "gender", "pet_allowed", "options", "other",
            "tags", "surrounding_type", "surrounding_desc", "surrounding_distance",
        ]

        for field in required_fields:
            assert field in result, f"Missing field: {field}"
