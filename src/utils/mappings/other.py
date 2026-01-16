"""
Other (features) mapping (中文 → 代號).
"""

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
