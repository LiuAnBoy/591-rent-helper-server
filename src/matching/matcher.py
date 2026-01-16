"""
Subscription matching logic for rental objects.

This module provides functions to match rental objects against
user subscription criteria.
"""

import re
from decimal import InvalidOperation

from loguru import logger

matcher_log = logger.bind(module="Matcher")


# ============================================================
# Parsing functions
# ============================================================


def parse_price_value(value: str | int | None) -> int | None:
    """
    Parse price from various formats.

    Args:
        value: Price as raw string ("10,000", "8,500元/月") or int (10000)

    Returns:
        Price as int or None if parsing fails

    Examples:
        >>> parse_price_value(10000)
        10000
        >>> parse_price_value("10,000")
        10000
        >>> parse_price_value("8,500元/月")
        8500
        >>> parse_price_value("15000-20000元/月")
        15000
        >>> parse_price_value("面議")
        None
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if not value:
            return None

        # Handle "面議" (negotiable)
        if "面議" in value:
            return None

        # Remove commas and whitespace
        cleaned = value.replace(",", "").replace(" ", "")

        # Pattern 1: Range "15000-20000" - take lower bound
        range_match = re.search(r"(\d+)\s*[-~]\s*(\d+)", cleaned)
        if range_match:
            try:
                return int(range_match.group(1))
            except ValueError:
                pass

        # Pattern 2: Single number
        num_match = re.search(r"(\d+)", cleaned)
        if num_match:
            try:
                return int(num_match.group(1))
            except ValueError:
                pass

    return None


def parse_area_value(value: str | float | int | None) -> float | None:
    """
    Parse area from various formats.

    Args:
        value: Area as raw string ("25.5坪", "約10坪") or float (25.5)

    Returns:
        Area as float or None if parsing fails

    Examples:
        >>> parse_area_value(25.5)
        25.5
        >>> parse_area_value("25.5坪")
        25.5
        >>> parse_area_value("約10坪")
        10.0
        >>> parse_area_value("10~15坪")
        10.0
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if not value:
            return None

        # Remove common prefixes
        cleaned = value.replace(" ", "").replace("約", "")

        # Pattern 1: Range "10~15坪" - take lower bound
        range_match = re.search(r"([\d.]+)\s*[-~]\s*([\d.]+)", cleaned)
        if range_match:
            try:
                return float(range_match.group(1))
            except ValueError:
                pass

        # Pattern 2: Single number
        num_match = re.search(r"([\d.]+)", cleaned)
        if num_match:
            try:
                return float(num_match.group(1))
            except ValueError:
                pass

    return None


def safe_float(value, default: float | None = None) -> float | None:
    """
    Safely convert Decimal or other numeric types to float.

    Args:
        value: Value to convert
        default: Default if conversion fails

    Returns:
        Float value or default
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError, InvalidOperation):
        return default


# ============================================================
# Floor functions
# ============================================================


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


# ============================================================
# Matching functions
# ============================================================


def match_price(
    obj_price: str | int | None,
    price_min: int | None,
    price_max: int | None,
) -> bool:
    """
    Check if price is within range.

    Supports both raw string ("10,000") and parsed int (10000) formats.

    Args:
        obj_price: Object's price (raw or parsed)
        price_min: Minimum price (inclusive), None = no limit
        price_max: Maximum price (inclusive), None = no limit

    Returns:
        True if price matches (or cannot be determined)
    """
    price = parse_price_value(obj_price)
    if price is None:
        return True  # Cannot parse, assume match (conservative)

    if price_min is not None and price < price_min:
        return False
    if price_max is not None and price > price_max:
        return False
    return True


def match_area(
    obj_area: str | float | None,
    area_min: float | None,
    area_max: float | None,
) -> bool:
    """
    Check if area is within range.

    Supports both raw string ("25.5坪") and parsed float (25.5) formats.

    Args:
        obj_area: Object's area (raw or parsed)
        area_min: Minimum area (inclusive), None = no limit
        area_max: Maximum area (inclusive), None = no limit

    Returns:
        True if area matches (or cannot be determined)
    """
    area = parse_area_value(obj_area)
    if area is None:
        return True  # Cannot parse, assume match (conservative)

    # Convert Decimal to float for comparison
    area_min_f = safe_float(area_min)
    area_max_f = safe_float(area_max)

    if area_min_f is not None and area < area_min_f:
        return False
    if area_max_f is not None and area > area_max_f:
        return False
    return True


def match_quick(obj: dict, sub: dict) -> bool:
    """
    Quick filter using basic criteria only (price, area).

    Used by pre_filter to decide if detail page should be fetched.
    Intentionally loose - we'd rather fetch extra than miss matches.

    Supports both raw data (ListRawData) and parsed data (DBReadyData).

    Args:
        obj: Object data (can be ListRawData or DBReadyData)
        sub: Subscription criteria

    Returns:
        True if object might match subscription
    """
    # Price check - support both raw and parsed formats
    price_value = obj.get("price") or obj.get("price_raw")
    if not match_price(price_value, sub.get("price_min"), sub.get("price_max")):
        return False

    # Area check - support both raw and parsed formats
    area_value = obj.get("area") or obj.get("area_raw")
    if not match_area(area_value, sub.get("area_min"), sub.get("area_max")):
        return False

    return True


def match_full(obj: dict, sub: dict) -> bool:
    """
    Full match using all subscription criteria.

    This is the main matching function for subscription notifications.

    Args:
        obj: Object data (DBReadyData format expected)
        sub: Subscription criteria

    Returns:
        True if object matches all criteria
    """
    # Quick check first (price, area)
    if not match_quick(obj, sub):
        return False

    # Kind (property type)
    if sub.get("kind"):
        obj_kind = obj.get("kind")
        if obj_kind is not None and obj_kind not in sub["kind"]:
            return False

    # Section (district)
    if sub.get("section"):
        obj_section = obj.get("section")
        if obj_section is not None and obj_section not in sub["section"]:
            return False

    # Shape (建物型態)
    if sub.get("shape"):
        obj_shape = obj.get("shape")
        if obj_shape is not None and obj_shape not in sub["shape"]:
            return False

    # Layout (格局) - 4 means 4+
    if sub.get("layout"):
        obj_layout = obj.get("layout")
        if obj_layout is not None:
            matched = False
            for required in sub["layout"]:
                if required == 4 and obj_layout >= 4:
                    matched = True
                    break
                elif obj_layout == required:
                    matched = True
                    break
            if not matched:
                return False

    # Bathroom (衛浴) - 4 means 4+
    if sub.get("bathroom"):
        obj_bathroom = obj.get("bathroom")
        if obj_bathroom is not None:
            matched = False
            for required in sub["bathroom"]:
                if required == 4 and obj_bathroom >= 4:
                    matched = True
                    break
                elif required == obj_bathroom:
                    matched = True
                    break
            if not matched:
                return False

    # Floor (樓層)
    floor_min = sub.get("floor_min")
    floor_max = sub.get("floor_max")
    if floor_min is not None or floor_max is not None:
        obj_floor = obj.get("floor")
        if not match_floor(obj_floor, floor_min, floor_max):
            return False

    # Fitment (裝潢)
    if sub.get("fitment"):
        obj_fitment = obj.get("fitment")
        if obj_fitment is not None and obj_fitment not in sub["fitment"]:
            return False

    # Exclude rooftop addition
    if sub.get("exclude_rooftop") and obj.get("is_rooftop"):
        return False

    # Gender restriction
    if sub.get("gender"):
        obj_gender = obj.get("gender", "all")
        if sub["gender"] == "boy" and obj_gender not in ["boy", "all"]:
            return False
        if sub["gender"] == "girl" and obj_gender not in ["girl", "all"]:
            return False

    # Pet required
    if sub.get("pet_required") and not obj.get("pet_allowed"):
        return False

    # Other (features)
    if sub.get("other"):
        obj_other = {code.lower() for code in (obj.get("other", []) or [])}
        sub_other = {f.lower() for f in sub["other"]}
        if not sub_other <= obj_other:
            return False

    # Options (設備)
    if sub.get("options"):
        obj_options = {o.lower() for o in (obj.get("options", []) or [])}
        sub_options = {o.lower() for o in sub["options"]}
        if not sub_options <= obj_options:
            return False

    return True


# Backward compatibility alias
def match_object_to_subscription(obj: dict, sub: dict) -> bool:
    """
    Check if an object matches a subscription's criteria.

    Note: This is an alias for match_full() for backward compatibility.
    """
    return match_full(obj, sub)
