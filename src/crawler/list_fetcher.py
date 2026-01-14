"""
Unified list fetcher with automatic fallback.

Primary: BS4 (fast, lightweight)
Fallback: Playwright (stable, reliable)
"""

import asyncio

from loguru import logger

from src.crawler.list_fetcher_bs4 import ListFetcherBs4, get_bs4_fetcher
from src.crawler.list_fetcher_playwright import (
    ListFetcherPlaywright,
    get_playwright_fetcher,
)
from src.crawler.types import ListRawData, calculate_list_workers

fetcher_log = logger.bind(module="ListFetcher")


class ListFetcher:
    """
    Unified list fetcher with automatic fallback.

    Uses BS4 as primary method (fast, lightweight).
    Falls back to Playwright when BS4 fails 3 times (stable, reliable).
    """

    def __init__(
        self,
        max_retries: int = 3,
        headless: bool = True,
        bs4_timeout: float = 15.0,
    ):
        """
        Initialize the list fetcher.

        Args:
            max_retries: Max retries for BS4 before falling back to Playwright
            headless: Run Playwright browser in headless mode
            bs4_timeout: Timeout for BS4 requests
        """
        self._max_retries = max_retries
        self._headless = headless
        self._bs4_timeout = bs4_timeout

        self._bs4_fetcher: ListFetcherBs4 | None = None
        self._playwright_fetcher: ListFetcherPlaywright | None = None
        self._playwright_started = False

    async def start(self) -> None:
        """Initialize BS4 fetcher (Playwright is lazy-loaded on demand)."""
        if self._bs4_fetcher is None:
            self._bs4_fetcher = get_bs4_fetcher(timeout=self._bs4_timeout)
            await self._bs4_fetcher.start()
            fetcher_log.info("ListFetcher started (BS4 ready, Playwright on-demand)")

    async def close(self) -> None:
        """Close all fetchers."""
        if self._bs4_fetcher:
            await self._bs4_fetcher.close()
            self._bs4_fetcher = None

        if self._playwright_fetcher:
            await self._playwright_fetcher.close()
            self._playwright_fetcher = None
            self._playwright_started = False

        fetcher_log.info("ListFetcher closed")

    async def _ensure_playwright(self) -> None:
        """Lazy-load Playwright fetcher when needed."""
        if not self._playwright_started:
            fetcher_log.info("Initializing Playwright fetcher (fallback)...")
            self._playwright_fetcher = get_playwright_fetcher(headless=self._headless)
            await self._playwright_fetcher.start()
            self._playwright_started = True

    async def fetch_objects_raw(
        self,
        region: int,
        sort: str = "posttime_desc",
        max_items: int | None = None,
    ) -> list[ListRawData]:
        """
        Fetch rental objects from list page, returning raw data.

        Uses BS4 as primary method.
        Falls back to Playwright when BS4 fails 3 times.

        Args:
            region: City code (1=Taipei, 3=New Taipei)
            sort: Sort order (default: posttime_desc)
            max_items: Maximum number of items to return

        Returns:
            List of ListRawData or empty list if failed
        """
        if self._bs4_fetcher is None:
            await self.start()

        # Try bs4 up to max_retries times
        for attempt in range(self._max_retries):
            items = await self._bs4_fetcher.fetch_objects_raw(
                region=region,
                sort=sort,
                max_items=max_items,
            )
            if items:
                fetcher_log.info(
                    f"BS4 raw fetched {len(items)} objects (attempt {attempt + 1})"
                )
                return items

            fetcher_log.warning(
                f"BS4 raw attempt {attempt + 1}/{self._max_retries} returned no items"
            )

            # Wait 1.5 seconds before retry
            if attempt < self._max_retries - 1:
                await asyncio.sleep(1.5)

        # Fallback to Playwright
        fetcher_log.warning(
            "BS4 raw failed all attempts, falling back to Playwright..."
        )
        await self._ensure_playwright()

        result = await self._playwright_fetcher.fetch_objects_raw(
            region=region,
            sort=sort,
            max_items=max_items,
        )

        if not result:
            fetcher_log.error("Both BS4 and Playwright failed to fetch raw objects")

        return result

    async def fetch_objects_raw_multi(
        self,
        regions: list[int],
        sort: str = "posttime_desc",
        max_items: int | None = None,
    ) -> dict[int, list[ListRawData]]:
        """
        Fetch rental objects from multiple regions in parallel.

        Dynamically uses worker count based on number of regions.

        Args:
            regions: List of region codes (1=Taipei, 3=New Taipei)
            sort: Sort order (default: posttime_desc)
            max_items: Maximum number of items per region

        Returns:
            Dict mapping region to list of ListRawData
        """
        if not regions:
            return {}

        if self._bs4_fetcher is None:
            await self.start()

        worker_count = calculate_list_workers(len(regions))
        fetcher_log.info(
            f"Fetching {len(regions)} regions with {worker_count} workers..."
        )

        async def fetch_region(region: int) -> tuple[int, list[ListRawData]]:
            items = await self.fetch_objects_raw(
                region=region,
                sort=sort,
                max_items=max_items,
            )
            return region, items

        # Fetch all regions in parallel
        tasks = [fetch_region(r) for r in regions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        output: dict[int, list[ListRawData]] = {}
        for result in results:
            if isinstance(result, Exception):
                fetcher_log.error(f"Region fetch failed: {result}")
                continue
            region, items = result
            output[region] = items

        total_items = sum(len(items) for items in output.values())
        fetcher_log.info(
            f"Fetched {total_items} total objects from {len(output)} regions"
        )

        return output


# Singleton instance
_list_fetcher: ListFetcher | None = None


def get_list_fetcher(
    max_retries: int = 3,
    headless: bool = True,
    bs4_timeout: float = 15.0,
) -> ListFetcher:
    """
    Get or create the singleton list fetcher instance.

    Args:
        max_retries: Max retries for BS4 before falling back
        headless: Run Playwright browser in headless mode
        bs4_timeout: Timeout for BS4 requests

    Returns:
        ListFetcher instance
    """
    global _list_fetcher
    if _list_fetcher is None:
        _list_fetcher = ListFetcher(
            max_retries=max_retries,
            headless=headless,
            bs4_timeout=bs4_timeout,
        )
    return _list_fetcher
