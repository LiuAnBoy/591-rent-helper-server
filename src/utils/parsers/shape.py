"""
Shape (building type) parsing utilities.

Parse building type from rental data.
"""

from typing import Optional

# Building type mapping
# 1 = apartment (walk-up)
# 2 = elevator building
# 3 = townhouse
# 4 = villa
SHAPE_MAPPING = {
    "公寓": 1,
    "電梯大樓": 2,
    "透天厝": 3,
    "透天": 3,
    "別墅": 4,
}


def parse_shape(text: str) -> Optional[int]:
    """
    Parse building type (shape) from page text.

    Args:
        text: Page text content or building type string

    Returns:
        Shape code: 1 (apartment), 2 (elevator), 3 (townhouse), 4 (villa), or None
    """
    if not text:
        return None

    for name, code in SHAPE_MAPPING.items():
        if name in text:
            return code

    return None


def get_shape_name(shape_code: Optional[int]) -> Optional[str]:
    """
    Get shape name from code.

    Args:
        shape_code: Shape code (1-4)

    Returns:
        Shape name or None
    """
    if shape_code is None:
        return None

    code_to_name = {v: k for k, v in SHAPE_MAPPING.items()}
    return code_to_name.get(shape_code)
