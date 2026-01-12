"""
Unified list fetcher with automatic fallback.

Primary: BS4 (fast, lightweight)
Fallback: Playwright (stable, reliable)
"""

from typing import Optional

from loguru import logger

from src.crawler.list_fetcher_bs4 import ListFetcherBs4, get_bs4_fetcher
from src.crawler.list_fetcher_playwright import (
    ListFetcherPlaywright,
    get_playwright_fetcher,
)
from src.modules.objects.models import RentalObject

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

        self._bs4_fetcher: Optional[ListFetcherBs4] = None
        self._playwright_fetcher: Optional[ListFetcherPlaywright] = None
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

    async def fetch_objects(
        self,
        region: int = 1,
        section: Optional[int] = None,
        kind: Optional[int] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        other: Optional[list[str]] = None,
        sort: str = "posttime_desc",
        max_pages: Optional[int] = None,
        max_items: Optional[int] = None,
    ) -> list[RentalObject]:
        """
        Fetch rental objects with automatic fallback.

        1. Try BS4 (up to max_retries times)
        2. If all fail, fallback to Playwright

        Args:
            region: City code (1=Taipei, 3=New Taipei)
            section: District code
            kind: Property type (1=整層, 2=獨立套房, 3=分租套房, 4=雅房)
            price_min: Minimum price
            price_max: Maximum price
            other: Feature tags (e.g., ["pet", "near_subway"])
            sort: Sort order (posttime_desc=最新)
            max_pages: Maximum pages to fetch
            max_items: Maximum items to return

        Returns:
            List of RentalObject objects
        """
        if self._bs4_fetcher is None:
            await self.start()

        # Try BS4 first (up to max_retries)
        for attempt in range(self._max_retries):
            try:
                result = await self._bs4_fetcher.fetch_objects(
                    region=region,
                    section=section,
                    kind=kind,
                    price_min=price_min,
                    price_max=price_max,
                    other=other,
                    sort=sort,
                    max_pages=max_pages,
                    max_items=max_items,
                )
                if result:
                    fetcher_log.info(f"BS4 succeeded: {len(result)} objects")
                    return result
                fetcher_log.warning(
                    f"BS4 attempt {attempt + 1}/{self._max_retries} returned empty"
                )
            except Exception as e:
                fetcher_log.warning(
                    f"BS4 attempt {attempt + 1}/{self._max_retries} failed: {e}"
                )

        # Fallback to Playwright
        fetcher_log.warning("BS4 failed, falling back to Playwright...")
        await self._ensure_playwright()

        result = await self._playwright_fetcher.fetch_objects(
            region=region,
            section=section,
            kind=kind,
            price_min=price_min,
            price_max=price_max,
            other=other,
            sort=sort,
            max_pages=max_pages,
            max_items=max_items,
        )

        if not result:
            fetcher_log.error("Both BS4 and Playwright failed to fetch objects")

        return result


# Singleton instance
_list_fetcher: Optional[ListFetcher] = None


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
