"""
Detail fetcher using requests + BeautifulSoup.

Lightweight alternative to Playwright for fetching rental detail pages.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from src.utils.mappings import (
    SHAPE_NAME_TO_CODE,
    convert_options_to_codes,
)

fetcher_log = logger.bind(module="BS4")


class DetailFetcherBs4:
    """
    Lightweight detail fetcher using requests + BeautifulSoup.

    Parses rental detail pages without browser automation.
    """

    # HTTP headers to mimic browser request
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }

    # Facility names to search for in page text
    FACILITY_NAMES = [
        "冷氣",
        "洗衣機",
        "冰箱",
        "電視",
        "熱水器",
        "床",
        "衣櫃",
        "沙發",
        "第四台",
        "網路",
        "天然瓦斯",
        "電梯",
        "車位",
        "陽台",
        "桌椅",
    ]

    def __init__(
        self,
        timeout: float = 10.0,
        max_workers: int = 5,
    ):
        """
        Initialize the bs4 detail fetcher.

        Args:
            timeout: Request timeout in seconds
            max_workers: Max concurrent requests for batch fetching
        """
        self._timeout = timeout
        self._max_workers = max_workers
        self._session: Optional[requests.Session] = None
        self._executor: Optional[ThreadPoolExecutor] = None

    async def start(self) -> None:
        """Initialize session (for interface compatibility)."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(self.DEFAULT_HEADERS)
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
            fetcher_log.info("DetailFetcherBs4 started")

    async def close(self) -> None:
        """Close session and executor."""
        if self._session:
            self._session.close()
            self._session = None
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        fetcher_log.info("DetailFetcherBs4 closed")

    def _fetch_html(self, object_id: int) -> Optional[str]:
        """
        Fetch HTML content for a detail page.

        Args:
            object_id: The rental object ID

        Returns:
            HTML content or None if failed
        """
        url = f"https://rent.591.com.tw/{object_id}"

        try:
            # Note: verify=False due to 591's SSL certificate issues
            resp = self._session.get(url, timeout=self._timeout, verify=False)
            if resp.status_code == 200:
                return resp.text
            fetcher_log.warning(f"HTTP {resp.status_code} for {object_id}")
            return None
        except requests.RequestException as e:
            fetcher_log.error(f"Request failed for {object_id}: {e}")
            return None

    def _parse_gender(self, page_text: str) -> str:
        """
        Parse gender restriction from page text.

        Args:
            page_text: Full text content of the page

        Returns:
            "boy" | "girl" | "all"
        """
        if "限男" in page_text:
            return "boy"
        elif "限女" in page_text:
            return "girl"
        return "all"

    def _parse_pet(self, page_text: str) -> Optional[bool]:
        """
        Parse pet policy from page text.

        Args:
            page_text: Full text content of the page

        Returns:
            True (allowed) | False (not allowed) | None (unknown)
        """
        if "可養寵物" in page_text or "可養寵" in page_text:
            return True
        elif "不可養寵" in page_text or "禁養寵" in page_text:
            return False
        return None

    def _parse_shape(self, page_text: str) -> Optional[int]:
        """
        Parse building shape/type from page text.

        Args:
            page_text: Full text content of the page

        Returns:
            Shape code (1-4) or None
        """
        for name, code in SHAPE_NAME_TO_CODE.items():
            if name in page_text:
                return code
        return None

    def _parse_options(self, page_text: str) -> list[str]:
        """
        Parse facility/equipment options from page text.

        Args:
            page_text: Full text content of the page

        Returns:
            List of option codes
        """
        found_facilities = []
        for facility in self.FACILITY_NAMES:
            if facility in page_text:
                found_facilities.append(facility)
        return convert_options_to_codes(found_facilities)

    def _parse_detail_sync(self, object_id: int) -> Optional[dict]:
        """
        Synchronously fetch and parse a detail page.

        Args:
            object_id: The rental object ID

        Returns:
            Dict with parsed fields or None if failed
        """
        html = self._fetch_html(object_id)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            page_text = soup.get_text()

            result = {
                "gender": self._parse_gender(page_text),
                "pet_allowed": self._parse_pet(page_text),
                "shape": self._parse_shape(page_text),
                "options": self._parse_options(page_text),
            }

            fetcher_log.debug(
                f"Parsed {object_id}: gender={result['gender']}, "
                f"pet={result['pet_allowed']}, shape={result['shape']}, "
                f"options={len(result['options'])} items"
            )

            return result

        except Exception as e:
            fetcher_log.error(f"Parse error for {object_id}: {e}")
            return None

    async def fetch_detail(self, object_id: int) -> Optional[dict]:
        """
        Fetch detail page data for a single rental object.

        Args:
            object_id: The rental object ID

        Returns:
            Dict with parsed detail fields or None if failed:
                - gender: "boy" | "girl" | "all"
                - pet_allowed: True | False | None
                - shape: int | None (1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅)
                - options: list[str] (equipment codes)
        """
        if self._session is None:
            await self.start()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._parse_detail_sync,
            object_id,
        )

    async def fetch_details_batch(
        self,
        object_ids: list[int],
    ) -> dict[int, dict]:
        """
        Fetch detail data for multiple objects concurrently.

        Args:
            object_ids: List of object IDs to fetch

        Returns:
            Dict mapping object_id to detail data
        """
        if not object_ids:
            return {}

        if self._session is None:
            await self.start()

        fetcher_log.info(f"Fetching {len(object_ids)} detail pages with bs4...")

        # Create tasks for all objects
        tasks = [self.fetch_detail(oid) for oid in object_ids]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        results = {}
        success_count = 0

        for oid, result in zip(object_ids, results_list):
            if isinstance(result, Exception):
                fetcher_log.error(f"Task failed for {oid}: {result}")
                continue
            if result:
                results[oid] = result
                success_count += 1

        fetcher_log.info(
            f"bs4 fetched {success_count}/{len(object_ids)} detail pages"
        )

        return results


# Singleton instance
_bs4_fetcher: Optional[DetailFetcherBs4] = None


def get_bs4_fetcher(
    timeout: float = 10.0,
    max_workers: int = 5,
) -> DetailFetcherBs4:
    """
    Get or create singleton bs4 fetcher instance.

    Args:
        timeout: Request timeout in seconds
        max_workers: Max concurrent requests

    Returns:
        DetailFetcherBs4 instance
    """
    global _bs4_fetcher
    if _bs4_fetcher is None:
        _bs4_fetcher = DetailFetcherBs4(
            timeout=timeout,
            max_workers=max_workers,
        )
    return _bs4_fetcher
