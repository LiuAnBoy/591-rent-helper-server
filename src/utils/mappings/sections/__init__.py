"""
Section mappings for 591 regions.

Each region has its own module with district name to section code mapping.
"""

from src.utils.mappings.sections.new_taipei import NEW_TAIPEI_SECTIONS
from src.utils.mappings.sections.taipei import TAIPEI_SECTIONS

# Region code to section mapping
SECTION_MAPPINGS: dict[int, dict[str, int]] = {
    1: TAIPEI_SECTIONS,
    3: NEW_TAIPEI_SECTIONS,
}


def get_section_from_address(region: int, address_raw: str) -> int | None:
    """
    Extract section code from address_raw.

    Args:
        region: Region code (1=Taipei, 3=New Taipei)
        address_raw: Address string (e.g., "北投區-中央北路四段")

    Returns:
        Section code or None if not found
    """
    if not address_raw:
        return None

    mapping = SECTION_MAPPINGS.get(region)
    if not mapping:
        return None

    # Extract district name (before "-")
    district = address_raw.split("-")[0].strip()

    return mapping.get(district)


__all__ = [
    "TAIPEI_SECTIONS",
    "NEW_TAIPEI_SECTIONS",
    "SECTION_MAPPINGS",
    "get_section_from_address",
]
