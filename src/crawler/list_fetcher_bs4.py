"""
List fetcher using requests + BeautifulSoup.

Lightweight alternative to Playwright for fetching rental objects.
Note: 591 list pages use NUXT which requires JavaScript execution,
so this fetcher may fail and fallback to Playwright is expected.
"""

from urllib.parse import urlencode

import requests
import urllib3
from loguru import logger

# Suppress SSL warnings for 591's certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.crawler.extractors import ListRawData, extract_list_raw  # noqa: E402

fetcher_log = logger.bind(module="BS4")


class ListFetcherBs4:
    """
    Lightweight list fetcher using requests + BeautifulSoup.

    Attempts to parse rental objects from HTML.
    May fail on 591 as it requires JavaScript for NUXT data.
    """

    BASE_URL = "https://rent.591.com.tw/list"

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }

    def __init__(self, timeout: float = 15.0):
        """
        Initialize the BS4 list fetcher.

        Args:
            timeout: Request timeout in seconds
        """
        self._timeout = timeout
        self._session: requests.Session | None = None

    async def start(self) -> None:
        """Initialize session (for interface compatibility)."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(self.DEFAULT_HEADERS)
            fetcher_log.info("ListFetcherBs4 started")

    async def close(self) -> None:
        """Close session."""
        if self._session:
            self._session.close()
            self._session = None
        fetcher_log.info("ListFetcherBs4 closed")

    def _build_url(
        self,
        region: int,
        section: int | None = None,
        kind: int | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        other: list[str] | None = None,
        sort: str = "posttime_desc",
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

        return f"{self.BASE_URL}?{urlencode(params)}"

    async def fetch_objects_raw(
        self,
        region: int,
        sort: str = "posttime_desc",
        max_items: int | None = None,
    ) -> list[ListRawData]:
        """
        Fetch rental objects from list page, returning raw data.

        Uses the new ETL extractor for consistent raw data extraction.

        Args:
            region: City code (1=Taipei, 3=New Taipei)
            sort: Sort order (default: posttime_desc)
            max_items: Maximum number of items to return

        Returns:
            List of ListRawData or empty list if failed
        """
        if self._session is None:
            await self.start()

        # Use the ETL extractor
        items = extract_list_raw(region=region, page=1, session=self._session)

        # Apply max_items limit
        if max_items and len(items) > max_items:
            items = items[:max_items]

        return items


# Singleton instance
_bs4_fetcher: ListFetcherBs4 | None = None


def get_bs4_fetcher(timeout: float = 15.0) -> ListFetcherBs4:
    """
    Get or create singleton BS4 list fetcher.

    Args:
        timeout: Request timeout in seconds

    Returns:
        ListFetcherBs4 instance
    """
    global _bs4_fetcher
    if _bs4_fetcher is None:
        _bs4_fetcher = ListFetcherBs4(timeout=timeout)
    return _bs4_fetcher
