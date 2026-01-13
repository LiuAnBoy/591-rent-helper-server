"""
Detail fetcher using requests + BeautifulSoup.

Lightweight alternative to Playwright for fetching rental detail pages.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3
from loguru import logger

# Suppress SSL warnings for 591's certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.crawler.extractors import DetailRawData, extract_detail_raw  # noqa: E402

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
        self._session: requests.Session | None = None
        self._executor: ThreadPoolExecutor | None = None

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

    def _fetch_html(self, object_id: int) -> str | None:
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

    async def fetch_detail_raw(self, object_id: int) -> DetailRawData | None:
        """
        Fetch detail page and return raw data (no transformation).

        Uses the new ETL extractor for consistent raw data extraction.

        Args:
            object_id: The rental object ID

        Returns:
            DetailRawData or None if failed
        """
        if self._session is None:
            await self.start()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: extract_detail_raw(object_id, session=self._session),
        )


# Singleton instance
_bs4_fetcher: DetailFetcherBs4 | None = None


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
