"""
List page raw data extractor for 591 crawler.

This module extracts raw data from 591 list pages without any transformation.
Part of the ETL Extract phase.
"""

import re

import requests
import urllib3
from bs4 import BeautifulSoup
from loguru import logger

from src.crawler.extractors.types import ListRawData

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

extractor_log = logger.bind(module="ListExtractorBS4")

BASE_URL = "https://rent.591.com.tw/list"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# Kind name constants for matching
KIND_NAMES = ["整層住家", "獨立套房", "分租套房", "雅房", "車位", "其他"]


def extract_list_raw(
    region: int,
    page: int = 1,
    session: requests.Session | None = None,
) -> list[ListRawData]:
    """
    Extract raw data from 591 list page.

    Args:
        region: Region code (e.g., 1 for Taipei)
        page: Page number (default 1)
        session: Optional requests session (creates new if not provided)

    Returns:
        List of ListRawData dictionaries

    Raises:
        requests.RequestException: If HTTP request fails
    """
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    # Build URL with pagination
    offset = (page - 1) * 30
    url = f"{BASE_URL}?region={region}&sort=posttime_desc"
    if offset > 0:
        url += f"&firstRow={offset}"

    extractor_log.debug(f"Fetching list page: {url}")

    resp = session.get(url, timeout=15, verify=False)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.find_all("div", class_="item")

    extractor_log.debug(f"Found {len(items)} items on page {page}")

    results: list[ListRawData] = []
    for elem in items:
        try:
            raw_data = _parse_item_raw(elem, region)
            if raw_data.get("id"):
                results.append(raw_data)
        except Exception as e:
            extractor_log.warning(f"Failed to parse item: {e}")
            continue

    return results


def _parse_item_raw(elem: BeautifulSoup, region: int) -> ListRawData:
    """
    Parse a single item element and return raw data.

    No transformation is done - values are kept as-is from HTML.

    Args:
        elem: BeautifulSoup element for the item
        region: Region code

    Returns:
        ListRawData dictionary
    """
    result: ListRawData = {
        "region": region,
        "id": "",
        "url": "",
        "title": "",
        "price_raw": "",
        "tags": [],
        "kind_name": "",
        "area_raw": "",
        "floor_raw": "",
        "address_raw": "",
    }

    # ID from data-id attribute
    data_id = elem.get("data-id")
    if data_id:
        result["id"] = str(data_id)

    # URL from link
    link = elem.find("a", href=re.compile(r"rent\.591\.com\.tw/\d+"))
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
    # Note: layout is obtained from detail page for accuracy
    txt_elems = elem.select(".item-info-txt")
    for txt_elem in txt_elems:
        has_home = txt_elem.select_one(".house-home")
        has_place = txt_elem.select_one(".house-place")

        if has_home:
            # Parse by content pattern (not position)
            spans = txt_elem.find_all("span")
            for span in spans:
                text = span.get_text(strip=True)
                if not text:
                    continue

                # kind_name: exact match for property types
                if text in KIND_NAMES:
                    result["kind_name"] = text
                # area_raw: contains "坪" (e.g., "10坪")
                elif "坪" in text:
                    result["area_raw"] = text
                # floor_raw: contains "F" or "層" (e.g., "3F/5F")
                elif "F" in text or "層" in text:
                    result["floor_raw"] = text

        elif has_place:
            # Address (raw, including separators)
            result["address_raw"] = txt_elem.get_text(strip=True)

    return result


def create_session() -> requests.Session:
    """
    Create a configured requests session for 591.

    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    return session
