"""
Subscription matching logic for rental objects.

This module provides functions to match rental objects against
user subscription criteria.
"""

import re

from loguru import logger

matcher_log = logger.bind(module="Matcher")


def extract_floor_number(floor_name: str) -> int | None:
    """
    Extract floor number from floor name.

    Args:
        floor_name: String like "3F/10F" or "B1/10F" or "頂樓加蓋"

    Returns:
        Floor number or None if cannot extract

    Examples:
        >>> extract_floor_number("3F/10F")
        3
        >>> extract_floor_number("B1/10F")
        0
        >>> extract_floor_number("頂樓加蓋")
        None
    """
    # Handle basement floors
    if floor_name.upper().startswith("B"):
        return 0  # Treat basement as floor 0

    # Extract first number (current floor)
    match = re.search(r"(\d+)", floor_name)
    if match:
        return int(match.group(1))
    return None


def match_floor(
    obj_floor: int | None,
    floor_min: int | None,
    floor_max: int | None,
) -> bool:
    """
    Match object floor against subscription floor range.

    Args:
        obj_floor: Object's floor number (0=basement, negative=underground)
        floor_min: Minimum floor (inclusive), None = no limit
        floor_max: Maximum floor (inclusive), None = no limit

    Returns:
        True if floor matches the range
    """
    if obj_floor is None:
        return True  # No floor info, don't filter

    if floor_min is not None and obj_floor < floor_min:
        return False
    if floor_max is not None and obj_floor > floor_max:
        return False
    return True


def match_object_to_subscription(obj: dict, sub: dict) -> bool:
    """
    Check if an object matches a subscription's criteria.

    Matching logic:
    - For list criteria (kind, section, layout, shape, etc.):
      object value must be IN the list
    - For range criteria (price, area):
      object value must be within range
    - For exclude_rooftop: object must not be rooftop addition
    - For gender: object gender must match (or be "all")
    - For pet_required: object must allow pets

    Args:
        obj: Object data (DBReadyData or Redis object)
        sub: Subscription criteria

    Returns:
        True if object matches all criteria
    """
    # Price range
    if sub.get("price_min") is not None or sub.get("price_max") is not None:
        obj_price = obj.get("price", 0)
        if isinstance(obj_price, str):
            obj_price = int(obj_price.replace(",", "")) if obj_price else 0

        if sub.get("price_min") is not None and obj_price < sub["price_min"]:
            return False
        if sub.get("price_max") is not None and obj_price > sub["price_max"]:
            return False

    # Kind (property type) - obj.kind in sub.kind list
    if sub.get("kind"):
        obj_kind = obj.get("kind")
        if obj_kind is not None and obj_kind not in sub["kind"]:
            return False

    # Section (district) - obj.section in sub.section list
    if sub.get("section"):
        obj_section = obj.get("section")
        if obj_section is not None and obj_section not in sub["section"]:
            return False

    # Shape (建物型態) - obj.shape in sub.shape list
    # 1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅
    if sub.get("shape"):
        obj_shape = obj.get("shape")
        if obj_shape is not None and obj_shape not in sub["shape"]:
            return False

    # Area range
    if sub.get("area_min") is not None or sub.get("area_max") is not None:
        obj_area = obj.get("area", 0) or 0

        if sub.get("area_min") is not None and obj_area < float(sub["area_min"]):
            return False
        if sub.get("area_max") is not None and obj_area > float(sub["area_max"]):
            return False

    # Layout (格局) - obj.layout in sub.layout list
    # sub.layout is like [1, 2, 3, 4] where 4 means 4+
    if sub.get("layout"):
        obj_layout = obj.get("layout")
        if obj_layout is not None:
            matched = False
            for required in sub["layout"]:
                if required == 4:  # 4房以上
                    if obj_layout >= 4:
                        matched = True
                        break
                elif obj_layout == required:
                    matched = True
                    break
            if not matched:
                return False

    # Bathroom (衛浴) - obj.bathroom in sub.bathroom list
    # sub.bathroom is like [1, 2, 3, 4] where 4 means 4+
    if sub.get("bathroom"):
        obj_bathroom = obj.get("bathroom")
        if obj_bathroom is not None:
            matched = False
            for required in sub["bathroom"]:
                if required == 4:  # 4衛以上
                    if obj_bathroom >= 4:
                        matched = True
                        break
                elif required == obj_bathroom:
                    matched = True
                    break
            if not matched:
                return False

    # Floor (樓層) - use floor_min/floor_max for numeric comparison
    floor_min = sub.get("floor_min")
    floor_max = sub.get("floor_max")
    if floor_min is not None or floor_max is not None:
        obj_floor = obj.get("floor")
        if not match_floor(obj_floor, floor_min, floor_max):
            return False

    # Fitment (裝潢) - obj.fitment in sub.fitment list
    # 99=新裝潢, 3=中檔裝潢, 4=高檔裝潢
    if sub.get("fitment"):
        obj_fitment = obj.get("fitment")
        if obj_fitment is not None and obj_fitment not in sub["fitment"]:
            return False

    # Exclude rooftop addition (排除頂樓加蓋)
    if sub.get("exclude_rooftop"):
        if obj.get("is_rooftop"):
            return False

    # Gender restriction (性別限制)
    # sub.gender: "boy" = wants male-only or all, "girl" = wants female-only or all
    if sub.get("gender"):
        obj_gender = obj.get("gender", "all")
        if sub["gender"] == "boy" and obj_gender not in ["boy", "all"]:
            return False
        if sub["gender"] == "girl" and obj_gender not in ["girl", "all"]:
            return False

    # Pet required (需要可養寵物)
    if sub.get("pet_required"):
        # pet_allowed defaults to False, only True if explicitly allowed
        if not obj.get("pet_allowed"):
            return False

    # Other (features) - compare subscription.other with object.other (both are codes)
    if sub.get("other"):
        obj_other = {code.lower() for code in (obj.get("other", []) or [])}
        sub_other = {f.lower() for f in sub["other"]}
        # All subscription features must be present in object
        if not sub_other <= obj_other:
            return False

    # Options (設備) - sub.options must be subset of obj.options
    if sub.get("options"):
        obj_options = {o.lower() for o in (obj.get("options", []) or [])}
        sub_options = {o.lower() for o in sub["options"]}
        if not sub_options <= obj_options:
            return False

    return True
