"""
List fetcher using Playwright browser automation.

Reliable method for fetching rental objects from 591.
"""

import asyncio
import random
from urllib.parse import urlencode

from loguru import logger
from playwright.async_api import Browser, Page, async_playwright

from src.crawler.types import ListRawData
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
        self._browser: Browser | None = None
        self._page: Page | None = None

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
        section: int | None = None,
        kind: int | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        other: list[str] | None = None,
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
            await self._page.wait_for_selector(
                "[data-v-][class*='item']", timeout=10000
            )
        except Exception:
            fetcher_log.debug("No item selector found, waiting 2s...")
            await asyncio.sleep(2)

    async def _extract_nuxt_data(self) -> dict | None:
        """Extract data from window.__NUXT__.data."""
        try:
            data = await self._page.evaluate("window.__NUXT__?.data")
            return data
        except Exception as e:
            fetcher_log.error(f"Failed to extract __NUXT__ data: {e}")
            return None

    def _find_items_and_total(self, data: dict) -> tuple[list[dict], int]:
        """Find items array and total count in the NUXT data structure."""
        if not isinstance(data, dict):
            return [], 0

        def search(d: dict) -> tuple[list[dict], int]:
            if isinstance(d, dict):
                for _key, value in d.items():
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

        return search(data)

    def _parse_item_raw(self, item: dict, region: int) -> ListRawData:
        """Parse a single item from NUXT structure into ListRawData."""
        result: ListRawData = {
            "region": region,
            "section": None,
            "id": "",
            "url": "",
            "title": "",
            "price_raw": "",
            "tags": [],
            "kind_name": "",
            "layout_raw": "",
            "area_raw": "",
            "floor_raw": "",
            "address_raw": "",
        }

        # Section - directly from NUXT sectionid
        section_id = item.get("sectionid")
        if section_id is not None:
            result["section"] = int(section_id)

        # ID - directly from NUXT data
        item_id = item.get("id")
        if item_id is not None:
            result["id"] = str(item_id)

        # URL
        result["url"] = item.get("url", "")

        # Title
        result["title"] = item.get("title", "")

        # Price
        price = item.get("price")
        if price is not None:
            result["price_raw"] = f"{price}元/月"

        # Tags
        tags = item.get("tags", [])
        if tags:
            if isinstance(tags[0], dict):
                result["tags"] = [tag.get("value") for tag in tags if tag.get("value")]
            else:
                result["tags"] = [str(t) for t in tags if t]

        # Kind name
        result["kind_name"] = item.get("kind_name", "") or item.get("kindName", "")

        # Layout
        result["layout_raw"] = item.get("layoutStr", "")

        # Area
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
        section: int | None = None,
        kind: int | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        other: list[str] | None = None,
        sort: str = "posttime_desc",
        max_pages: int | None = None,
        max_items: int | None = None,
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

            items, total = self._find_items_and_total(data)

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

    async def fetch_objects_raw(
        self,
        region: int,
        sort: str = "posttime_desc",
        max_items: int | None = None,
        first_row: int = 0,
    ) -> list[ListRawData]:
        """
        Fetch rental objects and return raw data (no transformation).

        Args:
            region: City code (1=Taipei, 3=New Taipei)
            sort: Sort order (default: posttime_desc)
            max_items: Maximum number of items to return
            first_row: Pagination offset (0=page 1, 30=page 2, etc.)

        Returns:
            List of ListRawData
        """
        if not self._browser:
            await self.start()

        url = self._build_url(region=region, sort=sort, first_row=first_row)
        fetcher_log.info(f"Playwright fetching raw: {url}")

        await self._page.goto(url, wait_until="domcontentloaded")
        await self._wait_for_content()

        nuxt_data = await self._extract_nuxt_data()
        if not nuxt_data:
            fetcher_log.warning("No NUXT data found")
            return []

        # Parse items
        items, total = self._find_items_and_total(nuxt_data)
        if not items:
            fetcher_log.warning("No items found in NUXT data")
            return []

        fetcher_log.debug(f"Found {len(items)} items (total: {total})")

        results: list[ListRawData] = []
        for item in items:
            try:
                raw_data = self._parse_item_raw(item, region)
                if raw_data.get("id"):
                    results.append(raw_data)
            except Exception as e:
                fetcher_log.warning(f"Failed to parse NUXT item: {e}")
                continue

        if max_items and len(results) > max_items:
            results = results[:max_items]

        fetcher_log.info(f"Playwright fetched {len(results)} objects (raw)")
        return results


# Singleton instance
_playwright_fetcher: ListFetcherPlaywright | None = None


def get_playwright_fetcher(headless: bool = True) -> ListFetcherPlaywright:
    """Get or create singleton Playwright list fetcher."""
    global _playwright_fetcher
    if _playwright_fetcher is None:
        _playwright_fetcher = ListFetcherPlaywright(headless=headless)
    return _playwright_fetcher


# Standalone functions for testing
def _find_items(data: dict) -> tuple[list[dict], int]:
    """Find items array and total count in the NUXT data structure (for testing)."""
    fetcher = ListFetcherPlaywright()
    return fetcher._find_items_and_total(data)


def _parse_item_raw_from_nuxt(item: dict, region: int) -> ListRawData:
    """Parse a single item from NUXT structure into ListRawData (for testing)."""
    fetcher = ListFetcherPlaywright()
    return fetcher._parse_item_raw(item, region)


def extract_list_raw_from_nuxt(nuxt_data: dict, region: int) -> list[ListRawData]:
    """Extract raw data from NUXT data structure (for testing)."""
    items, _ = _find_items(nuxt_data)
    results = []
    for item in items:
        raw_data = _parse_item_raw_from_nuxt(item, region)
        if raw_data.get("id"):
            results.append(raw_data)
    return results


def get_total_from_nuxt(nuxt_data: dict) -> int:
    """Get total count from NUXT data structure (for testing)."""
    _, total = _find_items(nuxt_data)
    return total
