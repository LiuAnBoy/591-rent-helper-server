"""
List page raw data extractor from NUXT data.

Extracts raw data from window.__NUXT__.data for Playwright fetcher.
Part of the ETL Extract phase.
"""

import logging

from src.crawler.extractors.types import ListRawData

logger = logging.getLogger(__name__)


def extract_list_raw_from_nuxt(
    nuxt_data: dict,
    region: int,
) -> list[ListRawData]:
    """
    Extract raw data from NUXT data structure.

    Args:
        nuxt_data: window.__NUXT__.data object from Playwright
        region: Region code

    Returns:
        List of ListRawData dictionaries
    """
    items, total = _find_items(nuxt_data)
    if not items:
        logger.warning("No items found in NUXT data")
        return []

    logger.debug(f"Found {len(items)} items (total: {total}) in NUXT data")

    results: list[ListRawData] = []
    for item in items:
        try:
            raw_data = _parse_item_raw_from_nuxt(item, region)
            if raw_data.get("id"):
                results.append(raw_data)
        except Exception as e:
            logger.warning(f"Failed to parse NUXT item: {e}")
            continue

    return results


def _find_items(nuxt_data: dict) -> tuple[list[dict], int]:
    """
    Find items array and total count in NUXT data structure.

    Args:
        nuxt_data: window.__NUXT__.data object

    Returns:
        Tuple of (items list, total count)
    """
    if not isinstance(nuxt_data, dict):
        return [], 0

    def search(data: dict) -> tuple[list[dict], int]:
        if isinstance(data, dict):
            for _key, value in data.items():
                if isinstance(value, dict):
                    if "items" in value and isinstance(value["items"], list):
                        items = value["items"]
                        total = value.get("total", len(items))
                        try:
                            total = int(total)
                        except (ValueError, TypeError):
                            total = len(items)
                        return items, total
                    result = search(value)
                    if result[0]:
                        return result
        return [], 0

    return search(nuxt_data)


def _parse_item_raw_from_nuxt(item: dict, region: int) -> ListRawData:
    """
    Parse a single item from NUXT structure into ListRawData.

    Args:
        item: Item dict from NUXT items array
        region: Region code

    Returns:
        ListRawData dictionary
    """
    result: ListRawData = {
        "region": region,
        "id": "",
        "url": "",
        "title": "",
        "price_raw": "",
        "tags": [],
        "kind_name": "",
        "area_raw": "",
        "floor_raw": "",
        "address_raw": "",
    }

    # ID
    item_id = item.get("id") or item.get("post_id")
    if item_id is not None:
        result["id"] = str(item_id)
        result["url"] = f"https://rent.591.com.tw/{item_id}"

    # Title
    result["title"] = item.get("title", "")

    # Price - format as "X元/月"
    price = item.get("price")
    if price is not None:
        result["price_raw"] = f"{price}元/月"

    # Tags - extract value from tag objects
    tags = item.get("tags", [])
    if tags:
        if isinstance(tags[0], dict):
            # NUXT format: [{"id": 2, "value": "近捷運"}, ...]
            result["tags"] = [tag.get("value") for tag in tags if tag.get("value")]
        else:
            # Simple string list
            result["tags"] = [str(t) for t in tags if t]

    # Kind name
    result["kind_name"] = item.get("kind_name", "") or item.get("kindName", "")

    # Note: layout is obtained from detail page for accuracy

    # Area - format as "X坪"
    area = item.get("area")
    if area is not None:
        if isinstance(area, (int, float)):
            result["area_raw"] = f"{area}坪"
        else:
            result["area_raw"] = str(area)

    # Floor
    floor_name = item.get("floor_name") or item.get("floorName")
    if floor_name:
        result["floor_raw"] = str(floor_name)

    # Address
    address = item.get("address") or item.get("section_str")
    if address:
        result["address_raw"] = str(address)

    return result


def get_total_from_nuxt(nuxt_data: dict) -> int:
    """
    Get total count from NUXT data.

    Args:
        nuxt_data: window.__NUXT__.data object

    Returns:
        Total count of items
    """
    _, total = _find_items(nuxt_data)
    return total
