"""
Unified detail fetcher with automatic fallback.

Primary: bs4 (fast, lightweight)
Fallback: Playwright (stable, reliable)
"""

import asyncio

from loguru import logger

from src.crawler.detail_fetcher_bs4 import DetailFetcherBs4
from src.crawler.detail_fetcher_playwright import DetailFetcherPlaywright
from src.crawler.extractors import DetailRawData

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

    async def fetch_detail_raw(self, object_id: int) -> DetailRawData | None:
        """
        Fetch detail with automatic fallback, returning raw data.

        1. Try bs4 (up to max_retries)
        2. If all fail, fallback to Playwright

        Args:
            object_id: The rental object ID

        Returns:
            DetailRawData or None if all methods failed
        """
        if self._bs4_fetcher is None:
            await self.start()

        # Try bs4 first
        for attempt in range(self._max_retries):
            result = await self._bs4_fetcher.fetch_detail_raw(object_id)
            if result:
                # Check if we got meaningful data (tags should not be empty)
                if result.get("tags"):
                    return result
                fetcher_log.warning(
                    f"bs4 raw attempt {attempt + 1}/{self._max_retries} returned empty tags for {object_id}"
                )
            else:
                fetcher_log.warning(
                    f"bs4 raw attempt {attempt + 1}/{self._max_retries} failed for {object_id}"
                )

            # Wait 1 second before retry
            if attempt < self._max_retries - 1:
                await asyncio.sleep(1)

        # Fallback to Playwright
        fetcher_log.debug(f"BS4 raw failed, falling back to Playwright for {object_id}")
        await self._ensure_playwright()
        result = await self._playwright_fetcher.fetch_detail_raw(object_id)

        # Playwright fetcher already logs specific failure reason
        return result

    async def fetch_details_batch_raw(
        self,
        object_ids: list[int],
    ) -> dict[int, DetailRawData]:
        """
        Fetch multiple details with automatic fallback, returning raw data.

        1. Try bs4 for all objects
        2. For failed objects, fallback to Playwright

        Args:
            object_ids: List of object IDs to fetch

        Returns:
            Dict mapping object_id to DetailRawData
        """
        if not object_ids:
            return {}

        if self._bs4_fetcher is None:
            await self.start()

        fetcher_log.info(f"Fetching {len(object_ids)} detail pages (raw)...")

        # Use unified fetch_detail_raw for each object (has retry + fallback)
        tasks = [self.fetch_detail_raw(oid) for oid in object_ids]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        results: dict[int, DetailRawData] = {}
        error_count = 0
        skipped_count = 0
        for oid, result in zip(object_ids, results_list, strict=False):
            if isinstance(result, Exception):
                fetcher_log.error(f"Fetch raw exception for {oid}: {result}")
                error_count += 1
            elif result:
                results[oid] = result
            else:
                # None = object removed/unavailable (already logged by fetcher)
                skipped_count += 1

        fetcher_log.info(
            f"Fetched {len(results)}/{len(object_ids)} detail pages (raw) "
            f"({skipped_count} unavailable, {error_count} errors)"
        )

        return results


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
