"""
Fitment/decoration parsing utilities.

Parse decoration level from rental data.
"""

from typing import Optional

# Fitment level mapping
# 99 = newly decorated (within 3 years)
# 3 = mid-range decoration
# 4 = high-end decoration
FITMENT_MAPPING = {
    "新裝潢": 99,
    "三年內": 99,
    "中檔": 3,
    "中檔裝潢": 3,
    "高檔": 4,
    "高檔裝潢": 4,
    "豪華裝潢": 4,
}


def parse_fitment(text: str) -> Optional[int]:
    """
    Parse fitment/decoration level from page text.

    Args:
        text: Page text content or decoration string

    Returns:
        Fitment code: 99 (new), 3 (mid-range), 4 (high-end), or None
    """
    if not text:
        return None

    for name, code in FITMENT_MAPPING.items():
        if name in text:
            return code

    return None
