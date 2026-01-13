"""
Rule parsing utilities.

Parse gender restrictions and pet policies from rental rules.
"""


def parse_rule(rule: str | None) -> dict:
    """
    Parse gender restriction and pet policy from service.rule.

    Args:
        rule: Rule string from detail page API
              (e.g., "此房屋限男生租住，不可養寵物")

    Returns:
        dict with keys:
            - gender: "boy" | "girl" | "all"
            - pet_allowed: True | False (default False)

    Examples:
        >>> parse_rule("此房屋限男生租住，不可養寵物")
        {"gender": "boy", "pet_allowed": False}
        >>> parse_rule("此房屋男女皆可租住，可養寵物")
        {"gender": "all", "pet_allowed": True}
        >>> parse_rule("此房屋限女生租住，不可養寵物")
        {"gender": "girl", "pet_allowed": False}
        >>> parse_rule(None)
        {"gender": "all", "pet_allowed": False}
    """
    if not rule:
        return {"gender": "all", "pet_allowed": False}

    # Parse gender restriction
    gender = "all"
    if "限男" in rule:
        gender = "boy"
    elif "限女" in rule:
        gender = "girl"

    # Parse pet policy - only True if explicitly allowed
    pet_allowed = "可養寵物" in rule

    return {"gender": gender, "pet_allowed": pet_allowed}
