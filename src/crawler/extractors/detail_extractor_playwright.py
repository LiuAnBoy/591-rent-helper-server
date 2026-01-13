"""
Detail page raw data extractor from NUXT data.

Extracts raw data from window.__NUXT__.data for Playwright fetcher.
Part of the ETL Extract phase.
"""

from loguru import logger

from src.crawler.extractors.types import DetailRawData

extractor_log = logger.bind(module="Playwright")


def extract_detail_raw_from_nuxt(
    nuxt_data: dict,
    object_id: int,
) -> DetailRawData | None:
    """
    Extract raw data from NUXT data structure.

    Args:
        nuxt_data: window.__NUXT__.data object from Playwright
        object_id: Object ID

    Returns:
        DetailRawData dictionary or None if parsing failed
    """
    # Find detail data in NUXT structure
    detail_data = _find_detail_data(nuxt_data)
    if not detail_data:
        extractor_log.warning(f"No detail data found in NUXT for object {object_id}")
        return None

    return _parse_detail_raw_from_nuxt(detail_data, object_id)


def _find_detail_data(nuxt_data: dict) -> dict | None:
    """
    Find detail data in NUXT data structure.

    NUXT data structure varies, need to search for "service" key.

    Args:
        nuxt_data: window.__NUXT__.data object

    Returns:
        Detail data dict or None if not found
    """
    if not isinstance(nuxt_data, dict):
        return None

    for _key, val in nuxt_data.items():
        if isinstance(val, dict) and "data" in val:
            data = val["data"]
            if isinstance(data, dict) and "service" in data:
                return data
    return None


def _parse_detail_raw_from_nuxt(data: dict, object_id: int) -> DetailRawData:
    """
    Parse detail data from NUXT structure into DetailRawData.

    Args:
        data: Detail data dict containing service, info, breadcrumb, etc.
        object_id: Object ID

    Returns:
        DetailRawData dictionary
    """
    result: DetailRawData = {
        "id": object_id,
        "title": "",
        "price_raw": "",
        "tags": [],
        "address_raw": "",
        "region": "",
        "section": "",
        "kind": "",
        "floor_raw": "",
        "layout_raw": "",
        "area_raw": "",
        "gender_raw": None,
        "shape_raw": None,
        "fitment_raw": None,
        "options": [],
        "surrounding_type": None,
        "surrounding_raw": None,
    }

    # Title
    result["title"] = data.get("title", "")

    # Price - format as "X元/月"
    price = data.get("price")
    if price is not None:
        result["price_raw"] = f"{price}元/月"

    # Tags - extract value from tag objects
    tags = data.get("tags", [])
    if tags:
        result["tags"] = [tag.get("value") for tag in tags if tag.get("value")]

    # Address
    result["address_raw"] = data.get("address", "")

    # Breadcrumb - extract region, section, kind
    breadcrumb = data.get("breadcrumb", [])
    for crumb in breadcrumb:
        query = crumb.get("query")
        crumb_id = crumb.get("id")
        if crumb_id is not None:
            if query == "region":
                result["region"] = str(crumb_id)
            elif query == "section":
                result["section"] = str(crumb_id)
            elif query == "kind":
                result["kind"] = str(crumb_id)

    # Info array - extract floor, layout, shape, fitment, area
    info = data.get("info", [])
    for item in info:
        key = item.get("key")
        value = item.get("value")
        if not value:
            continue

        if key == "floor":
            result["floor_raw"] = value
        elif key == "layout":
            result["layout_raw"] = value
        elif key == "shape":
            result["shape_raw"] = value
        elif key == "fitment":
            result["fitment_raw"] = value
        elif key == "area":
            # Area might be numeric or string
            if isinstance(value, (int, float)):
                result["area_raw"] = f"{value}坪"
            else:
                result["area_raw"] = value

    # Fallback for area from top-level
    if not result["area_raw"]:
        area = data.get("area")
        if area is not None:
            result["area_raw"] = f"{area}坪"

    # Fallback for floor from floor_name
    if not result["floor_raw"]:
        floor_name = data.get("floor_name") or data.get("floorName")
        if floor_name:
            result["floor_raw"] = floor_name

    # Fallback for layout from layoutStr
    if not result["layout_raw"]:
        layout_str = data.get("layoutStr") or data.get("layout_str")
        if layout_str:
            result["layout_raw"] = layout_str

    # Service - extract gender, options
    service = data.get("service", {})
    if service:
        # Gender from rule
        rule = service.get("rule", "")
        if rule:
            if "限男" in rule:
                result["gender_raw"] = "限男"
            elif "限女" in rule:
                result["gender_raw"] = "限女"

        # Options from facility
        facility = service.get("facility", [])
        if facility:
            # NUXT format: [{"key": "fridge", "active": 1, "name": "冰箱"}, ...]
            active_names = []
            for f in facility:
                if isinstance(f, dict) and f.get("active") == 1:
                    name = f.get("name")
                    if name:
                        active_names.append(name)
            result["options"] = active_names

    # Surrounding/Traffic info
    traffic = data.get("traffic") or data.get("surround")
    if traffic:
        result = _extract_surrounding(traffic, result)

    return result


def _extract_surrounding(traffic: dict | list, result: DetailRawData) -> DetailRawData:
    """
    Extract surrounding/traffic information.

    Args:
        traffic: Traffic data (can be dict or list)
        result: DetailRawData to update

    Returns:
        Updated DetailRawData
    """
    # Handle different traffic data structures
    if isinstance(traffic, dict):
        # Try metro first, then bus
        metro = traffic.get("metro") or traffic.get("subway")
        bus = traffic.get("bus")

        if metro and isinstance(metro, list) and len(metro) > 0:
            item = metro[0]
            result["surrounding_type"] = "metro"
            name = item.get("name", "")
            distance = item.get("distance", "")
            if name and distance:
                result["surrounding_raw"] = f"距{name}{distance}公尺"
        elif bus and isinstance(bus, list) and len(bus) > 0:
            item = bus[0]
            result["surrounding_type"] = "bus"
            name = item.get("name", "")
            distance = item.get("distance", "")
            if name and distance:
                result["surrounding_raw"] = f"距{name}{distance}公尺"

    elif isinstance(traffic, list) and len(traffic) > 0:
        # Simple list format
        item = traffic[0]
        if isinstance(item, dict):
            t_type = item.get("type", "")
            if "metro" in t_type.lower() or "subway" in t_type.lower():
                result["surrounding_type"] = "metro"
            elif "bus" in t_type.lower():
                result["surrounding_type"] = "bus"

            name = item.get("name", "")
            distance = item.get("distance", "")
            if name and distance:
                result["surrounding_raw"] = f"距{name}{distance}公尺"

    return result
