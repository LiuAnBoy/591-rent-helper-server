"""
Detail page parsing utilities.

Parse fields from rental detail page data.
"""

from src.utils import convert_options_to_codes
from src.utils.parsers.rule import parse_rule
from src.utils.parsers.shape import parse_shape
from src.utils.parsers.fitment import parse_fitment


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
    """
    result = {
        "gender": "all",
        "pet_allowed": None,
        "shape": None,
        "options": [],
        "fitment": None,
        "section": None,
        "kind": None,
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
        facility = service.get("facility", [])
        if facility:
            result["options"] = convert_options_to_codes(facility)

    # Parse info array for shape and fitment
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

    # Parse breadcrumb for section and kind
    breadcrumb = detail_data.get("breadcrumb", [])
    for crumb in breadcrumb:
        query = crumb.get("query", {})
        if "section" in query:
            result["section"] = int(query["section"])
        if "kind" in query:
            result["kind"] = int(query["kind"])

    return result
