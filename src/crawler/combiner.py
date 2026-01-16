"""
Combiner for merging List and Detail raw data.

This module combines raw data from List and Detail pages according to
specific priority rules. Part of the ETL Extract/Combine phase.
"""

from src.crawler.types import CombinedRawData, DetailRawData, ListRawData


def combine_raw_data(
    list_data: ListRawData,
    detail_data: DetailRawData,
) -> CombinedRawData:
    """
    Combine raw data from List and Detail pages.

    Priority rules:
    - id, url, kind_name: from List
    - title, price_raw, address_raw, floor_raw, area_raw, layout_raw: Detail > List
    - tags: merged from both (deduplicated)
    - region, section, kind: from Detail
    - gender_raw, shape_raw, fitment_raw, options: from Detail only
    - surrounding_type, surrounding_raw: from Detail only

    Args:
        list_data: Raw data from list page
        detail_data: Raw data from detail page

    Returns:
        CombinedRawData with merged fields
    """
    # Merge tags (deduplicated)
    list_tags = list_data.get("tags", [])
    detail_tags = detail_data.get("tags", [])
    merged_tags = list(set(list_tags + detail_tags))

    # Build combined result
    result: CombinedRawData = {
        # From List only
        "id": list_data.get("id", ""),
        "url": list_data.get("url", ""),
        "kind_name": list_data.get("kind_name", ""),
        # Detail > List (Detail priority)
        "title": detail_data.get("title") or list_data.get("title", ""),
        "price_raw": detail_data.get("price_raw") or list_data.get("price_raw", ""),
        "address_raw": detail_data.get("address_raw")
        or list_data.get("address_raw", ""),
        "floor_raw": detail_data.get("floor_raw") or list_data.get("floor_raw", ""),
        "area_raw": detail_data.get("area_raw") or list_data.get("area_raw", ""),
        "layout_raw": detail_data.get("layout_raw") or list_data.get("layout_raw", ""),
        # Merged
        "tags": merged_tags,
        # From Detail (with List fallback for section)
        "region": detail_data.get("region", ""),
        "section": detail_data.get("section") or list_data.get("section", ""),
        "kind": detail_data.get("kind", ""),
        "gender_raw": detail_data.get("gender_raw"),
        "shape_raw": detail_data.get("shape_raw"),
        "fitment_raw": detail_data.get("fitment_raw"),
        "options": detail_data.get("options", []),
        "surrounding_type": detail_data.get("surrounding_type"),
        "surrounding_raw": detail_data.get("surrounding_raw"),
        "has_detail": True,
    }

    return result


def combine_with_detail_only(
    detail_data: DetailRawData, url: str = ""
) -> CombinedRawData:
    """
    Create CombinedRawData from detail data only (when list data is unavailable).

    This is useful when fetching a single object by ID without list context.

    Args:
        detail_data: Raw data from detail page
        url: Optional URL (will be generated if not provided)

    Returns:
        CombinedRawData with fields from detail only
    """
    object_id = detail_data.get("id", 0)
    if not url:
        url = f"https://rent.591.com.tw/{object_id}"

    result: CombinedRawData = {
        "id": str(object_id),
        "url": url,
        "title": detail_data.get("title", ""),
        "price_raw": detail_data.get("price_raw", ""),
        "tags": detail_data.get("tags", []),
        "kind_name": "",  # Not available from detail
        "address_raw": detail_data.get("address_raw", ""),
        "surrounding_type": detail_data.get("surrounding_type"),
        "surrounding_raw": detail_data.get("surrounding_raw"),
        "region": detail_data.get("region", ""),
        "section": detail_data.get("section", ""),
        "kind": detail_data.get("kind", ""),
        "floor_raw": detail_data.get("floor_raw", ""),
        "layout_raw": detail_data.get("layout_raw", ""),
        "area_raw": detail_data.get("area_raw", ""),
        "gender_raw": detail_data.get("gender_raw"),
        "shape_raw": detail_data.get("shape_raw"),
        "fitment_raw": detail_data.get("fitment_raw"),
        "options": detail_data.get("options", []),
        "has_detail": True,
    }

    return result
