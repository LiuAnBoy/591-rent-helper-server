"""
Pre-filter functions for subscription matching.

This module provides functions to quickly filter objects before
fetching detail pages, using only basic criteria (price, area).
"""

from loguru import logger

from src.matching.matcher import match_quick

pre_filter_log = logger.bind(module="PreFilter")


# ============================================================
# Single object checks
# ============================================================


def should_fetch_detail(list_data: dict, subscriptions: list[dict]) -> bool:
    """
    Check if any subscription MIGHT match this object based on list data.

    The check is intentionally loose - we'd rather fetch extra detail pages
    than miss potential matches.

    Args:
        list_data: Raw data from list page (ListRawData with price_raw, area_raw)
        subscriptions: List of subscription dictionaries

    Returns:
        True if detail page should be fetched (might match some subscription).
        False if definitely won't match any subscription (skip detail).
    """
    if not subscriptions:
        return False

    for sub in subscriptions:
        if match_quick(list_data, sub):
            return True

    return False


def should_match_redis_object(obj: dict, subscriptions: list[dict]) -> bool:
    """
    Check if any subscription MIGHT match this Redis cached object.

    Uses the same match_quick logic, which handles both raw strings
    (price_raw, area_raw) and parsed values (price, area).

    Args:
        obj: Object dictionary from Redis cache (with parsed fields)
        subscriptions: List of subscription dictionaries

    Returns:
        True if object might match some subscription.
        False if definitely won't match any subscription.
    """
    if not subscriptions:
        return False

    for sub in subscriptions:
        if match_quick(obj, sub):
            return True

    return False


# ============================================================
# Batch filter functions
# ============================================================


def filter_objects(
    list_items: list[dict],
    subscriptions: list[dict],
) -> tuple[list[dict], int]:
    """
    Filter list items to only those that might match subscriptions.

    Args:
        list_items: List of raw data from list pages
        subscriptions: List of subscription dictionaries

    Returns:
        Tuple of (filtered_items, skipped_count)
    """
    if not subscriptions:
        return [], len(list_items)

    filtered = []
    skipped = 0

    for item in list_items:
        if should_fetch_detail(item, subscriptions):
            filtered.append(item)
        else:
            skipped += 1

    return filtered, skipped


def filter_redis_objects(
    objects: list[dict],
    subscriptions: list[dict],
) -> tuple[list[dict], int]:
    """
    Filter Redis cached objects to only those that might match subscriptions.

    This is used by InstantNotify to pre-filter before fetching details.

    Args:
        objects: List of object dictionaries from Redis cache
        subscriptions: List of subscription dictionaries

    Returns:
        Tuple of (filtered_objects, skipped_count)
    """
    if not subscriptions:
        return [], len(objects)

    if not objects:
        return [], 0

    filtered = []
    skipped = 0

    for obj in objects:
        if should_match_redis_object(obj, subscriptions):
            filtered.append(obj)
        else:
            skipped += 1

    pre_filter_log.debug(f"Redis filter: {len(filtered)} passed, {skipped} skipped")
    return filtered, skipped
