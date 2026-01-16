"""
Kind mapping (中文 → 代號).

1=整層住家, 2=獨立套房, 3=分租套房, 4=雅房, 8=車位, 24=其他
"""

KIND_NAME_TO_CODE: dict[str, int] = {
    "整層住家": 1,
    "獨立套房": 2,
    "分租套房": 3,
    "雅房": 4,
    "車位": 8,
    "其他": 24,
}


def convert_kind_name_to_code(kind_name: str | None) -> int | None:
    """
    Convert kind name to code.

    Args:
        kind_name: Chinese kind name (e.g., "整層住家", "獨立套房")

    Returns:
        Kind code (1, 2, 3, 4, 8, 24) or None if unrecognized

    Example:
        >>> convert_kind_name_to_code("整層住家")
        1
        >>> convert_kind_name_to_code("車位")
        8
        >>> convert_kind_name_to_code("unknown")
        None
    """
    if not kind_name:
        return None
    return KIND_NAME_TO_CODE.get(kind_name)
