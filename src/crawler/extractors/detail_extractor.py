"""
Detail page raw data extractor for 591 crawler.

This module extracts raw data from 591 detail pages without any transformation.
Part of the ETL Extract phase.
"""

import re

import requests
import urllib3
from bs4 import BeautifulSoup
from loguru import logger

from src.crawler.extractors.types import DetailRawData

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

extractor_log = logger.bind(module="BS4")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

# Shape names for matching
SHAPE_NAMES = ["公寓", "電梯大樓", "透天厝", "別墅"]

# Fitment names for matching
FITMENT_NAMES = ["新裝潢", "中檔裝潢", "高檔裝潢"]


def extract_detail_raw(
    object_id: int,
    session: requests.Session | None = None,
) -> DetailRawData | None:
    """
    Extract raw data from 591 detail page.

    Args:
        object_id: Object ID to fetch
        session: Optional requests session (creates new if not provided)

    Returns:
        DetailRawData dictionary or None if fetch failed

    Raises:
        requests.RequestException: If HTTP request fails
    """
    import time

    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    url = f"https://rent.591.com.tw/{object_id}"
    extractor_log.debug(f"Fetching detail page: {url}")

    # Wait before fetching to avoid rate limiting
    time.sleep(3)

    resp = session.get(url, timeout=15, verify=False)

    if resp.status_code != 200:
        extractor_log.warning(
            f"Failed to fetch detail page {object_id}: HTTP {resp.status_code}"
        )
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text()

    return _parse_detail_raw(soup, page_text, object_id)


def _parse_detail_raw(
    soup: BeautifulSoup, page_text: str, object_id: int
) -> DetailRawData:
    """
    Parse detail page and return raw data.

    No transformation is done - values are kept as-is from HTML.

    Args:
        soup: BeautifulSoup object of the page
        page_text: Full text content of the page
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

    # Title from h1
    title_elem = soup.find("h1")
    if title_elem:
        result["title"] = title_elem.get_text(strip=True)

    # Price from span.c-price
    price_elem = soup.select_one("span.c-price")
    if price_elem:
        result["price_raw"] = price_elem.get_text(strip=True)

    # Tags from span.label-item
    tags: list[str] = []
    tag_elems = soup.select("span.label-item")
    for tag in tag_elems:
        text = tag.get_text(strip=True)
        if text:
            tags.append(text)
    result["tags"] = tags

    # Address from div.address span.load-map
    addr_div = soup.find("div", class_="address")
    if addr_div:
        load_map = addr_div.find("span", class_="load-map")
        if load_map:
            result["address_raw"] = load_map.get_text(strip=True)

    # Breadcrumb for region, section, kind
    for link in soup.find_all("a", href=re.compile(r"region=\d+")):
        href = link.get("href", "")
        m = re.search(r"region=(\d+)", href)
        if m:
            result["region"] = m.group(1)
        m = re.search(r"section=(\d+)", href)
        if m:
            result["section"] = m.group(1)
        m = re.search(r"kind=(\d+)", href)
        if m:
            result["kind"] = m.group(1)

    # Floor from span matching pattern
    floor_pattern = re.compile(r"\d+F/\d+F|B\d+/\d+F|頂[層樓]加蓋")
    for elem in soup.find_all("span"):
        text = elem.get_text(strip=True)
        if floor_pattern.match(text):
            result["floor_raw"] = text
            break

    # Layout from page text - prioritize longer matches (4房2廳2衛 > 1房)
    layout_patterns = [
        r"([1-9]房\d+廳\d+衛)",  # Full: 4房2廳2衛
        r"([1-9]房\d+廳)",       # Partial: 2房1廳
        r"([1-9]房\d+衛)",       # Partial: 2房1衛
        r"([1-9]房|開放格局)",   # Fallback: 1房 or 開放格局
    ]
    for pattern in layout_patterns:
        m = re.search(pattern, page_text)
        if m:
            result["layout_raw"] = m.group(1)
            break

    # Area from page text
    m = re.search(r"[\d.]+\s*坪", page_text)
    if m:
        result["area_raw"] = m.group(0)

    # Gender restriction
    if "限男" in page_text:
        result["gender_raw"] = "限男"
    elif "限女" in page_text:
        result["gender_raw"] = "限女"

    # Shape (building type)
    for name in SHAPE_NAMES:
        if name in page_text:
            result["shape_raw"] = name
            break

    # Fitment (decoration level)
    for name in FITMENT_NAMES:
        if name in page_text:
            result["fitment_raw"] = name
            break

    # Options (equipment) - only items without 'del' class
    options: list[str] = []
    for dl in soup.find_all("dl"):
        if "del" not in dl.get("class", []):
            dd = dl.find("dd", class_="text")
            if dd:
                text = dd.get_text(strip=True)
                if text:
                    options.append(text)
    result["options"] = options

    # Surrounding (from traffic section)
    traffic = soup.find("div", class_="traffic")
    if traffic:
        for p in traffic.find_all("p"):
            classes = p.get("class", [])
            if "icon-subway" in classes:
                result["surrounding_type"] = "metro"
            elif "icon-bus" in classes:
                result["surrounding_type"] = "bus"
            else:
                continue

            # Get station name and distance
            name_elem = p.find("b", class_="ellipsis")
            dist_elem = p.find("strong")
            if name_elem and dist_elem:
                name = name_elem.get_text(strip=True)
                dist = dist_elem.get_text(strip=True)
                result["surrounding_raw"] = f"距{name}{dist}公尺"
            break  # Only take the first one

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
