"""
List fetcher using requests + BeautifulSoup.

Lightweight alternative to Playwright for fetching rental objects.
"""

import re
from urllib.parse import urlencode

import requests
import urllib3
from bs4 import BeautifulSoup
from loguru import logger

from src.crawler.types import ListRawData
from src.utils.sections import get_section_from_address

# Suppress SSL warnings for 591's certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

fetcher_log = logger.bind(module="BS4")

# Kind name constants for matching
KIND_NAMES = ["整層住家", "獨立套房", "分租套房", "雅房", "車位", "其他"]


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

    async def fetch_objects_raw(
        self,
        region: int,
        sort: str = "posttime_desc",
        max_items: int | None = None,
        first_row: int = 0,
    ) -> list[ListRawData]:
        """
        Fetch rental objects from list page, returning raw data.

        Args:
            region: City code (1=Taipei, 3=New Taipei)
            sort: Sort order (default: posttime_desc)
            max_items: Maximum number of items to return
            first_row: Pagination offset (0=page 1, 30=page 2, etc.)

        Returns:
            List of ListRawData or empty list if failed
        """
        if self._session is None:
            await self.start()

        # Build URL with pagination support
        url = self._build_url(region=region, sort=sort, first_row=first_row)
        fetcher_log.debug(f"Fetching list page: {url}")

        resp = self._session.get(url, timeout=self._timeout, verify=False)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.find_all("div", class_="item")

        fetcher_log.debug(f"Found {len(items)} items")

        results: list[ListRawData] = []
        for elem in items:
            try:
                raw_data = self._parse_item_raw(elem, region)
                if raw_data.get("id"):
                    results.append(raw_data)
            except Exception as e:
                fetcher_log.warning(f"Failed to parse item: {e}")
                continue

        # Apply max_items limit
        if max_items and len(results) > max_items:
            results = results[:max_items]

        return results

    def _parse_item_raw(self, elem: BeautifulSoup, region: int) -> ListRawData:
        """
        Parse a single item element and return raw data.

        Args:
            elem: BeautifulSoup element for the item
            region: Region code

        Returns:
            ListRawData dictionary
        """
        result: ListRawData = {
            "region": region,
            "section": "",
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

        # ID - directly from data-id attribute
        data_id = elem.get("data-id")
        if data_id:
            result["id"] = str(data_id)

        # URL from link
        link = elem.find("a", href=re.compile(r"rent\.591\.com\.tw/(\d+)"))
        if link:
            result["url"] = link.get("href", "")

        # Title
        title_elem = elem.select_one(".item-info-title a")
        if title_elem:
            result["title"] = title_elem.get_text(strip=True)

        # Price (raw, including unit)
        price_elem = elem.select_one(".item-info-price")
        if price_elem:
            result["price_raw"] = price_elem.get_text(strip=True)

        # Tags from multiple possible selectors
        tags: list[str] = []
        tag_elems = elem.select(".item-tags span, .item-info-tag span")
        for tag in tag_elems:
            tag_text = tag.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)
        result["tags"] = tags

        # Info row parsing (kind_name, area_raw, floor_raw, address_raw)
        txt_elems = elem.select(".item-info-txt")
        for txt_elem in txt_elems:
            has_home = txt_elem.select_one(".house-home")
            has_place = txt_elem.select_one(".house-place")

            if has_home:
                spans = txt_elem.find_all("span")
                for span in spans:
                    text = span.get_text(strip=True)
                    if not text:
                        continue

                    if text in KIND_NAMES:
                        result["kind_name"] = text
                    elif re.match(r"\d房", text):
                        # Layout: "2房1廳", "3房2廳" etc.
                        result["layout_raw"] = text
                    elif "坪" in text:
                        result["area_raw"] = text
                    elif "F" in text or "層" in text:
                        result["floor_raw"] = text

            elif has_place:
                # Address: may have community name before actual address
                # e.g., ['仁愛新城', '中正區-仁愛路一段'] -> take the one with "區-"
                spans = txt_elem.find_all("span")
                for span in reversed(spans):
                    text = span.get_text(strip=True)
                    if text and ("區-" in text or "區－" in text):
                        result["address_raw"] = text
                        break
                else:
                    # Fallback: use full text if no "區-" found
                    result["address_raw"] = txt_elem.get_text(strip=True)

        # Parse section from address_raw
        if result["address_raw"]:
            section = get_section_from_address(region, result["address_raw"])
            if section:
                result["section"] = str(section)

        return result


# Singleton instance
_bs4_fetcher: ListFetcherBs4 | None = None


def get_bs4_fetcher(timeout: float = 15.0) -> ListFetcherBs4:
    """Get or create singleton BS4 list fetcher."""
    global _bs4_fetcher
    if _bs4_fetcher is None:
        _bs4_fetcher = ListFetcherBs4(timeout=timeout)
    return _bs4_fetcher


# Standalone function for testing
def _parse_item_raw(elem: BeautifulSoup, region: int) -> ListRawData:
    """
    Parse a single item element and return raw data (standalone function for testing).

    Args:
        elem: BeautifulSoup element for the item
        region: Region code

    Returns:
        ListRawData dictionary
    """
    fetcher = ListFetcherBs4()
    return fetcher._parse_item_raw(elem, region)
