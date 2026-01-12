"""
Rule parsing utilities.

Parse gender restrictions and pet policies from rental rules.
"""

from typing import Optional


def parse_rule(rule: Optional[str]) -> dict:
    """
    Parse gender restriction and pet policy from service.rule.

    Args:
        rule: Rule string from detail page API
              (e.g., "此房屋限男生租住，不可養寵物")

    Returns:
        dict with keys:
            - gender: "boy" | "girl" | "all"
            - pet_allowed: True | False | None

    Examples:
        >>> parse_rule("此房屋限男生租住，不可養寵物")
        {"gender": "boy", "pet_allowed": False}
        >>> parse_rule("此房屋男女皆可租住，可養寵物")
        {"gender": "all", "pet_allowed": True}
        >>> parse_rule("此房屋限女生租住，不可養寵物")
        {"gender": "girl", "pet_allowed": False}
        >>> parse_rule(None)
        {"gender": "all", "pet_allowed": None}
    """
    if not rule:
        return {"gender": "all", "pet_allowed": None}

    # Parse gender restriction
    gender = "all"
    if "限男" in rule:
        gender = "boy"
    elif "限女" in rule:
        gender = "girl"

    # Parse pet policy
    pet_allowed: Optional[bool] = None
    if "可養寵" in rule or "可以養" in rule:
        pet_allowed = True
    elif "不可養" in rule or "禁養" in rule:
        pet_allowed = False

    return {"gender": gender, "pet_allowed": pet_allowed}
