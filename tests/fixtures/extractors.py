"""
Mock data fixtures for extractor tests.
"""

import pytest

# ============================================================
# Raw Data Fixtures
# ============================================================


@pytest.fixture
def sample_list_raw():
    """Sample ListRawData."""
    return {
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


@pytest.fixture
def sample_detail_raw():
    """Sample DetailRawData."""
    return {
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


# ============================================================
# NUXT Data Fixtures
# ============================================================


@pytest.fixture
def sample_nuxt_list_data():
    """Sample NUXT data for list page."""
    return {
        "fetch": {
            "data": {
                "items": [
                    {
                        "id": 12345678,
                        "sectionid": 7,
                        "title": "NUXT套房",
                        "price": 15000,
                        "tags": [{"id": 1, "value": "近捷運"}],
                        "kind_name": "獨立套房",
                        "layoutStr": "2房1廳",
                        "area": 10,
                        "floor_name": "3F/10F",
                        "address": "信義區",
                    }
                ],
                "total": 100,
            }
        }
    }


@pytest.fixture
def sample_nuxt_detail_data():
    """Sample NUXT data for detail page."""
    return {
        "fetch": {
            "data": {
                "title": "NUXT詳細頁套房",
                "price": 16000,
                "tags": [{"value": "可養寵物"}],
                "address": "台北市信義區",
                "breadcrumb": [
                    {"query": "region", "id": 1},
                    {"query": "section", "id": 7},
                    {"query": "kind", "id": 2},
                ],
                "info": [
                    {"key": "floor", "value": "5F/10F"},
                    {"key": "layout", "value": "3房2廳"},
                    {"key": "shape", "value": "電梯大樓"},
                    {"key": "fitment", "value": "新裝潢"},
                    {"key": "area", "value": "15坪"},
                ],
                "service": {
                    "rule": "此房屋男女皆可，可養寵物",
                    "facility": [
                        {"key": "cold", "active": 1, "name": "冷氣"},
                        {"key": "washer", "active": 1, "name": "洗衣機"},
                        {"key": "tv", "active": 0, "name": "電視"},
                    ],
                },
                "traffic": {
                    "metro": [{"name": "信義安和站", "distance": 353}],
                },
            }
        }
    }


# ============================================================
# HTML Fixtures
# ============================================================


@pytest.fixture
def sample_list_html():
    """Sample HTML for list item."""
    return """
    <div class="item" data-id="12345678">
        <a href="https://rent.591.com.tw/12345678">連結</a>
        <div class="item-info-title"><a>台北市信義區套房</a></div>
        <div class="item-info-price">15,000元/月</div>
        <div class="item-tags">
            <span>近捷運</span>
            <span>有陽台</span>
        </div>
        <div class="item-info-txt">
            <span class="house-home"></span>
            <span>獨立套房</span>
            <span>2房1廳</span>
            <span>10坪</span>
            <span>3F/10F</span>
        </div>
        <div class="item-info-txt">
            <span class="house-place"></span>
            <span>信義區-信義路</span>
        </div>
    </div>
    """


@pytest.fixture
def sample_detail_html():
    """Sample HTML for detail page."""
    return """
    <html>
    <body>
        <h1>台北市信義區精緻套房</h1>
        <span class="c-price">16,000</span>
        <span class="label-item">可養寵物</span>
        <span class="label-item">有電梯</span>
        <div class="address">
            <span class="load-map">台北市信義區信義路五段</span>
        </div>
        <a href="/list?region=1&section=7&kind=2">麵包屑</a>
        <span>3F/10F</span>
        <div>2房1廳1衛</div>
        <div>12坪</div>
        <div>電梯大樓</div>
        <div>新裝潢</div>
        <dl>
            <dd class="text">冷氣</dd>
        </dl>
        <dl>
            <dd class="text">洗衣機</dd>
        </dl>
        <div class="traffic">
            <p class="icon-subway">
                <b class="ellipsis">信義安和站</b>
                <strong>353</strong>
            </p>
        </div>
    </body>
    </html>
    """
