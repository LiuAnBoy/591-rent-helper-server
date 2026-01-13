"""
Raw data type definitions for 591 crawler ETL.

These TypedDicts define the structure of raw data extracted from 591.
No transformation is done at this stage - values are kept as-is from the HTML.
"""

from typing import TypedDict


class ListRawData(TypedDict):
    """
    Raw data extracted from 591 list page.

    All values are kept as-is from the HTML, no transformation applied.

    Attributes:
        region: Region code (e.g., 1 for Taipei)
        id: Object ID from data-id attribute
        url: Full URL to detail page
        title: Listing title from .item-info-title a
        price_raw: Price string including unit (e.g., "8,500元/月")
        tags: List of tags from .item-tags span (e.g., ["近捷運", "可養寵物"])
        kind_name: Property type (整層住家, 獨立套房, 分租套房, 雅房, 車位, 其他)
        layout_str: Layout string containing "房" (e.g., "2房1廳")
        area_raw: Area string containing "坪" (e.g., "10坪")
        floor_raw: Floor string containing "F" (e.g., "3F/5F")
        address_raw: Address from .item-info-txt (house-place)
    """

    region: int
    id: str
    url: str
    title: str
    price_raw: str
    tags: list[str]
    kind_name: str
    layout_str: str
    area_raw: str
    floor_raw: str
    address_raw: str


class DetailRawData(TypedDict):
    """
    Raw data extracted from 591 detail page.

    All values are kept as-is from the HTML, no transformation applied.

    Attributes:
        id: Object ID (passed as parameter)
        title: Title from h1 element
        price_raw: Price from span.c-price
        tags: Tags from span.label-item
        address_raw: Address from div.address span.load-map
        region: Region code from breadcrumb URL (region=)
        section: Section code from breadcrumb URL (section=)
        kind: Kind code from breadcrumb URL (kind=)
        floor_raw: Floor string (regex: \\d+F/\\d+F)
        layout_raw: Layout string (regex: [1-9]房...)
        area_raw: Area string (regex: [\\d.]+坪)
        gender_raw: Gender restriction (限男/限女) or None
        shape_raw: Building shape (公寓/電梯大樓/透天厝/別墅) or None
        fitment_raw: Fitment level (新裝潢/中檔裝潢/高檔裝潢) or None
        options: Equipment list from dl:not(.del) > dd.text
        surrounding_type: Transport type (metro/bus) or None
        surrounding_raw: Distance string (e.g., "距信義安和站353公尺") or None
    """

    id: int
    title: str
    price_raw: str
    tags: list[str]
    address_raw: str
    region: str
    section: str
    kind: str
    floor_raw: str
    layout_raw: str
    area_raw: str
    gender_raw: str | None
    shape_raw: str | None
    fitment_raw: str | None
    options: list[str]
    surrounding_type: str | None
    surrounding_raw: str | None


class CombinedRawData(TypedDict):
    """
    Combined raw data from List and Detail pages.

    This structure merges data from both sources with specific priority rules:
    - id, url, kind_name: from List
    - title, price_raw, address_raw, floor_raw, area_raw: Detail > List
    - tags: merged from both (deduplicated)
    - layout_raw: List > Detail (List is cleaner)
    - region, section, kind: from Detail
    - gender_raw, shape_raw, fitment_raw, options: from Detail only
    - surrounding_type, surrounding_raw: from Detail only

    Attributes:
        id: Object ID
        url: Full URL to detail page
        title: Listing title (Detail priority)
        price_raw: Price string (Detail priority)
        tags: Merged tags from List + Detail (deduplicated)
        kind_name: Property type from List
        address_raw: Address (Detail priority)
        surrounding_type: Transport type (metro/bus) from Detail
        surrounding_raw: Distance string from Detail
        region: Region code from Detail
        section: Section code from Detail
        kind: Kind code from Detail
        floor_raw: Floor string (Detail priority)
        layout_raw: Layout string (List priority)
        area_raw: Area string (Detail priority)
        gender_raw: Gender restriction from Detail
        shape_raw: Building shape from Detail
        fitment_raw: Fitment level from Detail
        options: Equipment list from Detail
    """

    id: str
    url: str
    title: str
    price_raw: str
    tags: list[str]
    kind_name: str
    address_raw: str
    surrounding_type: str | None
    surrounding_raw: str | None
    region: str
    section: str
    kind: str
    floor_raw: str
    layout_raw: str
    area_raw: str
    gender_raw: str | None
    shape_raw: str | None
    fitment_raw: str | None
    options: list[str]
