"""
Detail page parsing utilities.

Parse fields from rental detail page data.
"""

from src.utils import convert_options_to_codes
from src.utils.parsers.fitment import parse_fitment
from src.utils.parsers.floor import parse_floor
from src.utils.parsers.rule import parse_rule
from src.utils.parsers.shape import parse_shape


def parse_detail_fields(detail_data: dict) -> dict:
    """
    Parse notice-related fields from detail page data.

    Args:
        detail_data: Detail page data containing service.rule, info, etc.

    Returns:
        dict with parsed fields:
            - gender: "boy" | "girl" | "all"
            - pet_allowed: True | False | None
            - shape: int | None (1=公寓, 2=電梯, 3=透天, 4=別墅)
            - options: list[str] (equipment/facilities)
            - fitment: int | None (99=新裝潢, 3=中檔, 4=高檔)
            - section: int | None (行政區代碼)
            - kind: int | None (類型代碼)
            - floor_str: str | None (e.g., "5F/7F")
            - floor: int | None (current floor)
            - total_floor: int | None (total floors)
            - is_rooftop: bool (rooftop addition)
    """
    result = {
        "gender": "all",
        "pet_allowed": None,
        "shape": None,
        "options": [],
        "fitment": None,
        "section": None,
        "kind": None,
        "floor_str": None,
        "floor": None,
        "total_floor": None,
        "is_rooftop": False,
        "layout_str": None,
        "tags": [],
    }

    # Parse service fields
    service = detail_data.get("service", {})
    if service:
        # Parse rule for gender and pet
        rule = service.get("rule", "")
        parsed = parse_rule(rule)
        result["gender"] = parsed["gender"]
        result["pet_allowed"] = parsed["pet_allowed"]

        # Parse facility for equipment/options (convert to codes)
        # NUXT format: [{"key": "fridge", "active": 1, "name": "冰箱"}, ...]
        # BS4 format: ["冰箱", "洗衣機", ...]
        facility = service.get("facility", [])
        if isinstance(facility, list) and facility:
            if isinstance(facility[0], dict):
                # NUXT format - extract names from active facilities
                active_names = [f.get("name") for f in facility if f.get("active") == 1]
                result["options"] = convert_options_to_codes(active_names)
            else:
                # BS4 format - list of strings
                result["options"] = convert_options_to_codes(facility)

    # Parse info array for shape, fitment, floor, layout
    # NUXT format: [{"name": "格局", "value": "3房2廳2衛", "key": "layout"}, ...]
    info = detail_data.get("info", [])
    for item in info:
        key = item.get("key")
        value = item.get("value")

        if key == "shape" and value:
            # Convert shape name to code
            result["shape"] = parse_shape(value)

        elif key == "fitment" and value:
            # Convert fitment name to code
            result["fitment"] = parse_fitment(value)

        elif key == "floor" and value:
            # Parse floor info (e.g., "2F/14F")
            result["floor_str"] = value
            floor, total_floor, is_rooftop = parse_floor(value)
            result["floor"] = floor
            result["total_floor"] = total_floor
            result["is_rooftop"] = is_rooftop

        elif key == "layout" and value:
            # Layout string (e.g., "3房2廳2衛")
            result["layout_str"] = value

    # Parse breadcrumb for section and kind
    # NUXT format: [{"name": "中山區", "id": 3, "query": "section", "link": "..."}, ...]
    breadcrumb = detail_data.get("breadcrumb", [])
    for crumb in breadcrumb:
        query_type = crumb.get("query")
        crumb_id = crumb.get("id")
        if query_type == "section" and crumb_id:
            result["section"] = int(crumb_id)
        elif query_type == "kind" and crumb_id:
            result["kind"] = int(crumb_id)

    # Fallback: Parse floor info from floor_name field (if not set from info array)
    if not result["floor_str"]:
        floor_name = detail_data.get("floor_name")
        if floor_name:
            result["floor_str"] = floor_name
            floor, total_floor, is_rooftop = parse_floor(floor_name)
            result["floor"] = floor
            result["total_floor"] = total_floor
            result["is_rooftop"] = is_rooftop

    # Fallback: Parse layout_str (if not set from info array)
    if not result["layout_str"]:
        layout_str = detail_data.get("layoutStr") or detail_data.get("layout_str")
        if layout_str:
            result["layout_str"] = layout_str

    # Parse tags (e.g., [{"id": 2, "value": "近捷運"}, ...])
    tags = detail_data.get("tags", [])
    if tags:
        result["tags"] = [tag.get("value") for tag in tags if tag.get("value")]

    return result
