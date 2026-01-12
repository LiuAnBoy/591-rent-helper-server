"""
Layout parsing utilities.

Parse room/hall/bathroom layout from rental data.
"""

import re
from typing import Optional


def parse_layout_str(text: str) -> Optional[str]:
    """
    Extract layout string from page text.

    Args:
        text: Page text content

    Returns:
        Layout string like "2房1廳1衛" or None
    """
    if not text:
        return None

    # Match patterns like "2房1廳1衛", "3房2廳", "1房"
    match = re.search(r"(\d+房\d*廳?\d*衛?)", text)
    return match.group(1) if match else None


def parse_layout_num(layout_str: Optional[str]) -> Optional[int]:
    """
    Extract room count from layout string.

    Args:
        layout_str: Layout string like "2房1廳1衛"

    Returns:
        Room count as integer or None
    """
    if not layout_str:
        return None

    match = re.search(r"(\d+)房", layout_str)
    return int(match.group(1)) if match else None


def parse_bathroom_num(layout_str: Optional[str]) -> Optional[int]:
    """
    Extract bathroom count from layout string.

    Args:
        layout_str: Layout string like "2房1廳1衛"

    Returns:
        Bathroom count as integer or None
    """
    if not layout_str:
        return None

    match = re.search(r"(\d+)衛", layout_str)
    return int(match.group(1)) if match else None
