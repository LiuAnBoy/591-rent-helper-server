"""
Unified detail fetcher with automatic fallback.

Primary: bs4 (fast, lightweight)
Fallback: Playwright (stable, reliable)
"""

import asyncio

from loguru import logger

from src.crawler.detail_fetcher_bs4 import DetailFetcherBs4
from src.crawler.detail_fetcher_playwright import DetailFetcherPlaywright
from src.crawler.types import DetailFetchStatus, DetailRawData

fetcher_log = logger.bind(module="DetailFetcher")


class DetailFetcher:
    """
    Unified detail fetcher with automatic fallback.

    Uses bs4 as primary method (fast, lightweight).
    Falls back to Playwright when bs4 fails (stable, reliable).
    """

    def __init__(
        self,
        max_retries: int = 3,
        bs4_max_workers: int = 5,
        playwright_max_workers: int = 3,
    ):
        """
        Initialize the detail fetcher.

        Args:
            max_retries: Max retries for bs4 before falling back to Playwright
            bs4_max_workers: Max concurrent requests for bs4 fetcher
            playwright_max_workers: Max concurrent requests for Playwright fetcher
        """
        self._max_retries = max_retries
        self._bs4_max_workers = bs4_max_workers
        self._playwright_max_workers = playwright_max_workers

        self._bs4_fetcher: DetailFetcherBs4 | None = None
        self._playwright_fetcher: DetailFetcherPlaywright | None = None
        self._playwright_started = False

    async def start(self) -> None:
        """Initialize bs4 fetcher (Playwright is lazy-loaded on demand)."""
        if self._bs4_fetcher is None:
            self._bs4_fetcher = DetailFetcherBs4(max_workers=self._bs4_max_workers)
            await self._bs4_fetcher.start()
            fetcher_log.info("DetailFetcher started (bs4 ready, Playwright on-demand)")

    async def close(self) -> None:
        """Close all fetchers."""
        if self._bs4_fetcher:
            await self._bs4_fetcher.close()
            self._bs4_fetcher = None

        if self._playwright_fetcher:
            await self._playwright_fetcher.close()
            self._playwright_fetcher = None
            self._playwright_started = False

        fetcher_log.info("DetailFetcher closed")

    async def _ensure_playwright(self) -> None:
        """Lazy-load Playwright fetcher when needed."""
        if not self._playwright_started:
            fetcher_log.info("Initializing Playwright fetcher (fallback)...")
            self._playwright_fetcher = DetailFetcherPlaywright(
                max_workers=self._playwright_max_workers
            )
            await self._playwright_fetcher.start()
            self._playwright_started = True

    async def fetch_detail_raw(
        self, object_id: int
    ) -> tuple[DetailRawData | None, DetailFetchStatus]:
        """
        Fetch detail with automatic fallback, returning raw data.

        1. Try bs4 (up to max_retries)
        2. If all fail, fallback to Playwright

        Args:
            object_id: The rental object ID

        Returns:
            Tuple of (DetailRawData or None, status)
        """
        if self._bs4_fetcher is None:
            await self.start()

        # Try bs4 first
        for attempt in range(self._max_retries):
            result, status = await self._bs4_fetcher.fetch_detail_raw(object_id)

            # If not_found, don't retry - object is removed
            if status == "not_found":
                return None, "not_found"

            if result:
                # Check if we got meaningful data (tags should not be empty)
                if result.get("tags"):
                    return result, "success"
                fetcher_log.warning(
                    f"bs4 raw attempt {attempt + 1}/{self._max_retries} returned empty tags for {object_id}"
                )
            else:
                fetcher_log.warning(
                    f"bs4 raw attempt {attempt + 1}/{self._max_retries} failed for {object_id}"
                )

            # Wait 1.5 seconds before retry
            if attempt < self._max_retries - 1:
                await asyncio.sleep(1.5)

        # Fallback to Playwright
        fetcher_log.debug(f"BS4 raw failed, falling back to Playwright for {object_id}")
        await self._ensure_playwright()
        return await self._playwright_fetcher.fetch_detail_raw(object_id)

    async def fetch_details_batch_raw(
        self,
        object_ids: list[int],
    ) -> tuple[dict[int, DetailRawData], int, int]:
        """
        Fetch multiple details with automatic fallback, returning raw data.

        Dynamically adjusts worker count based on batch size.

        1. Try bs4 for all objects
        2. For failed objects, fallback to Playwright

        Args:
            object_ids: List of object IDs to fetch

        Returns:
            Tuple of (results dict, not_found count, error count)
        """
        if not object_ids:
            return {}, 0, 0

        if self._bs4_fetcher is None:
            await self.start()

        # Dynamic worker scaling for BS4
        await self._bs4_fetcher._ensure_workers(len(object_ids))

        fetcher_log.info(f"Fetching {len(object_ids)} detail pages (raw)...")

        # Use unified fetch_detail_raw for each object (has retry + fallback)
        tasks = [self.fetch_detail_raw(oid) for oid in object_ids]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        results: dict[int, DetailRawData] = {}
        not_found_count = 0
        error_count = 0
        for oid, result in zip(object_ids, results_list, strict=False):
            if isinstance(result, Exception):
                fetcher_log.error(f"Fetch raw exception for {oid}: {result}")
                error_count += 1
            elif isinstance(result, tuple):
                data, status = result
                if data:
                    results[oid] = data
                elif status == "not_found":
                    not_found_count += 1
                else:
                    error_count += 1

        fetcher_log.info(
            f"Fetched {len(results)}/{len(object_ids)} detail pages (raw) "
            f"({not_found_count} not found, {error_count} errors)"
        )

        return results, not_found_count, error_count


# Singleton instance
_detail_fetcher: DetailFetcher | None = None


def get_detail_fetcher(
    max_retries: int = 3,
    bs4_max_workers: int = 5,
    playwright_max_workers: int = 3,
) -> DetailFetcher:
    """
    Get or create the singleton detail fetcher instance.

    Args:
        max_retries: Max retries for bs4 before falling back
        bs4_max_workers: Max concurrent requests for bs4
        playwright_max_workers: Max concurrent requests for Playwright

    Returns:
        DetailFetcher instance
    """
    global _detail_fetcher
    if _detail_fetcher is None:
        _detail_fetcher = DetailFetcher(
            max_retries=max_retries,
            bs4_max_workers=bs4_max_workers,
            playwright_max_workers=playwright_max_workers,
        )
    return _detail_fetcher
