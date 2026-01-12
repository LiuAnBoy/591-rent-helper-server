"""
List fetcher using requests + BeautifulSoup.

Lightweight alternative to Playwright for fetching rental listings.
Note: 591 list pages use NUXT which requires JavaScript execution,
so this fetcher may fail and fallback to Playwright is expected.
"""

import re
import urllib3
from typing import Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from loguru import logger

# Suppress SSL warnings for 591's certificate issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.modules.objects import RentalObject, Surrounding
from src.utils.parsers import parse_floor

fetcher_log = logger.bind(module="BS4")


class ListFetcherBs4:
    """
    Lightweight list fetcher using requests + BeautifulSoup.

    Attempts to parse rental listings from HTML.
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
        self._session: Optional[requests.Session] = None

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
        section: Optional[int] = None,
        kind: Optional[int] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        other: Optional[list[str]] = None,
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

    def _parse_item(self, elem, region: int) -> Optional[RentalObject]:
        """
        Parse a single item element into RentalObject.

        Args:
            elem: BeautifulSoup element (div.item)
            region: Region code

        Returns:
            RentalObject or None if parsing fails
        """
        try:
            # Get ID from link URL (e.g., https://rent.591.com.tw/20503183)
            link = elem.find("a", href=re.compile(r"rent\.591\.com\.tw/\d+"))
            if not link:
                return None

            href = link.get("href", "")
            id_match = re.search(r"/(\d+)$", href)
            if not id_match:
                return None

            obj_id = int(id_match.group(1))
            url = href

            # Get title
            title_elem = elem.select_one(".item-info-title a")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Get price
            price_elem = elem.select_one(".item-info-price")
            price = "0"
            price_unit = "元/月"
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r"([\d,]+)", price_text)
                if price_match:
                    price = price_match.group(1)
                unit_match = re.search(r"(元/\S+)", price_text)
                if unit_match:
                    price_unit = unit_match.group(1)

            # Get area and floor from text
            text = elem.get_text()

            area = None
            area_match = re.search(r"([\d.]+)\s*坪", text)
            if area_match:
                area = float(area_match.group(1))

            floor_str = None
            floor = None
            total_floor = None
            is_rooftop = False
            floor_match = re.search(r"(\d+F/\d+F|B\d+/\d+F|頂[加樓])", text)
            if floor_match:
                floor_str = floor_match.group(1)
                floor, total_floor, is_rooftop = parse_floor(floor_str)

            # Get kind_name, layout_str, address from item-info-txt spans
            kind_name = None
            layout_str = None
            address = None
            txt_elem = elem.select_one(".item-info-txt")
            if txt_elem:
                spans = txt_elem.find_all("span")
                for span in spans:
                    span_text = span.get_text(strip=True)
                    # First span is kind_name (整層住家, 獨立套房, etc.)
                    if kind_name is None and span_text in ["整層住家", "獨立套房", "分租套房", "雅房"]:
                        kind_name = span_text
                    # Layout pattern: X房X廳, X房, or 開放格局
                    elif layout_str is None and (re.match(r"^\d+房", span_text) or span_text == "開放格局"):
                        layout_str = span_text
                    # Address contains 區 and street info
                    elif address is None and "區" in span_text and ("-" in span_text or "路" in span_text or "街" in span_text):
                        address = span_text

            # Get tags
            tags = []
            tag_elems = elem.select(".item-info-tag span")
            for tag in tag_elems:
                tag_text = tag.get_text(strip=True)
                if tag_text:
                    tags.append(tag_text)

            return RentalObject(
                id=obj_id,
                title=title,
                url=url,
                region=region,
                price=price,
                price_unit=price_unit,
                area=area,
                floor_name=floor_str,
                floor=floor,
                total_floor=total_floor,
                is_rooftop=is_rooftop,
                layout_str=layout_str,
                kind_name=kind_name,
                address=address,
                tags=tags,
            )

        except Exception as e:
            fetcher_log.debug(f"Failed to parse item: {e}")
            return None

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
        Fetch rental objects from 591 using BS4.

        Args:
            region: City code (1=Taipei, 3=New Taipei)
            section: District code
            kind: Property type
            price_min: Minimum price
            price_max: Maximum price
            other: Feature tags
            sort: Sort order
            max_pages: Maximum pages to fetch
            max_items: Maximum items to return

        Returns:
            List of RentalObject objects (may be empty if BS4 cannot parse)
        """
        if self._session is None:
            await self.start()

        url = self._build_url(
            region=region,
            section=section,
            kind=kind,
            price_min=price_min,
            price_max=price_max,
            other=other,
            sort=sort,
        )

        fetcher_log.info(f"BS4 fetching: {url}")

        try:
            resp = self._session.get(url, timeout=self._timeout, verify=False)
            if resp.status_code != 200:
                fetcher_log.warning(f"HTTP {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")

            # Find item containers (div.item)
            items = soup.find_all("div", class_="item")

            if not items:
                fetcher_log.warning("No items found in HTML (591 may require JavaScript)")
                return []

            objects = []
            for elem in items:
                obj = self._parse_item(elem, region)
                if obj:
                    objects.append(obj)
                    fetcher_log.debug(f"Parsed {obj.id} {obj.title[:30]}")
                    if max_items and len(objects) >= max_items:
                        break

            fetcher_log.info(f"BS4 parsed {len(objects)} objects")
            return objects

        except requests.RequestException as e:
            fetcher_log.error(f"Request failed: {e}")
            return []
        except Exception as e:
            fetcher_log.error(f"BS4 parsing failed: {e}")
            return []


# Singleton instance
_bs4_fetcher: Optional[ListFetcherBs4] = None


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
