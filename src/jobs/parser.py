"""
Parser utilities for 591 rental data.

Contains functions to parse rental object fields from raw API data.
"""

from typing import Optional

from src.utils import convert_options_to_codes


def parse_is_rooftop(floor_name: Optional[str]) -> bool:
    """
    Parse whether the property is a rooftop addition from floor_name.

    Args:
        floor_name: Floor string from API (e.g., "頂層加蓋/4F", "4F/5F")

    Returns:
        True if rooftop addition, False otherwise

    Examples:
        >>> parse_is_rooftop("頂層加蓋/4F")
        True
        >>> parse_is_rooftop("頂樓加蓋/4F")
        True
        >>> parse_is_rooftop("4F/5F")
        False
        >>> parse_is_rooftop(None)
        False
    """
    if not floor_name:
        return False
    return "頂" in floor_name and "加蓋" in floor_name


def parse_rule(rule: Optional[str]) -> dict:
    """
    Parse gender restriction and pet policy from service.rule.

    Args:
        rule: Rule string from detail page API
              (e.g., "此房屋限男生租住，不可養寵物")

    Returns:
        dict with keys:
            - gender: "boy" | "girl" | "all"
            - pet_allowed: True | False | None

    Examples:
        >>> parse_rule("此房屋限男生租住，不可養寵物")
        {"gender": "boy", "pet_allowed": False}
        >>> parse_rule("此房屋男女皆可租住，可養寵物")
        {"gender": "all", "pet_allowed": True}
        >>> parse_rule("此房屋限女生租住，不可養寵物")
        {"gender": "girl", "pet_allowed": False}
        >>> parse_rule(None)
        {"gender": "all", "pet_allowed": None}
    """
    if not rule:
        return {"gender": "all", "pet_allowed": None}

    # Parse gender restriction
    gender = "all"
    if "限男" in rule:
        gender = "boy"
    elif "限女" in rule:
        gender = "girl"

    # Parse pet policy
    pet_allowed: Optional[bool] = None
    if "可養寵" in rule or "可以養" in rule:
        pet_allowed = True
    elif "不可養" in rule or "禁養" in rule:
        pet_allowed = False

    return {"gender": gender, "pet_allowed": pet_allowed}


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
