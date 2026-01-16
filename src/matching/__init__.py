"""
Matching module for subscription filtering and object matching.

This module provides functions to match rental objects against
user subscription criteria.
"""

from src.matching.matcher import (
    extract_floor_number,
    match_floor,
    match_object_to_subscription,
)

__all__ = [
    "extract_floor_number",
    "match_floor",
    "match_object_to_subscription",
]
