"""
Equipment/Options mapping (中文 → 代號).

Used by: parser.py (convert detail page data), checker.py (matching)
"""

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
