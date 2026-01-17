"""
Unit tests for src/crawler/extractors/
"""

from bs4 import BeautifulSoup

from src.crawler.combiner import (
    combine_raw_data,
    combine_with_detail_only,
    combine_with_list_only,
)
from src.crawler.detail_fetcher_bs4 import _parse_detail_raw
from src.crawler.detail_fetcher_playwright import (
    _extract_surrounding,
    _find_detail_data,
    _parse_detail_raw_from_nuxt,
    extract_detail_raw_from_nuxt,
)
from src.crawler.list_fetcher_bs4 import _parse_item_raw
from src.crawler.list_fetcher_playwright import (
    _find_items,
    _parse_item_raw_from_nuxt,
    extract_list_raw_from_nuxt,
    get_total_from_nuxt,
)

# Import fixtures from fixtures folder
pytest_plugins = ["tests.fixtures.extractors"]


# ============================================================
# combiner.py tests
# ============================================================


class TestCombineRawData:
    """Tests for combine_raw_data function."""

    def test_basic_combine(self, sample_list_raw, sample_detail_raw):
        result = combine_raw_data(sample_list_raw, sample_detail_raw)

        # From List only
        assert result["id"] == "12345678"
        assert result["url"] == "https://rent.591.com.tw/12345678"
        assert result["kind_name"] == "獨立套房"

        # Detail priority
        assert result["title"] == "台北市信義區精緻套房"
        assert result["price_raw"] == "16,000元/月"
        assert result["address_raw"] == "台北市信義區信義路五段"

        # From Detail only
        assert result["region"] == "1"
        assert result["section"] == "7"
        assert result["shape_raw"] == "電梯大樓"
        assert result["surrounding_type"] == "metro"

    def test_tags_merged(self, sample_list_raw, sample_detail_raw):
        result = combine_raw_data(sample_list_raw, sample_detail_raw)

        # Tags should be merged and deduplicated
        assert "近捷運" in result["tags"]
        assert "有陽台" in result["tags"]
        assert "可養寵物" in result["tags"]
        assert "有電梯" in result["tags"]

    def test_layout_from_detail_only(self, sample_list_raw, sample_detail_raw):
        result = combine_raw_data(sample_list_raw, sample_detail_raw)

        # Layout comes from Detail only (more accurate with 廳/衛 info)
        assert result["layout_raw"] == "2房1廳1衛"

    def test_detail_fallback_when_list_empty(self, sample_detail_raw):
        list_data = {
            "region": 1,
            "section": "",
            "id": "12345678",
            "url": "https://rent.591.com.tw/12345678",
            "title": "",
            "price_raw": "",
            "tags": [],
            "kind_name": "獨立套房",
            "layout_raw": "",
            "area_raw": "",
            "floor_raw": "",
            "address_raw": "",
        }
        result = combine_raw_data(list_data, sample_detail_raw)

        # Should fallback to Detail
        assert result["title"] == "台北市信義區精緻套房"
        assert result["price_raw"] == "16,000元/月"

    def test_section_detail_priority(self, sample_list_raw, sample_detail_raw):
        """Test that section from detail page takes priority over list."""
        # List has section 7, detail has section 7
        result = combine_raw_data(sample_list_raw, sample_detail_raw)
        assert result["section"] == "7"

        # Modify detail to have different section
        detail_modified = {**sample_detail_raw, "section": "5"}
        result = combine_raw_data(sample_list_raw, detail_modified)
        assert result["section"] == "5"  # Detail priority

    def test_section_fallback_to_list(self, sample_list_raw, sample_detail_raw):
        """Test that section falls back to list when detail is empty."""
        detail_empty_section = {**sample_detail_raw, "section": ""}
        result = combine_raw_data(sample_list_raw, detail_empty_section)
        assert result["section"] == "7"  # Fallback to list


class TestCombineWithDetailOnly:
    """Tests for combine_with_detail_only function."""

    def test_basic_detail_only(self, sample_detail_raw):
        result = combine_with_detail_only(sample_detail_raw)

        assert result["id"] == "12345678"
        assert result["url"] == "https://rent.591.com.tw/12345678"
        assert result["title"] == "台北市信義區精緻套房"
        assert result["kind_name"] == ""  # Not available from detail

    def test_custom_url(self, sample_detail_raw):
        custom_url = "https://custom.url/123"
        result = combine_with_detail_only(sample_detail_raw, url=custom_url)

        assert result["url"] == custom_url


class TestCombineWithListOnly:
    """Tests for combine_with_list_only function."""

    def test_basic_list_only(self, sample_list_raw):
        result = combine_with_list_only(sample_list_raw)

        assert result["id"] == "12345678"
        assert result["url"] == "https://rent.591.com.tw/12345678"
        assert result["title"] == "台北市信義區套房"
        assert result["kind_name"] == "獨立套房"
        assert result["has_detail"] is False

    def test_list_only_preserves_section(self, sample_list_raw):
        """Test that section from list is preserved."""
        result = combine_with_list_only(sample_list_raw)
        assert result["section"] == "7"

    def test_list_only_preserves_layout(self):
        """Test that layout_raw from list is preserved."""
        list_data = {
            "region": 1,
            "section": "5",
            "id": "123",
            "url": "https://rent.591.com.tw/123",
            "title": "測試",
            "price_raw": "10,000元/月",
            "tags": [],
            "kind_name": "整層住家",
            "layout_raw": "2房1廳",
            "area_raw": "20坪",
            "floor_raw": "3F/5F",
            "address_raw": "大安區-忠孝東路",
        }
        result = combine_with_list_only(list_data)
        assert result["layout_raw"] == "2房1廳"

    def test_list_only_detail_fields_are_none(self, sample_list_raw):
        """Test that detail-only fields are None/empty."""
        result = combine_with_list_only(sample_list_raw)

        assert result["kind"] == ""
        assert result["gender_raw"] is None
        assert result["shape_raw"] is None
        assert result["fitment_raw"] is None
        assert result["options"] == []
        assert result["surrounding_type"] is None
        assert result["surrounding_raw"] is None


# ============================================================
# list_extractor_playwright.py tests
# ============================================================


class TestFindItems:
    """Tests for _find_items function."""

    def test_find_items_in_nested_structure(self, sample_nuxt_list_data):
        items, total = _find_items(sample_nuxt_list_data)

        assert len(items) == 1
        assert total == 100

    def test_empty_dict(self):
        items, total = _find_items({})
        assert items == []
        assert total == 0

    def test_invalid_input(self):
        items, total = _find_items(None)
        assert items == []
        assert total == 0


class TestParseItemRawFromNuxt:
    """Tests for _parse_item_raw_from_nuxt function."""

    def test_parse_nuxt_item(self):
        item = {
            "id": 12345678,
            "url": "https://rent.591.com.tw/12345678",
            "title": "測試套房",
            "price": 15000,
            "tags": [{"id": 1, "value": "近捷運"}],
            "kind_name": "獨立套房",
            "layoutStr": "2房1廳",
            "area": 10,
            "floor_name": "3F/5F",
            "address": "信義區",
        }
        result = _parse_item_raw_from_nuxt(item, region=1)

        assert result["id"] == "12345678"
        assert result["url"] == "https://rent.591.com.tw/12345678"
        assert result["title"] == "測試套房"
        assert result["price_raw"] == "15000元/月"
        assert result["tags"] == ["近捷運"]
        assert result["kind_name"] == "獨立套房"
        # Note: layout is now obtained from detail page only
        assert result["area_raw"] == "10坪"
        assert result["floor_raw"] == "3F/5F"

    def test_parse_nuxt_item_with_id_field(self):
        """Test that ID is extracted directly from 'id' field."""
        item = {"id": 99999999, "title": "測試"}
        result = _parse_item_raw_from_nuxt(item, region=1)

        assert result["id"] == "99999999"

    def test_parse_nuxt_item_string_tags(self):
        item = {"id": 123, "tags": ["近捷運", "有陽台"]}
        result = _parse_item_raw_from_nuxt(item, region=1)

        assert result["tags"] == ["近捷運", "有陽台"]

    def test_parse_nuxt_item_with_sectionid(self):
        """Test that section is extracted from sectionid field."""
        item = {"id": 123, "sectionid": 7}
        result = _parse_item_raw_from_nuxt(item, region=1)

        assert result["section"] == "7"

    def test_parse_nuxt_item_without_sectionid(self):
        """Test that section is empty when sectionid is missing."""
        item = {"id": 123}
        result = _parse_item_raw_from_nuxt(item, region=1)

        assert result["section"] == ""


class TestExtractListRawFromNuxt:
    """Tests for extract_list_raw_from_nuxt function."""

    def test_extract_from_nuxt(self, sample_nuxt_list_data):
        results = extract_list_raw_from_nuxt(sample_nuxt_list_data, region=1)

        assert len(results) == 1
        assert results[0]["id"] == "12345678"
        assert results[0]["title"] == "NUXT套房"

    def test_empty_nuxt_data(self):
        results = extract_list_raw_from_nuxt({}, region=1)
        assert results == []


class TestGetTotalFromNuxt:
    """Tests for get_total_from_nuxt function."""

    def test_get_total(self, sample_nuxt_list_data):
        total = get_total_from_nuxt(sample_nuxt_list_data)
        assert total == 100


# ============================================================
# detail_extractor_playwright.py tests
# ============================================================


class TestFindDetailData:
    """Tests for _find_detail_data function."""

    def test_find_detail_data(self, sample_nuxt_detail_data):
        result = _find_detail_data(sample_nuxt_detail_data)

        assert result is not None
        assert "service" in result

    def test_not_found(self):
        result = _find_detail_data({})
        assert result is None


class TestParseDetailRawFromNuxt:
    """Tests for _parse_detail_raw_from_nuxt function."""

    def test_parse_detail_nuxt(self, sample_nuxt_detail_data):
        data = sample_nuxt_detail_data["fetch"]["data"]
        result = _parse_detail_raw_from_nuxt(data, object_id=12345678)

        assert result["id"] == 12345678
        assert result["title"] == "NUXT詳細頁套房"
        assert result["price_raw"] == "16000元/月"
        assert result["tags"] == ["可養寵物"]
        assert result["region"] == "1"
        assert result["section"] == "7"
        assert result["kind"] == "2"
        assert result["floor_raw"] == "5F/10F"
        assert result["layout_raw"] == "3房2廳"
        assert result["shape_raw"] == "電梯大樓"
        assert result["options"] == ["冷氣", "洗衣機"]
        assert result["surrounding_type"] == "metro"
        assert "信義安和站" in result["surrounding_raw"]


class TestExtractSurrounding:
    """Tests for _extract_surrounding function."""

    def test_metro_traffic(self):
        result = {
            "surrounding_type": None,
            "surrounding_raw": None,
        }
        traffic = {"metro": [{"name": "台北車站", "distance": 100}]}

        result = _extract_surrounding(traffic, result)

        assert result["surrounding_type"] == "metro"
        assert result["surrounding_raw"] == "距台北車站100公尺"

    def test_bus_traffic(self):
        result = {
            "surrounding_type": None,
            "surrounding_raw": None,
        }
        traffic = {"bus": [{"name": "信義路口", "distance": 50}]}

        result = _extract_surrounding(traffic, result)

        assert result["surrounding_type"] == "bus"
        assert "信義路口" in result["surrounding_raw"]

    def test_list_format_traffic(self):
        result = {
            "surrounding_type": None,
            "surrounding_raw": None,
        }
        traffic = [{"type": "metro", "name": "板橋站", "distance": 200}]

        result = _extract_surrounding(traffic, result)

        assert result["surrounding_type"] == "metro"


class TestExtractDetailRawFromNuxt:
    """Tests for extract_detail_raw_from_nuxt function."""

    def test_extract_detail(self, sample_nuxt_detail_data):
        result = extract_detail_raw_from_nuxt(sample_nuxt_detail_data, object_id=123)

        assert result is not None
        assert result["title"] == "NUXT詳細頁套房"

    def test_invalid_data(self):
        result = extract_detail_raw_from_nuxt({}, object_id=123)
        assert result is None


# ============================================================
# list_extractor.py tests (HTML parsing)
# ============================================================


class TestParseItemRaw:
    """Tests for _parse_item_raw function."""

    def test_parse_html_item(self, sample_list_html):
        soup = BeautifulSoup(sample_list_html, "html.parser")
        elem = soup.find("div", class_="item")
        result = _parse_item_raw(elem, region=1)

        assert result["id"] == "12345678"
        assert result["url"] == "https://rent.591.com.tw/12345678"
        assert result["title"] == "台北市信義區套房"
        assert result["price_raw"] == "15,000元/月"
        assert "近捷運" in result["tags"]
        assert result["kind_name"] == "獨立套房"
        # Note: layout is now obtained from detail page only
        assert result["area_raw"] == "10坪"
        assert result["floor_raw"] == "3F/10F"

    def test_empty_element(self):
        soup = BeautifulSoup("<div class='item'></div>", "html.parser")
        elem = soup.find("div", class_="item")
        result = _parse_item_raw(elem, region=1)

        assert result["id"] == ""
        assert result["title"] == ""
        assert result["tags"] == []

    def test_section_parsed_from_address_taipei(self):
        """Test that section is parsed from address_raw for Taipei."""
        html = """
        <div class="item" data-id="123">
            <div class="item-info-txt">
                <span class="house-place"></span>
                <span>大安區-忠孝東路</span>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.find("div", class_="item")
        result = _parse_item_raw(elem, region=1)

        assert result["section"] == 5  # 大安區 = 5
        assert result["address_raw"] == "大安區-忠孝東路"

    def test_section_parsed_from_address_new_taipei(self):
        """Test that section is parsed from address_raw for New Taipei."""
        html = """
        <div class="item" data-id="123">
            <div class="item-info-txt">
                <span class="house-place"></span>
                <span>板橋區-中山路</span>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.find("div", class_="item")
        result = _parse_item_raw(elem, region=3)

        assert result["section"] == 26  # 板橋區 = 26
        assert result["address_raw"] == "板橋區-中山路"

    def test_section_none_when_district_not_found(self):
        """Test that section is None when district is not in mapping."""
        html = """
        <div class="item" data-id="123">
            <div class="item-info-txt">
                <span class="house-place"></span>
                <span>未知區-某路</span>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.find("div", class_="item")
        result = _parse_item_raw(elem, region=1)

        assert result["section"] is None


# ============================================================
# detail_extractor.py tests (HTML parsing)
# ============================================================


class TestParseDetailRaw:
    """Tests for _parse_detail_raw function."""

    def test_parse_html_detail(self, sample_detail_html):
        soup = BeautifulSoup(sample_detail_html, "html.parser")
        page_text = soup.get_text()
        result = _parse_detail_raw(soup, page_text, object_id=12345678)

        assert result["id"] == 12345678
        assert result["title"] == "台北市信義區精緻套房"
        assert result["price_raw"] == "16,000"
        assert "可養寵物" in result["tags"]
        assert result["address_raw"] == "台北市信義區信義路五段"
        assert result["region"] == "1"
        assert result["shape_raw"] == "電梯大樓"
        assert result["fitment_raw"] == "新裝潢"
        assert "冷氣" in result["options"]
        assert result["surrounding_type"] == "metro"

    def test_gender_restriction_male(self):
        html = "<html><body><h1>Title</h1><div>限男生租住</div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text()
        result = _parse_detail_raw(soup, page_text, object_id=123)

        assert result["gender_raw"] == "限男"

    def test_gender_restriction_female(self):
        html = "<html><body><h1>Title</h1><div>限女生租住</div></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text()
        result = _parse_detail_raw(soup, page_text, object_id=123)

        assert result["gender_raw"] == "限女"

    def test_empty_page(self):
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text()
        result = _parse_detail_raw(soup, page_text, object_id=123)

        assert result["id"] == 123
        assert result["title"] == ""
        assert result["tags"] == []
