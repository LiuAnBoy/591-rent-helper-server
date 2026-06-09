"""
Generic worker-count helpers for crawler fetching.

Source-agnostic: these compute concurrency based on batch / region counts and
carry no 591-specific knowledge, so any source can reuse them.
"""


def calculate_detail_workers(items_count: int) -> int:
    """
    Calculate optimal worker count for detail fetching.

    Args:
        items_count: Number of items to fetch

    Returns:
        Optimal worker count (0-3)
    """
    if items_count == 0:
        return 0
    if items_count <= 5:
        return 1
    if items_count <= 15:
        return 2
    return 3


def calculate_list_workers(regions_count: int) -> int:
    """
    Calculate optimal worker count for list fetching.

    Args:
        regions_count: Number of regions to fetch

    Returns:
        Optimal worker count (1 per region)
    """
    return max(1, regions_count)
