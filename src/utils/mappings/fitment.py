"""
Fitment mapping (中文 → 代號).

99=新裝潢, 3=中檔裝潢, 4=高檔裝潢
Unrecognized values (簡易裝潢, --, etc.) → None
"""

FITMENT_NAME_TO_CODE: dict[str, int] = {
    "新裝潢": 99,
    "中檔裝潢": 3,
    "高檔裝潢": 4,
}


def convert_fitment_to_code(fitment_name: str | None) -> int | None:
    """
    Convert fitment name to code.

    Args:
        fitment_name: Chinese fitment name (e.g., "中檔裝潢")

    Returns:
        Fitment code (99, 3, 4) or None if unrecognized

    Example:
        >>> convert_fitment_to_code("中檔裝潢")
        3
        >>> convert_fitment_to_code("簡易裝潢")
        None
        >>> convert_fitment_to_code("--")
        None
    """
    if not fitment_name or fitment_name == "--":
        return None
    return FITMENT_NAME_TO_CODE.get(fitment_name)
