"""
Pre-filter module for list page data.

Filters objects based on list page data (price, area) before fetching detail pages.
This reduces unnecessary requests to 591 by skipping objects that won't match
any subscription.
"""

import re
from decimal import InvalidOperation

from loguru import logger

from src.crawler.types import ListRawData

pre_filter_log = logger.bind(module="PreFilter")


def parse_price(price_raw: str) -> int | None:
    """
    Parse price from raw string.

    Args:
        price_raw: Price string from list page (e.g., "8,500元/月", "15,000-20,000元/月")

    Returns:
        Parsed price as integer, or None if parsing fails.
        For ranges, returns the lower bound.
    """
    if not price_raw:
        return None

    # Remove commas and whitespace
    cleaned = price_raw.replace(",", "").replace(" ", "")

    # Handle "面議" (negotiable) - return None to indicate unknown
    if "面議" in cleaned:
        return None

    # Try to find price patterns
    # Pattern 1: Range "15000-20000" - take lower bound
    range_match = re.search(r"(\d+)\s*[-~]\s*(\d+)", cleaned)
    if range_match:
        try:
            return int(range_match.group(1))
        except ValueError:
            pass

    # Pattern 2: Single number "8500" or "8500元/月"
    num_match = re.search(r"(\d+)", cleaned)
    if num_match:
        try:
            return int(num_match.group(1))
        except ValueError:
            pass

    pre_filter_log.debug(f"Failed to parse price: {price_raw}")
    return None


def parse_area(area_raw: str) -> float | None:
    """
    Parse area from raw string.

    Args:
        area_raw: Area string from list page (e.g., "10坪", "約10坪", "10~15坪")

    Returns:
        Parsed area as float, or None if parsing fails.
        For ranges, returns the lower bound.
    """
    if not area_raw:
        return None

    # Remove common prefixes and whitespace
    cleaned = area_raw.replace(" ", "").replace("約", "")

    # Pattern 1: Range "10~15坪" - take lower bound
    range_match = re.search(r"([\d.]+)\s*[-~]\s*([\d.]+)", cleaned)
    if range_match:
        try:
            return float(range_match.group(1))
        except ValueError:
            pass

    # Pattern 2: Single number "10坪" or "10.5坪"
    num_match = re.search(r"([\d.]+)", cleaned)
    if num_match:
        try:
            return float(num_match.group(1))
        except ValueError:
            pass

    pre_filter_log.debug(f"Failed to parse area: {area_raw}")
    return None


def should_fetch_detail(list_data: ListRawData, subscriptions: list[dict]) -> bool:
    """
    Check if any subscription MIGHT match this object based on list data.

    The check is intentionally loose - we'd rather fetch extra detail pages
    than miss potential matches.

    Args:
        list_data: Raw data from list page
        subscriptions: List of subscription dictionaries

    Returns:
        True if detail page should be fetched (might match some subscription).
        False if definitely won't match any subscription (skip detail).
    """
    # No subscriptions = nothing to match against
    if not subscriptions:
        return False

    price = parse_price(list_data.get("price_raw", ""))
    area = parse_area(list_data.get("area_raw", ""))

    for sub in subscriptions:
        # If parsing failed, assume it might match (be conservative)
        passes_price = True
        passes_area = True

        # Price check
        if price is not None:
            price_max = sub.get("price_max")
            price_min = sub.get("price_min")

            if price_max is not None and price > price_max:
                passes_price = False
            if price_min is not None and price < price_min:
                passes_price = False

        # Area check
        if area is not None:
            area_max = sub.get("area_max")
            area_min = sub.get("area_min")

            # Convert Decimal to float for comparison
            if area_max is not None:
                try:
                    area_max = float(area_max)
                except (ValueError, TypeError, InvalidOperation):
                    area_max = None

            if area_min is not None:
                try:
                    area_min = float(area_min)
                except (ValueError, TypeError, InvalidOperation):
                    area_min = None

            if area_max is not None and area > area_max:
                passes_area = False
            if area_min is not None and area < area_min:
                passes_area = False

        # If this subscription might match, fetch detail
        if passes_price and passes_area:
            return True

    # No subscription could match
    return False


def filter_objects(
    list_items: list[ListRawData],
    subscriptions: list[dict],
) -> tuple[list[ListRawData], int]:
    """
    Filter list items to only those that might match subscriptions.

    Args:
        list_items: List of raw data from list pages
        subscriptions: List of subscription dictionaries

    Returns:
        Tuple of (filtered_items, skipped_count)
    """
    if not subscriptions:
        # No subscriptions = nothing to match, skip all
        return [], len(list_items)

    filtered = []
    skipped = 0

    for item in list_items:
        if should_fetch_detail(item, subscriptions):
            filtered.append(item)
        else:
            skipped += 1

    return filtered, skipped
