"""
ETL Transform module for 591 crawler.

Transform raw data from extractors into database-ready format.
This module centralizes all data transformation logic.
"""

import re
from typing import TypedDict

from src.utils.mappings import (
    FITMENT_NAME_TO_CODE,
    OPTIONS_NAME_TO_CODE,
    OTHER_NAME_TO_CODE,
    SHAPE_NAME_TO_CODE,
)

# ============================================
# Type Definitions
# ============================================


class DBReadyData(TypedDict):
    """Database-ready data structure matching objects table schema."""

    id: int
    url: str
    title: str
    price: int
    price_unit: str
    region: int
    section: int
    kind: int
    kind_name: str
    address: str
    floor: int | None
    floor_str: str
    total_floor: int | None
    is_rooftop: bool
    layout: int | None
    layout_str: str
    bathroom: int | None
    area: float | None
    shape: int | None
    fitment: int | None
    gender: str
    pet_allowed: bool | None
    options: list[str]
    other: list[str]
    tags: list[str]
    surrounding_type: str | None
    surrounding_desc: str | None
    surrounding_distance: int | None


# ============================================
# Individual Transform Functions
# ============================================


def transform_id(id_str: str) -> int:
    """
    Transform ID string to integer.

    Args:
        id_str: Object ID as string (e.g., "20510104")

    Returns:
        Object ID as integer

    Examples:
        >>> transform_id("20510104")
        20510104
    """
    return int(id_str)


def transform_price(price_raw: str) -> tuple[int, str]:
    """
    Transform price string to numeric value and unit.

    Args:
        price_raw: Price string (e.g., "8,499元/月", "15,000 元/月")

    Returns:
        Tuple of (price_value, price_unit)

    Examples:
        >>> transform_price("8,499元/月")
        (8499, "元/月")
        >>> transform_price("15,000 元/月")
        (15000, "元/月")
        >>> transform_price("含")
        (0, "")
    """
    if not price_raw:
        return 0, ""

    # Remove commas and whitespace
    cleaned = price_raw.replace(",", "").replace(" ", "")

    # Extract numeric part
    match = re.match(r"(\d+)", cleaned)
    if not match:
        return 0, ""

    price = int(match.group(1))

    # Extract unit (everything after the number)
    unit_match = re.search(r"\d+(.+)", cleaned)
    unit = unit_match.group(1) if unit_match else "元/月"

    return price, unit


def transform_floor(floor_raw: str | None) -> tuple[int | None, int | None, bool]:
    """
    Transform floor string to structured data.

    Args:
        floor_raw: Floor string (e.g., "3F/5F", "頂層加蓋/5F", "B1/10F")

    Returns:
        Tuple of (floor, total_floor, is_rooftop)

    Examples:
        >>> transform_floor("3F/5F")
        (3, 5, False)
        >>> transform_floor("頂層加蓋/5F")
        (0, 5, True)
        >>> transform_floor("B1/10F")
        (-1, 10, False)
        >>> transform_floor(None)
        (None, None, False)
    """
    if not floor_raw:
        return None, None, False

    # Check for rooftop addition
    is_rooftop = "頂" in floor_raw and "加" in floor_raw

    # Parse total floor (e.g., "/5F" -> 5)
    total_match = re.search(r"/(\d+)F", floor_raw, re.IGNORECASE)
    total_floor = int(total_match.group(1)) if total_match else None

    # Parse current floor
    floor: int | None = None
    if is_rooftop:
        floor = 0
    elif floor_raw.upper().startswith("B"):
        # Basement: B1 -> -1, B2 -> -2
        basement_match = re.match(r"B(\d+)", floor_raw, re.IGNORECASE)
        floor = -int(basement_match.group(1)) if basement_match else -1
    else:
        # Normal floor: "3F" -> 3
        floor_match = re.match(r"(\d+)F", floor_raw, re.IGNORECASE)
        floor = int(floor_match.group(1)) if floor_match else None

    return floor, total_floor, is_rooftop


def transform_layout(
    layout_raw: str | None,
) -> tuple[int | None, str | None, int | None]:
    """
    Transform layout string to structured data.

    Args:
        layout_raw: Layout string (e.g., "3房2廳1衛", "開放格局")

    Returns:
        Tuple of (layout_num, layout_str, bathroom_num)

    Examples:
        >>> transform_layout("3房2廳1衛")
        (3, "3房2廳1衛", 1)
        >>> transform_layout("2房1廳")
        (2, "2房1廳", None)
        >>> transform_layout("開放格局")
        (None, "開放格局", None)
        >>> transform_layout(None)
        (None, None, None)
    """
    if not layout_raw:
        return None, None, None

    # Extract room count
    room_match = re.search(r"(\d+)房", layout_raw)
    layout_num = int(room_match.group(1)) if room_match else None

    # Extract bathroom count
    bath_match = re.search(r"(\d+)衛", layout_raw)
    bathroom_num = int(bath_match.group(1)) if bath_match else None

    return layout_num, layout_raw, bathroom_num


def transform_area(area_raw: str | None) -> float | None:
    """
    Transform area string to float.

    Args:
        area_raw: Area string (e.g., "4坪", "10.5 坪")

    Returns:
        Area as float or None

    Examples:
        >>> transform_area("4坪")
        4.0
        >>> transform_area("10.5 坪")
        10.5
        >>> transform_area(None)
        None
    """
    if not area_raw:
        return None

    # Extract numeric part (supports decimal)
    match = re.search(r"([\d.]+)", area_raw)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def transform_address(address_raw: str | None) -> str | None:
    """
    Transform address string (clean up separators).

    Args:
        address_raw: Address string (e.g., "永和區-永和路")

    Returns:
        Cleaned address string

    Examples:
        >>> transform_address("永和區-永和路")
        "永和區永和路"
        >>> transform_address("中山區 民生東路")
        "中山區民生東路"
    """
    if not address_raw:
        return None

    # Remove common separators
    cleaned = address_raw.replace("-", "").replace(" ", "")
    return cleaned


def transform_shape(shape_raw: str | None) -> int | None:
    """
    Transform shape name to code.

    Args:
        shape_raw: Shape name (e.g., "公寓", "電梯大樓")

    Returns:
        Shape code (1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅) or None

    Examples:
        >>> transform_shape("公寓")
        1
        >>> transform_shape("電梯大樓")
        2
        >>> transform_shape(None)
        None
    """
    if not shape_raw:
        return None

    # Direct match
    if shape_raw in SHAPE_NAME_TO_CODE:
        return SHAPE_NAME_TO_CODE[shape_raw]

    # Partial match (e.g., "透天" in "透天厝")
    for name, code in SHAPE_NAME_TO_CODE.items():
        if name in shape_raw or shape_raw in name:
            return code

    return None


def transform_fitment(fitment_raw: str | None) -> int | None:
    """
    Transform fitment name to code.

    Args:
        fitment_raw: Fitment name (e.g., "新裝潢", "中檔裝潢")

    Returns:
        Fitment code (99=新裝潢, 3=中檔裝潢, 4=高檔裝潢) or None

    Examples:
        >>> transform_fitment("新裝潢")
        99
        >>> transform_fitment("中檔裝潢")
        3
        >>> transform_fitment("簡易裝潢")
        None
    """
    if not fitment_raw or fitment_raw == "--":
        return None

    # Direct match
    if fitment_raw in FITMENT_NAME_TO_CODE:
        return FITMENT_NAME_TO_CODE[fitment_raw]

    # Partial match
    for name, code in FITMENT_NAME_TO_CODE.items():
        if name in fitment_raw:
            return code

    return None


def transform_gender(gender_raw: str | None) -> str:
    """
    Transform gender restriction to standardized code.

    Args:
        gender_raw: Gender string (e.g., "限男", "限女", None)

    Returns:
        Gender code: "boy", "girl", or "all"

    Examples:
        >>> transform_gender("限男")
        "boy"
        >>> transform_gender("限女")
        "girl"
        >>> transform_gender(None)
        "all"
    """
    if not gender_raw:
        return "all"

    if "限男" in gender_raw:
        return "boy"
    elif "限女" in gender_raw:
        return "girl"

    return "all"


def transform_pet_allowed(tags: list[str]) -> bool | None:
    """
    Determine if pets are allowed based on tags.

    Args:
        tags: List of tag strings

    Returns:
        True if pets allowed, False if not, None if not specified

    Examples:
        >>> transform_pet_allowed(["可養寵物", "近捷運"])
        True
        >>> transform_pet_allowed(["近捷運"])
        None
    """
    if not tags:
        return None

    for tag in tags:
        if "可養寵" in tag:
            return True
        if "不可養" in tag or "禁養" in tag:
            return False

    return None


def transform_options(options: list[str]) -> list[str]:
    """
    Transform equipment names to standardized codes.

    Args:
        options: List of Chinese equipment names (e.g., ["冰箱", "洗衣機"])

    Returns:
        List of standardized codes (e.g., ["icebox", "washer"])

    Examples:
        >>> transform_options(["冰箱", "洗衣機", "冷氣"])
        ["icebox", "washer", "cold"]
    """
    if not options:
        return []

    codes = set()
    for name in options:
        # Direct match
        if name in OPTIONS_NAME_TO_CODE:
            codes.add(OPTIONS_NAME_TO_CODE[name])
        else:
            # Partial match
            for key, code in OPTIONS_NAME_TO_CODE.items():
                if key in name:
                    codes.add(code)
                    break

    return list(codes)


def transform_other(tags: list[str]) -> list[str]:
    """
    Transform tag names to 'other' feature codes.

    Args:
        tags: List of Chinese tag names

    Returns:
        List of standardized codes

    Examples:
        >>> transform_other(["近捷運", "可養寵物"])
        ["near_subway", "pet"]
    """
    if not tags:
        return []

    codes = set()
    for name in tags:
        if name in OTHER_NAME_TO_CODE:
            codes.add(OTHER_NAME_TO_CODE[name])
        else:
            for key, code in OTHER_NAME_TO_CODE.items():
                if key in name:
                    codes.add(code)
                    break

    return list(codes)


def transform_surrounding(surrounding_raw: str | None) -> tuple[str | None, int | None]:
    """
    Transform surrounding string to description and distance.

    Args:
        surrounding_raw: Surrounding string (e.g., "距信義安和站353公尺")

    Returns:
        Tuple of (station_name, distance_meters)

    Examples:
        >>> transform_surrounding("距信義安和站353公尺")
        ("信義安和站", 353)
        >>> transform_surrounding("距行善仁愛路口站500公尺")
        ("行善仁愛路口站", 500)
        >>> transform_surrounding(None)
        (None, None)
    """
    if not surrounding_raw:
        return None, None

    # Pattern: "距{station_name}{distance}公尺"
    match = re.match(r"距(.+?)(\d+)公尺", surrounding_raw)
    if not match:
        return None, None

    station_name = match.group(1)
    distance = int(match.group(2))

    return station_name, distance


# ============================================
# Main Transform Function
# ============================================


def transform_to_db_ready(combined: dict) -> DBReadyData:
    """
    Transform combined raw data to database-ready format.

    This is the main entry point for the Transform phase of ETL.

    Args:
        combined: CombinedRawData dict from combiner

    Returns:
        DBReadyData dict ready for database insertion

    Example:
        >>> combined = {
        ...     "id": "20510104",
        ...     "url": "https://rent.591.com.tw/20510104",
        ...     "title": "近捷運套房",
        ...     "price_raw": "8,500元/月",
        ...     "tags": ["近捷運", "可養寵物"],
        ...     "kind_name": "獨立套房",
        ...     "address_raw": "中山區-民生東路",
        ...     "surrounding_type": "metro",
        ...     "surrounding_raw": "距信義安和站353公尺",
        ...     "region": "1",
        ...     "section": "3",
        ...     "kind": "2",
        ...     "floor_raw": "3F/5F",
        ...     "layout_raw": "2房1廳1衛",
        ...     "area_raw": "10坪",
        ...     "gender_raw": None,
        ...     "shape_raw": "電梯大樓",
        ...     "fitment_raw": "新裝潢",
        ...     "options": ["冰箱", "洗衣機"],
        ... }
        >>> result = transform_to_db_ready(combined)
        >>> result["id"]
        20510104
        >>> result["price"]
        8500
    """
    # Transform ID
    obj_id = transform_id(combined.get("id", "0"))

    # Transform price
    price, price_unit = transform_price(combined.get("price_raw", ""))

    # Transform floor
    floor, total_floor, is_rooftop = transform_floor(combined.get("floor_raw"))

    # Transform layout
    layout, layout_str, bathroom = transform_layout(combined.get("layout_raw"))

    # Transform area
    area = transform_area(combined.get("area_raw"))

    # Transform address
    address = transform_address(combined.get("address_raw"))

    # Transform shape
    shape = transform_shape(combined.get("shape_raw"))

    # Transform fitment
    fitment = transform_fitment(combined.get("fitment_raw"))

    # Transform gender
    gender = transform_gender(combined.get("gender_raw"))

    # Transform surrounding
    surrounding_desc, surrounding_distance = transform_surrounding(
        combined.get("surrounding_raw")
    )

    # Get tags for multiple transforms
    tags = combined.get("tags", [])

    # Transform pet_allowed from tags
    pet_allowed = transform_pet_allowed(tags)

    # Transform options
    options = transform_options(combined.get("options", []))

    # Transform other (features) from tags
    other = transform_other(tags)

    # Build result
    result: DBReadyData = {
        "id": obj_id,
        "url": combined.get("url", ""),
        "title": combined.get("title", ""),
        "price": price,
        "price_unit": price_unit,
        "region": int(combined.get("region", 0)),
        "section": int(combined.get("section", 0)),
        "kind": int(combined.get("kind", 0)),
        "kind_name": combined.get("kind_name", ""),
        "address": address or "",
        "floor": floor,
        "floor_str": combined.get("floor_raw", "") or "",
        "total_floor": total_floor,
        "is_rooftop": is_rooftop,
        "layout": layout,
        "layout_str": layout_str or "",
        "bathroom": bathroom,
        "area": area,
        "shape": shape,
        "fitment": fitment,
        "gender": gender,
        "pet_allowed": pet_allowed,
        "options": options,
        "other": other,
        "tags": tags,
        "surrounding_type": combined.get("surrounding_type"),
        "surrounding_desc": surrounding_desc,
        "surrounding_distance": surrounding_distance,
    }

    return result
