"""
Floor parsing utilities.

Parse floor-related fields from rental object data.
"""

import re
from typing import Optional


def parse_floor(floor_str: Optional[str]) -> tuple[Optional[int], Optional[int], bool]:
    """
    Parse floor string into structured data.

    Args:
        floor_str: Original string like "3F/5F" or "頂層加蓋/5F" or "B1/10F"

    Returns:
        (floor, total_floor, is_rooftop)
        - floor: Current floor number (0=rooftop, negative=basement)
        - total_floor: Total floors in building
        - is_rooftop: Whether it's a rooftop addition

    Examples:
        >>> parse_floor("3F/5F")
        (3, 5, False)
        >>> parse_floor("頂層加蓋/5F")
        (0, 5, True)
        >>> parse_floor("B1/10F")
        (-1, 10, False)
        >>> parse_floor("B2/8F")
        (-2, 8, False)
        >>> parse_floor("整棟")
        (None, None, False)
        >>> parse_floor(None)
        (None, None, False)
    """
    if not floor_str:
        return None, None, False

    # Check for rooftop addition
    is_rooftop = "頂" in floor_str and "加" in floor_str

    # Parse total floor (e.g., "/5F" -> 5)
    total_match = re.search(r"/(\d+)F", floor_str, re.IGNORECASE)
    total_floor = int(total_match.group(1)) if total_match else None

    # Parse current floor
    floor: Optional[int] = None
    if is_rooftop:
        floor = 0
    elif floor_str.upper().startswith("B"):
        # Basement: B1 -> -1, B2 -> -2
        basement_match = re.match(r"B(\d+)", floor_str, re.IGNORECASE)
        floor = -int(basement_match.group(1)) if basement_match else -1
    else:
        # Normal floor: "3F" -> 3
        floor_match = re.match(r"(\d+)F", floor_str, re.IGNORECASE)
        floor = int(floor_match.group(1)) if floor_match else None

    return floor, total_floor, is_rooftop


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
