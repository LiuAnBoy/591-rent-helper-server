"""
Shared constants for 591 crawler.

Contains mapping dictionaries for converting Chinese names to standardized codes.
"""

# Equipment/Options mapping (中文 → 代號)
# Used by: parser.py (convert detail page data), checker.py (matching)
OPTIONS_NAME_TO_CODE: dict[str, str] = {
    # cold - 冷氣
    "冷氣": "cold",
    "空調": "cold",
    # washer - 洗衣機
    "洗衣機": "washer",
    "洗衣": "washer",
    # icebox - 冰箱
    "冰箱": "icebox",
    # hotwater - 熱水器
    "熱水器": "hotwater",
    "熱水": "hotwater",
    # naturalgas - 天然瓦斯
    "天然瓦斯": "naturalgas",
    "天然氣": "naturalgas",
    "瓦斯": "naturalgas",
    # broadband - 網路
    "網路": "broadband",
    "寬頻": "broadband",
    "wifi": "broadband",
    "WiFi": "broadband",
    # bed - 床
    "床": "bed",
    "床鋪": "bed",
    # tv - 電視
    "電視": "tv",
    # wardrobe - 衣櫃
    "衣櫃": "wardrobe",
    # cable - 第四台
    "第四台": "cable",
    # sofa - 沙發
    "沙發": "sofa",
    # desk - 桌椅
    "桌椅": "desk",
    # balcony - 陽台
    "陽台": "balcony",
    # lift - 電梯
    "電梯": "lift",
    # parking - 車位
    "車位": "parking",
}

# Other (features) mapping (中文 → 代號)
OTHER_NAME_TO_CODE: dict[str, str] = {
    # near_subway - 近捷運
    "近捷運": "near_subway",
    "捷運": "near_subway",
    "mrt": "near_subway",
    # pet - 可養寵物
    "可養寵": "pet",
    "可養寵物": "pet",
    "寵物": "pet",
    # cook - 可開伙
    "可開伙": "cook",
    "開伙": "cook",
    "廚房": "cook",
    # lift - 有電梯
    "有電梯": "lift",
    "電梯": "lift",
    # balcony_1 - 有陽台
    "有陽台": "balcony_1",
    "陽台": "balcony_1",
    # cartplace - 有車位
    "車位": "cartplace",
    "停車": "cartplace",
    # newPost - 新上架
    "新上架": "newPost",
    # lease - 短租
    "短租": "lease",
    "可短期租賃": "lease",
    # social-housing - 社會住宅
    "社會住宅": "social-housing",
    # rental-subsidy - 租金補貼
    "租金補貼": "rental-subsidy",
    # elderly-friendly - 高齡友善
    "高齡友善": "elderly-friendly",
    # tax-deductible - 可報稅
    "可報稅": "tax-deductible",
    # naturalization - 可入籍
    "可入籍": "naturalization",
}


# Shape mapping (中文 → 代號)
# 1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅
SHAPE_NAME_TO_CODE: dict[str, int] = {
    "公寓": 1,
    "電梯大樓": 2,
    "透天厝": 3,
    "別墅": 4,
}


# Fitment mapping (中文 → 代號)
# 99=新裝潢, 3=中檔裝潢, 4=高檔裝潢
# Unrecognized values (簡易裝潢, --, etc.) → None
FITMENT_NAME_TO_CODE: dict[str, int] = {
    "新裝潢": 99,
    "中檔裝潢": 3,
    "高檔裝潢": 4,
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


def convert_options_to_codes(options: list[str]) -> list[str]:
    """
    Convert equipment names to standardized codes.

    Args:
        options: List of Chinese equipment names from detail page

    Returns:
        List of standardized codes (duplicates removed)

    Example:
        >>> convert_options_to_codes(["冰箱", "洗衣機", "冷氣"])
        ["icebox", "washer", "cold"]
    """
    codes = set()
    for name in options:
        # Direct match
        if name in OPTIONS_NAME_TO_CODE:
            codes.add(OPTIONS_NAME_TO_CODE[name])
        else:
            # Partial match (e.g., "冷氣機" contains "冷氣")
            for key, code in OPTIONS_NAME_TO_CODE.items():
                if key in name:
                    codes.add(code)
                    break
    return list(codes)


def convert_other_to_codes(tags: list[str]) -> list[str]:
    """
    Convert tag names to other codes.

    Args:
        tags: List of Chinese tag names

    Returns:
        List of standardized codes (duplicates removed)
    """
    codes = set()
    for name in tags:
        if name in OTHER_NAME_TO_CODE:
            codes.add(OTHER_NAME_TO_CODE[name])
        else:
            for key, code in OTHER_NAME_TO_CODE.items():
                if key in name:
                    codes.add(code)
                    break
    return list(codes)
