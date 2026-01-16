"""
Detail fetcher using Playwright browser automation.

Reliable fallback for fetching rental detail pages when bs4 fails.
"""

import asyncio

from loguru import logger
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.crawler.types import DetailFetchStatus, DetailRawData, calculate_detail_workers

fetcher_log = logger.bind(module="Playwright")


def _find_detail_data(nuxt_data: dict) -> dict | None:
    """
    Find detail data in NUXT data structure.

    NUXT data structure varies, need to search for "service" key.

    Args:
        nuxt_data: window.__NUXT__.data object

    Returns:
        Detail data dict or None if not found
    """
    if not isinstance(nuxt_data, dict):
        return None

    for _key, val in nuxt_data.items():
        if isinstance(val, dict) and "data" in val:
            data = val["data"]
            if isinstance(data, dict) and "service" in data:
                return data
    return None


def _extract_surrounding(traffic: dict | list, result: DetailRawData) -> DetailRawData:
    """
    Extract surrounding/traffic information.

    Args:
        traffic: Traffic data (can be dict or list)
        result: DetailRawData to update

    Returns:
        Updated DetailRawData
    """
    # Handle different traffic data structures
    if isinstance(traffic, dict):
        # Try metro first, then bus
        metro = traffic.get("metro") or traffic.get("subway")
        bus = traffic.get("bus")

        if metro and isinstance(metro, list) and len(metro) > 0:
            item = metro[0]
            result["surrounding_type"] = "metro"
            name = item.get("name", "")
            distance = item.get("distance", "")
            if name and distance:
                result["surrounding_raw"] = f"距{name}{distance}公尺"
        elif bus and isinstance(bus, list) and len(bus) > 0:
            item = bus[0]
            result["surrounding_type"] = "bus"
            name = item.get("name", "")
            distance = item.get("distance", "")
            if name and distance:
                result["surrounding_raw"] = f"距{name}{distance}公尺"

    elif isinstance(traffic, list) and len(traffic) > 0:
        # Simple list format
        item = traffic[0]
        if isinstance(item, dict):
            t_type = item.get("type", "")
            if "metro" in t_type.lower() or "subway" in t_type.lower():
                result["surrounding_type"] = "metro"
            elif "bus" in t_type.lower():
                result["surrounding_type"] = "bus"

            name = item.get("name", "")
            distance = item.get("distance", "")
            if name and distance:
                result["surrounding_raw"] = f"距{name}{distance}公尺"

    return result


def _parse_detail_raw_from_nuxt(data: dict, object_id: int) -> DetailRawData:
    """
    Parse detail data from NUXT structure into DetailRawData.

    Args:
        data: Detail data dict containing service, info, breadcrumb, etc.
        object_id: Object ID

    Returns:
        DetailRawData dictionary
    """
    result: DetailRawData = {
        "id": object_id,
        "title": "",
        "price_raw": "",
        "tags": [],
        "address_raw": "",
        "region": "",
        "section": "",
        "kind": "",
        "floor_raw": "",
        "layout_raw": "",
        "area_raw": "",
        "gender_raw": None,
        "shape_raw": None,
        "fitment_raw": None,
        "options": [],
        "surrounding_type": None,
        "surrounding_raw": None,
    }

    # Title
    result["title"] = data.get("title", "")

    # Price - format as "X元/月"
    price = data.get("price")
    if price is not None:
        result["price_raw"] = f"{price}元/月"

    # Tags - extract value from tag objects
    tags = data.get("tags", [])
    if tags:
        result["tags"] = [tag.get("value") for tag in tags if tag.get("value")]

    # Address
    result["address_raw"] = data.get("address", "")

    # Breadcrumb - extract region, section, kind
    breadcrumb = data.get("breadcrumb", [])
    for crumb in breadcrumb:
        query = crumb.get("query")
        crumb_id = crumb.get("id")
        if crumb_id is not None:
            if query == "region":
                result["region"] = str(crumb_id)
            elif query == "section":
                result["section"] = str(crumb_id)
            elif query == "kind":
                result["kind"] = str(crumb_id)

    # Info array - extract floor, layout, shape, fitment, area
    info = data.get("info", [])
    for item in info:
        key = item.get("key")
        value = item.get("value")
        if not value:
            continue

        if key == "floor":
            result["floor_raw"] = value
        elif key == "layout":
            result["layout_raw"] = value
        elif key == "shape":
            result["shape_raw"] = value
        elif key == "fitment":
            result["fitment_raw"] = value
        elif key == "area":
            # Area might be numeric or string
            if isinstance(value, (int, float)):
                result["area_raw"] = f"{value}坪"
            else:
                result["area_raw"] = value

    # Fallback for area from top-level
    if not result["area_raw"]:
        area = data.get("area")
        if area is not None:
            result["area_raw"] = f"{area}坪"

    # Fallback for floor from floor_name
    if not result["floor_raw"]:
        floor_name = data.get("floor_name") or data.get("floorName")
        if floor_name:
            result["floor_raw"] = floor_name

    # Fallback for layout from layoutStr
    if not result["layout_raw"]:
        layout_str = data.get("layoutStr") or data.get("layout_str")
        if layout_str:
            result["layout_raw"] = layout_str

    # Service - extract gender, options
    service = data.get("service", {})
    if service:
        # Gender from rule
        rule = service.get("rule", "")
        if rule:
            if "限男" in rule:
                result["gender_raw"] = "限男"
            elif "限女" in rule:
                result["gender_raw"] = "限女"

        # Options from facility
        facility = service.get("facility", [])
        if facility:
            # NUXT format: [{"key": "fridge", "active": 1, "name": "冰箱"}, ...]
            active_names = []
            for f in facility:
                if isinstance(f, dict) and f.get("active") == 1:
                    name = f.get("name")
                    if name:
                        active_names.append(name)
            result["options"] = active_names

    # Surrounding/Traffic info
    traffic = data.get("traffic") or data.get("surround")
    if traffic:
        result = _extract_surrounding(traffic, result)

    return result


def extract_detail_raw_from_nuxt(
    nuxt_data: dict,
    object_id: int,
) -> DetailRawData | None:
    """
    Extract raw data from NUXT data structure.

    Args:
        nuxt_data: window.__NUXT__.data object from Playwright
        object_id: Object ID

    Returns:
        DetailRawData dictionary or None if parsing failed
    """
    # Find detail data in NUXT structure
    detail_data = _find_detail_data(nuxt_data)
    if not detail_data:
        fetcher_log.warning(f"No detail data found in NUXT for object {object_id}")
        return None

    return _parse_detail_raw_from_nuxt(detail_data, object_id)


class DetailFetcherPlaywright:
    """
    Detail fetcher using Playwright browser automation.

    Supports parallel fetching using multiple browser pages.
    """

    def __init__(self, max_workers: int = 3, delay: float = 0.3):
        """
        Initialize the Playwright detail fetcher.

        Args:
            max_workers: Maximum concurrent requests
            delay: Delay between requests per worker (rate limiting)
        """
        self.max_workers = max_workers
        self.delay = delay
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._pages: list[Page] = []
        self._page_locks: list[asyncio.Lock] = []
        self._semaphore: asyncio.Semaphore | None = None

    async def start(self, worker_count: int | None = None) -> None:
        """Start browser and create worker pages.

        Args:
            worker_count: Override worker count (uses max_workers if None)
        """
        if self._browser:
            return

        # Use provided count or default
        actual_workers = worker_count if worker_count is not None else self.max_workers
        if actual_workers == 0:
            return

        fetcher_log.info(
            f"Starting DetailFetcherPlaywright with {actual_workers} workers"
        )

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
        for i in range(actual_workers):
            page = await self._context.new_page()
            self._pages.append(page)
            self._page_locks.append(asyncio.Lock())
            fetcher_log.debug(f"Created worker page {i + 1}/{actual_workers}")

        self._semaphore = asyncio.Semaphore(actual_workers)

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
        fetcher_log.info("DetailFetcherPlaywright closed")

    async def _ensure_workers(self, batch_size: int) -> int:
        """
        Ensure optimal worker count for the batch size.

        If browser not started, starts with optimal count.
        If current worker count differs from optimal, restarts browser.

        Args:
            batch_size: Number of items to process

        Returns:
            Actual worker count being used
        """
        optimal = calculate_detail_workers(batch_size)

        if optimal == 0:
            return 0

        current_workers = len(self._pages)

        # Not started yet - start with optimal count
        if not self._browser:
            await self.start(worker_count=optimal)
            return optimal

        # Already running with correct count
        if current_workers == optimal:
            return optimal

        # Need to resize - close and restart
        fetcher_log.info(
            f"Resizing workers: {current_workers} -> {optimal} (batch_size={batch_size})"
        )
        await self.close()
        await self.start(worker_count=optimal)
        return optimal

    async def _get_available_page(self) -> tuple[int, Page]:
        """Get an available page with its index."""
        for i, lock in enumerate(self._page_locks):
            if not lock.locked():
                return i, self._pages[i]
        # Fallback to first page (should not happen with semaphore)
        return 0, self._pages[0]

    async def _extract_nuxt_data(self, page: Page) -> dict | None:
        """Extract data from window.__NUXT__.data."""
        try:
            data = await page.evaluate("window.__NUXT__?.data")
            return data
        except Exception as e:
            fetcher_log.error(f"Failed to extract __NUXT__ data: {e}")
            return None

    async def fetch_detail_raw(
        self,
        object_id: int,
        page: Page | None = None,
    ) -> tuple[DetailRawData | None, DetailFetchStatus]:
        """
        Fetch detail page and return raw data (no transformation).

        Uses the NUXT extractor for consistent raw data extraction.

        Args:
            object_id: The rental object ID
            page: Optional page to use (for parallel fetching)

        Returns:
            Tuple of (DetailRawData or None, status)
        """
        if not self._browser:
            await self.start()

        # Use provided page or first available
        if page is None:
            page = self._pages[0]

        url = f"https://rent.591.com.tw/{object_id}"

        try:
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=15000
            )

            # Check response status
            if response:
                status = response.status
                if status == 404:
                    fetcher_log.debug(f"Object {object_id} not found (404)")
                    return None, "not_found"
                if status >= 400:
                    fetcher_log.warning(f"Object {object_id} returned HTTP {status}")
                    return None, "error"

            # Check if redirected (listing removed -> redirects to list page)
            current_url = page.url
            if f"/{object_id}" not in current_url:
                fetcher_log.debug(f"Object {object_id} redirected (removed)")
                return None, "not_found"

            # Wait for page to fully load before extracting data
            await page.wait_for_timeout(3000)

            # Extract NUXT data
            nuxt_data = await self._extract_nuxt_data(page)
            if not nuxt_data:
                fetcher_log.warning(f"No NUXT data found for object {object_id}")
                return None, "error"

            # Use NUXT extractor
            result = extract_detail_raw_from_nuxt(nuxt_data, object_id)

            if result:
                fetcher_log.debug(f"Parsed detail raw {object_id}")
                return result, "success"

            return None, "error"

        except Exception as e:
            error_msg = str(e)
            if "net::ERR_ABORTED" in error_msg:
                fetcher_log.debug(
                    f"Object {object_id} navigation aborted (likely removed)"
                )
                return None, "not_found"
            elif "Timeout" in error_msg:
                fetcher_log.warning(f"Object {object_id} timeout - network slow")
            else:
                fetcher_log.error(f"Object {object_id} fetch_detail_raw failed: {e}")
            return None, "error"

    async def _fetch_raw_with_worker(
        self,
        object_id: int,
        worker_id: int,
        progress: dict,
    ) -> tuple[int, DetailRawData | None, DetailFetchStatus]:
        """
        Fetch detail raw data using a specific worker.

        Args:
            object_id: Object ID to fetch
            worker_id: Worker index
            progress: Shared progress dict for logging

        Returns:
            Tuple of (object_id, DetailRawData, status)
        """
        async with self._page_locks[worker_id]:
            # Rate limiting
            if self.delay > 0:
                await asyncio.sleep(self.delay)

            progress["completed"] += 1
            fetcher_log.info(
                f"[Worker {worker_id + 1}] Fetching detail raw "
                f"{progress['completed']}/{progress['total']}: {object_id}"
            )

            data, status = await self.fetch_detail_raw(
                object_id, self._pages[worker_id]
            )
            return object_id, data, status

    async def fetch_details_batch_raw(
        self,
        object_ids: list[int],
    ) -> tuple[dict[int, DetailRawData], int, int]:
        """
        Fetch detail raw data for multiple objects in parallel.

        Dynamically adjusts worker count based on batch size.

        Args:
            object_ids: List of object IDs to fetch

        Returns:
            Tuple of (results dict, not_found count, error count)
        """
        if not object_ids:
            return {}, 0, 0

        # Dynamic worker scaling
        actual_workers = await self._ensure_workers(len(object_ids))
        if actual_workers == 0:
            return {}, 0, 0

        fetcher_log.info(
            f"Fetching {len(object_ids)} detail pages (raw) "
            f"with {actual_workers} workers..."
        )

        results: dict[int, DetailRawData] = {}
        not_found_count = 0
        error_count = 0
        progress = {"completed": 0, "total": len(object_ids)}

        # Create tasks with worker assignment
        async def fetch_with_semaphore(
            object_id: int,
        ) -> tuple[int, DetailRawData | None, DetailFetchStatus]:
            async with self._semaphore:
                # Find available worker
                worker_id = None
                for i, lock in enumerate(self._page_locks):
                    if not lock.locked():
                        worker_id = i
                        break
                if worker_id is None:
                    worker_id = 0  # Fallback

                return await self._fetch_raw_with_worker(object_id, worker_id, progress)

        # Execute all tasks concurrently (limited by semaphore)
        tasks = [fetch_with_semaphore(oid) for oid in object_ids]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in task_results:
            if isinstance(result, Exception):
                fetcher_log.error(f"Task failed: {result}")
                error_count += 1
                continue
            obj_id, detail, status = result
            if detail:
                results[obj_id] = detail
            elif status == "not_found":
                not_found_count += 1
            else:
                error_count += 1

        fetcher_log.info(f"Fetched {len(results)}/{len(object_ids)} detail pages (raw)")

        return results, not_found_count, error_count


# Singleton instance
_playwright_fetcher: DetailFetcherPlaywright | None = None


def get_playwright_fetcher(
    max_workers: int = 3,
    delay: float = 0.3,
) -> DetailFetcherPlaywright:
    """
    Get or create the singleton Playwright fetcher instance.

    Args:
        max_workers: Maximum concurrent requests
        delay: Delay between requests per worker

    Returns:
        DetailFetcherPlaywright instance
    """
    global _playwright_fetcher
    if _playwright_fetcher is None:
        _playwright_fetcher = DetailFetcherPlaywright(
            max_workers=max_workers, delay=delay
        )
    return _playwright_fetcher
