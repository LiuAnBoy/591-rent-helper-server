"""
Object Detail Crawler.

Fetches detail page data for rental objects with parallel processing support.
"""

import asyncio
from typing import Optional

from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.jobs.parser import parse_detail_fields


class ObjectDetailCrawler:
    """
    Crawler for fetching rental object detail pages.

    Supports parallel fetching using multiple browser pages.
    """

    def __init__(self, max_workers: int = 3, delay: float = 0.3):
        """
        Initialize the detail crawler.

        Args:
            max_workers: Maximum concurrent requests
            delay: Delay between requests per worker (rate limiting)
        """
        self.max_workers = max_workers
        self.delay = delay
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._pages: list[Page] = []
        self._page_locks: list[asyncio.Lock] = []
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def start(self) -> None:
        """Start browser and create worker pages."""
        if self._browser:
            return

        logger.info(f"Starting ObjectDetailCrawler with {self.max_workers} workers")

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        # Create worker pages
        self._pages = []
        self._page_locks = []
        for i in range(self.max_workers):
            page = await self._context.new_page()
            self._pages.append(page)
            self._page_locks.append(asyncio.Lock())
            logger.debug(f"Created worker page {i + 1}/{self.max_workers}")

        self._semaphore = asyncio.Semaphore(self.max_workers)

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._pages = []
        self._page_locks = []
        logger.info("ObjectDetailCrawler closed")

    async def _get_available_page(self) -> tuple[int, Page]:
        """Get an available page with its index."""
        for i, lock in enumerate(self._page_locks):
            if not lock.locked():
                return i, self._pages[i]
        # Fallback to first page (should not happen with semaphore)
        return 0, self._pages[0]

    async def _extract_nuxt_data(self, page: Page) -> Optional[dict]:
        """Extract data from window.__NUXT__.data."""
        try:
            data = await page.evaluate("window.__NUXT__?.data")
            return data
        except Exception as e:
            logger.error(f"Failed to extract __NUXT__ data: {e}")
            return None

    async def fetch_detail(
        self,
        object_id: int,
        page: Optional[Page] = None,
    ) -> Optional[dict]:
        """
        Fetch detail page data for a single rental object.

        Args:
            object_id: The rental object ID
            page: Optional page to use (for parallel fetching)

        Returns:
            Dict with parsed detail fields or None if failed:
                - gender: "boy" | "girl" | "all"
                - pet_allowed: True | False | None
                - shape: str | None
                - options: list[str] (equipment codes)
        """
        if not self._browser:
            await self.start()

        # Use provided page or first available
        if page is None:
            page = self._pages[0]

        url = f"https://rent.591.com.tw/{object_id}"

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(500)

            # Extract NUXT data
            nuxt_data = await self._extract_nuxt_data(page)
            if not nuxt_data:
                logger.warning(f"No NUXT data found for object {object_id}")
                return None

            # Find detail data in NUXT data
            detail_data = None
            for key, val in nuxt_data.items():
                if isinstance(val, dict) and "data" in val:
                    data = val["data"]
                    if isinstance(data, dict) and "service" in data:
                        detail_data = data
                        break

            if not detail_data:
                logger.warning(f"No detail data found for object {object_id}")
                return None

            # Parse fields
            result = parse_detail_fields(detail_data)

            logger.debug(
                f"Detail {object_id}: gender={result['gender']}, "
                f"pet={result['pet_allowed']}, options={len(result['options'])} items"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to fetch detail for {object_id}: {e}")
            return None

    async def _fetch_with_worker(
        self,
        object_id: int,
        worker_id: int,
        progress: dict,
    ) -> tuple[int, Optional[dict]]:
        """
        Fetch detail using a specific worker.

        Args:
            object_id: Object ID to fetch
            worker_id: Worker index
            progress: Shared progress dict for logging

        Returns:
            Tuple of (object_id, detail_data)
        """
        async with self._page_locks[worker_id]:
            # Rate limiting
            if self.delay > 0:
                await asyncio.sleep(self.delay)

            progress["completed"] += 1
            logger.info(
                f"[Worker {worker_id + 1}] Fetching detail "
                f"{progress['completed']}/{progress['total']}: {object_id}"
            )

            result = await self.fetch_detail(object_id, self._pages[worker_id])
            return object_id, result

    async def fetch_details_batch(
        self,
        object_ids: list[int],
    ) -> dict[int, dict]:
        """
        Fetch detail data for multiple objects in parallel.

        Args:
            object_ids: List of object IDs to fetch

        Returns:
            Dict mapping object_id to detail data
        """
        if not object_ids:
            return {}

        if not self._browser:
            await self.start()

        logger.info(
            f"Fetching {len(object_ids)} detail pages "
            f"with {self.max_workers} workers..."
        )

        results = {}
        progress = {"completed": 0, "total": len(object_ids)}

        # Create tasks with worker assignment
        async def fetch_with_semaphore(object_id: int) -> tuple[int, Optional[dict]]:
            async with self._semaphore:
                # Find available worker
                worker_id = None
                for i, lock in enumerate(self._page_locks):
                    if not lock.locked():
                        worker_id = i
                        break
                if worker_id is None:
                    worker_id = 0  # Fallback

                return await self._fetch_with_worker(object_id, worker_id, progress)

        # Execute all tasks concurrently (limited by semaphore)
        tasks = [fetch_with_semaphore(oid) for oid in object_ids]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in task_results:
            if isinstance(result, Exception):
                logger.error(f"Task failed: {result}")
                continue
            obj_id, detail = result
            if detail:
                results[obj_id] = detail

        logger.info(
            f"Fetched {len(results)}/{len(object_ids)} detail pages successfully"
        )

        return results


# Singleton instance
_detail_crawler: Optional[ObjectDetailCrawler] = None


async def get_detail_crawler(
    max_workers: int = 3,
    delay: float = 0.3,
) -> ObjectDetailCrawler:
    """
    Get or create the singleton detail crawler instance.

    Args:
        max_workers: Maximum concurrent requests
        delay: Delay between requests per worker

    Returns:
        ObjectDetailCrawler instance
    """
    global _detail_crawler
    if _detail_crawler is None:
        _detail_crawler = ObjectDetailCrawler(max_workers=max_workers, delay=delay)
    return _detail_crawler
