"""
Unified detail fetcher with automatic fallback.

Primary: bs4 (fast, lightweight)
Fallback: Playwright (stable, reliable)
"""

from typing import Optional

from loguru import logger

from src.crawler.detail_fetcher_bs4 import DetailFetcherBs4
from src.crawler.detail_fetcher_playwright import DetailFetcherPlaywright

fetcher_log = logger.bind(module="DetailFetcher")


class DetailFetcher:
    """
    Unified detail fetcher with automatic fallback.

    Uses bs4 as primary method (fast, lightweight).
    Falls back to Playwright when bs4 fails (stable, reliable).

    Both fetchers return the same field format:
        - gender: "boy" | "girl" | "all"
        - pet_allowed: True | False | None
        - shape: int | None (1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅)
        - options: list[str] (equipment codes)
        - fitment: int | None (99=新裝潢, 3=中檔, 4=高檔)
        - section: int | None (行政區代碼)
        - kind: int | None (類型代碼)
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

        self._bs4_fetcher: Optional[DetailFetcherBs4] = None
        self._playwright_fetcher: Optional[DetailFetcherPlaywright] = None
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

    async def fetch_detail(self, object_id: int) -> Optional[dict]:
        """
        Fetch detail with automatic fallback.

        1. Try bs4 (up to max_retries)
        2. If all fail, fallback to Playwright

        Args:
            object_id: The rental object ID

        Returns:
            Dict with parsed detail fields or None if all methods failed
        """
        if self._bs4_fetcher is None:
            await self.start()

        # Try bs4 first
        for attempt in range(self._max_retries):
            result = await self._bs4_fetcher.fetch_detail(object_id)
            if result:
                # Check if we got meaningful data (tags should not be empty)
                if result.get("tags"):
                    return result
                fetcher_log.warning(
                    f"bs4 attempt {attempt + 1}/{self._max_retries} returned empty tags for {object_id}"
                )
            else:
                fetcher_log.warning(
                    f"bs4 attempt {attempt + 1}/{self._max_retries} failed for {object_id}"
                )

        # Fallback to Playwright
        fetcher_log.warning(f"BS4 failed, falling back to Playwright for {object_id}")
        await self._ensure_playwright()
        result = await self._playwright_fetcher.fetch_detail(object_id)

        if result is None:
            fetcher_log.error(f"All fetchers failed for {object_id}")

        return result

    async def fetch_details_batch(
        self,
        object_ids: list[int],
    ) -> dict[int, dict]:
        """
        Fetch multiple details with automatic fallback.

        1. Try bs4 for all objects
        2. For failed objects, fallback to Playwright

        Args:
            object_ids: List of object IDs to fetch

        Returns:
            Dict mapping object_id to detail data
        """
        if not object_ids:
            return {}

        if self._bs4_fetcher is None:
            await self.start()

        fetcher_log.info(f"Fetching {len(object_ids)} detail pages...")

        # Try bs4 for all objects
        results = await self._bs4_fetcher.fetch_details_batch(object_ids)

        # Collect failed IDs
        failed_ids = [oid for oid in object_ids if oid not in results]

        if failed_ids:
            fetcher_log.warning(
                f"BS4 failed for {len(failed_ids)} objects, "
                f"falling back to Playwright..."
            )
            await self._ensure_playwright()
            playwright_results = await self._playwright_fetcher.fetch_details_batch(
                failed_ids
            )
            results.update(playwright_results)

            # Check for objects that failed both fetchers
            still_failed = [oid for oid in failed_ids if oid not in playwright_results]
            if still_failed:
                fetcher_log.error(
                    f"All fetchers failed for {len(still_failed)} objects: {still_failed}"
                )

        fetcher_log.info(
            f"Fetched {len(results)}/{len(object_ids)} detail pages successfully"
        )

        return results


# Singleton instance
_detail_fetcher: Optional[DetailFetcher] = None


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
