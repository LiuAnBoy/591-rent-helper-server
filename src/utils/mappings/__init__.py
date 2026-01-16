"""
Mapping modules for 591 crawler.

Contains mapping dictionaries for converting Chinese names to standardized codes.
"""

from src.utils.mappings.fitment import FITMENT_NAME_TO_CODE, convert_fitment_to_code
from src.utils.mappings.kind import KIND_NAME_TO_CODE, convert_kind_name_to_code
from src.utils.mappings.options import OPTIONS_NAME_TO_CODE, convert_options_to_codes
from src.utils.mappings.other import OTHER_NAME_TO_CODE, convert_other_to_codes
from src.utils.mappings.shape import SHAPE_NAME_TO_CODE, convert_shape_to_code

__all__ = [
    # Options
    "OPTIONS_NAME_TO_CODE",
    "convert_options_to_codes",
    # Other
    "OTHER_NAME_TO_CODE",
    "convert_other_to_codes",
    # Kind
    "KIND_NAME_TO_CODE",
    "convert_kind_name_to_code",
    # Shape
    "SHAPE_NAME_TO_CODE",
    "convert_shape_to_code",
    # Fitment
    "FITMENT_NAME_TO_CODE",
    "convert_fitment_to_code",
]
