"""
Matching module for subscription filtering and object matching.

This module provides functions to match rental objects against
user subscription criteria.
"""

from src.matching.matcher import (
    extract_floor_number,
    match_area,
    match_floor,
    match_full,
    match_object_to_subscription,
    match_price,
    match_quick,
    parse_area_value,
    parse_price_value,
)
from src.matching.pre_filter import (
    filter_objects,
    filter_redis_objects,
    should_fetch_detail,
    should_match_redis_object,
)

__all__ = [
    # Parsing functions
    "parse_price_value",
    "parse_area_value",
    # Floor functions
    "extract_floor_number",
    "match_floor",
    # Matching functions
    "match_price",
    "match_area",
    "match_quick",
    "match_full",
    "match_object_to_subscription",
    # Pre-filter functions
    "should_fetch_detail",
    "should_match_redis_object",
    "filter_objects",
    "filter_redis_objects",
]
