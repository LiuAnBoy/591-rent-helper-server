"""
Detail page parsing utilities.

Parse fields from rental detail page data.
"""

from src.utils import convert_options_to_codes
from src.utils.parsers.rule import parse_rule


def parse_detail_fields(detail_data: dict) -> dict:
    """
    Parse notice-related fields from detail page data.

    Args:
        detail_data: Detail page data containing service.rule, info, etc.

    Returns:
        dict with parsed fields:
            - gender: "boy" | "girl" | "all"
            - pet_allowed: True | False | None
            - shape: str | None (building type)
            - options: list[str] (equipment/facilities)
    """
    result = {
        "gender": "all",
        "pet_allowed": None,
        "shape": None,
        "options": [],
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

    # Parse shape from info array
    info = detail_data.get("info", [])
    for item in info:
        if item.get("key") == "shape":
            result["shape"] = item.get("value")
            break

    return result
