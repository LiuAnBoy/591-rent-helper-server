"""
Shape mapping (中文 → 代號).

1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅
"""

SHAPE_NAME_TO_CODE: dict[str, int] = {
    "公寓": 1,
    "電梯大樓": 2,
    "透天厝": 3,
    "別墅": 4,
}


def convert_shape_to_code(shape_name: str | None) -> int | None:
    """
    Convert shape name to code.

    Args:
        shape_name: Chinese shape name (e.g., "公寓", "電梯大樓")

    Returns:
        Shape code (1, 2, 3, 4) or None if unrecognized

    Example:
        >>> convert_shape_to_code("公寓")
        1
        >>> convert_shape_to_code("電梯大樓")
        2
        >>> convert_shape_to_code("unknown")
        None
    """
    if not shape_name:
        return None
    return SHAPE_NAME_TO_CODE.get(shape_name)
