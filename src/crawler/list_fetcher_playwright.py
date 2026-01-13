"""
List fetcher using Playwright browser automation.

Reliable method for fetching rental objects from 591.
"""

import asyncio
import random
from typing import Optional
from urllib.parse import urlencode

from loguru import logger
from playwright.async_api import async_playwright, Browser, Page

from src.modules.objects import RentalObject

fetcher_log = logger.bind(module="Playwright")


class ListFetcherPlaywright:
    """
    List fetcher using Playwright browser automation.

    Extracts data from window.__NUXT__ which requires JavaScript execution.
    """

    BASE_URL = "https://rent.591.com.tw/list"
    PAGE_SIZE = 30

    def __init__(self, headless: bool = True):
        """
        Initialize the Playwright list fetcher.

        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def start(self) -> None:
        """Start the browser."""
        if self._browser:
            return

        fetcher_log.info("Starting ListFetcherPlaywright...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._page = await self._browser.new_page()
        await self._page.set_viewport_size({"width": 1280, "height": 800})
        fetcher_log.info("ListFetcherPlaywright started")

    async def close(self) -> None:
        """Close the browser."""
        if self._page:
            await self._page.close()
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        fetcher_log.info("ListFetcherPlaywright closed")

    def _build_url(
        self,
        region: int,
        section: Optional[int] = None,
        kind: Optional[int] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        other: Optional[list[str]] = None,
        sort: str = "posttime_desc",
        first_row: int = 0,
    ) -> str:
        """Build the 591 list URL with query parameters."""
        params: dict[str, str | int] = {"region": region}

        if section:
            params["section"] = section
        if kind:
            params["kind"] = kind
        if price_min is not None or price_max is not None:
            price_str = f"{price_min or ''}" + "_" + f"{price_max or ''}"
            params["price"] = price_str
        if other:
            params["other"] = ",".join(other)
        params["sort"] = sort
        if first_row > 0:
            params["firstRow"] = first_row

        return f"{self.BASE_URL}?{urlencode(params)}"

    async def _wait_for_content(self) -> None:
        """Wait for page content to load."""
        try:
            await self._page.wait_for_selector("[data-v-][class*='item']", timeout=10000)
        except Exception:
            fetcher_log.debug("No item selector found, waiting 2s...")
            await asyncio.sleep(2)

    async def _extract_nuxt_data(self) -> Optional[dict]:
        """Extract data from window.__NUXT__.data."""
        try:
            data = await self._page.evaluate("window.__NUXT__?.data")
            return data
        except Exception as e:
            fetcher_log.error(f"Failed to extract __NUXT__ data: {e}")
            return None

    def _find_items(self, data: dict) -> list[dict]:
        """Find items array in the NUXT data structure."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    if "items" in value and isinstance(value["items"], list):
                        return value["items"]
                    result = self._find_items(value)
                    if result:
                        return result
        return []

    def _find_total(self, data: dict) -> int:
        """Find total count in the NUXT data structure."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    if "total" in value:
                        try:
                            return int(value["total"])
                        except (ValueError, TypeError):
                            pass
                    result = self._find_total(value)
                    if result > 0:
                        return result
        return 0

    def _parse_items(self, items: list[dict]) -> list[RentalObject]:
        """Parse raw items into RentalObject objects."""
        objects = []
        for item in items:
            try:
                obj = RentalObject.model_validate(item)
                objects.append(obj)
            except Exception as e:
                fetcher_log.warning(f"Failed to parse item {item.get('id', '?')}: {e}")
        return objects

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
        Fetch rental objects from 591.

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
        if not self._browser:
            await self.start()

        all_objects: list[RentalObject] = []
        first_row = 0
        page_num = 1

        while True:
            url = self._build_url(
                region=region,
                section=section,
                kind=kind,
                price_min=price_min,
                price_max=price_max,
                other=other,
                sort=sort,
                first_row=first_row,
            )

            fetcher_log.info(f"Fetching page {page_num}: {url}")
            await self._page.goto(url, wait_until="domcontentloaded")
            await self._wait_for_content()

            data = await self._extract_nuxt_data()
            if not data:
                fetcher_log.warning("No data found on page")
                break

            items = self._find_items(data)
            total = self._find_total(data)

            if not items:
                fetcher_log.info("No more items found")
                break

            objects = self._parse_items(items)
            all_objects.extend(objects)

            fetcher_log.info(
                f"Page {page_num}: Found {len(objects)} objects "
                f"(Total: {len(all_objects)}/{total})"
            )

            if max_items and len(all_objects) >= max_items:
                all_objects = all_objects[:max_items]
                fetcher_log.info(f"Reached max items limit: {max_items}")
                break

            if max_pages and page_num >= max_pages:
                fetcher_log.info(f"Reached max pages limit: {max_pages}")
                break

            if first_row + self.PAGE_SIZE >= total:
                fetcher_log.info("Reached last page")
                break

            first_row += self.PAGE_SIZE
            page_num += 1

            delay = random.uniform(2, 4)
            fetcher_log.debug(f"Waiting {delay:.1f}s before next page...")
            await asyncio.sleep(delay)

        fetcher_log.info(f"Playwright fetched {len(all_objects)} objects")
        return all_objects


# Singleton instance
_playwright_fetcher: Optional[ListFetcherPlaywright] = None


def get_playwright_fetcher(headless: bool = True) -> ListFetcherPlaywright:
    """
    Get or create singleton Playwright list fetcher.

    Args:
        headless: Run browser in headless mode

    Returns:
        ListFetcherPlaywright instance
    """
    global _playwright_fetcher
    if _playwright_fetcher is None:
        _playwright_fetcher = ListFetcherPlaywright(headless=headless)
    return _playwright_fetcher
