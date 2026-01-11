"""
591 Rent Crawler Module.

Handles fetching listings from 591 rental website using Playwright.
"""

import asyncio
import random
from typing import Optional
from urllib.parse import urlencode

from loguru import logger
from playwright.async_api import async_playwright, Page, Browser

from src.modules.objects import RentalObject

crawler_log = logger.bind(module="Crawler")


class Rent591Crawler:
    """591 rental website crawler using Playwright."""

    BASE_URL = "https://rent.591.com.tw/list"
    PAGE_SIZE = 30

    def __init__(self, headless: bool = True):
        """
        Initialize crawler.

        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright = None

    async def start(self) -> None:
        """Start the browser."""
        crawler_log.info("Starting Playwright browser...")
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
        )
        self.page = await self.browser.new_page()

        # Set viewport size
        await self.page.set_viewport_size({"width": 1280, "height": 800})

        crawler_log.info("Browser started successfully")

    async def close(self) -> None:
        """Close the browser."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        crawler_log.info("Browser closed")

    async def fetch_listings(
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
        Fetch rental listings from 591.

        Args:
            region: City code (1=Taipei, 3=New Taipei)
            section: District code
            kind: Property type (1=整層, 2=獨立套房, 3=分租套房, 4=雅房)
            price_min: Minimum price
            price_max: Maximum price
            other: Feature tags (e.g., ["pet", "near_subway"])
            sort: Sort order (posttime_desc=最新, money_desc=租金, area_desc=坪數)
            max_pages: Maximum pages to fetch (None = all pages)
            max_items: Maximum items to return (e.g., 10 for quick check)

        Returns:
            List of RentalObject objects
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        all_listings: list[RentalObject] = []
        first_row = 0
        page_num = 1

        while True:
            # Build URL
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

            crawler_log.info(f"Fetching page {page_num}: {url}")

            # Navigate to page (use domcontentloaded to avoid timeout from ads/tracking scripts)
            await self.page.goto(url, wait_until="domcontentloaded")

            # Wait for content to load
            await self._wait_for_content()

            # Extract data from __NUXT__
            data = await self._extract_nuxt_data()

            if not data:
                crawler_log.warning("No data found on page")
                break

            # Parse items
            items = self._find_items(data)
            total = self._find_total(data)

            if not items:
                crawler_log.info("No more items found")
                break

            # Convert to RentalObject objects
            listings = self._parse_items(items)
            all_listings.extend(listings)

            crawler_log.info(
                f"Page {page_num}: Found {len(listings)} objects "
                f"(Total so far: {len(all_listings)}/{total})"
            )

            # Check max_items limit
            if max_items and len(all_listings) >= max_items:
                all_listings = all_listings[:max_items]
                crawler_log.info(f"Reached max items limit: {max_items}")
                break

            # Check if we should continue
            if max_pages and page_num >= max_pages:
                crawler_log.info(f"Reached max pages limit: {max_pages}")
                break

            if first_row + self.PAGE_SIZE >= total:
                crawler_log.info("Reached last page")
                break

            # Move to next page
            first_row += self.PAGE_SIZE
            page_num += 1

            # Random delay to avoid rate limiting
            delay = random.uniform(2, 4)
            crawler_log.debug(f"Waiting {delay:.1f}s before next page...")
            await asyncio.sleep(delay)

        crawler_log.info(f"Crawling complete. Total objects: {len(all_listings)}")
        return all_listings

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
            price_str = f"{price_min or ''}"
            price_str += "_"
            price_str += f"{price_max or ''}"
            params["price"] = price_str

        if other:
            params["other"] = ",".join(other)

        # Always include sort parameter (default: posttime_desc for newest)
        params["sort"] = sort

        if first_row > 0:
            params["firstRow"] = first_row

        return f"{self.BASE_URL}?{urlencode(params)}"

    async def _wait_for_content(self) -> None:
        """Wait for page content to load."""
        try:
            # Wait for listing items to appear
            await self.page.wait_for_selector(
                "[data-v-][class*='item']",
                timeout=10000,
            )
        except Exception:
            # Fallback: wait a bit if no items found
            crawler_log.debug("No item selector found, waiting 2s...")
            await asyncio.sleep(2)

    async def _extract_nuxt_data(self) -> Optional[dict]:
        """Extract data from window.__NUXT__.data."""
        try:
            data = await self.page.evaluate("window.__NUXT__?.data")
            return data
        except Exception as e:
            crawler_log.error(f"Failed to extract __NUXT__ data: {e}")
            return None

    def _find_items(self, data: dict) -> list[dict]:
        """Find items array in the NUXT data structure."""
        # The data structure may vary, so we search for 'items' key
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    if "items" in value and isinstance(value["items"], list):
                        return value["items"]
                    # Recursively search
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
        listings = []
        for item in items:
            try:
                listing = RentalObject.model_validate(item)
                listings.append(listing)
            except Exception as e:
                crawler_log.warning(f"Failed to parse item {item.get('id', '?')}: {e}")
        return listings


async def main():
    """Test the crawler."""
    crawler = Rent591Crawler(headless=True)

    try:
        await crawler.start()

        # Fetch latest 10 listings from New Taipei City (region=3)
        listings = await crawler.fetch_listings(
            region=3,  # New Taipei City (新北市)
            max_items=10,  # Only get 10 items for quick check
        )

        print(f"\n{'='*60}")
        print(f"Found {len(listings)} listings (sorted by newest)")
        print(f"{'='*60}\n")

        for listing in listings:
            print(listing)
            print()

    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
