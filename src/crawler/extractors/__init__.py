"""
ETL Extractors for 591 crawler.

This package contains modules for extracting raw data from 591 pages.
Supports both BS4 (HTML) and NUXT (Playwright) extraction methods.
"""

from src.crawler.extractors.combiner import (
    combine_raw_data,
    combine_with_detail_only,
)
from src.crawler.extractors.detail_extractor import (
    create_session as create_detail_session,
)
from src.crawler.extractors.detail_extractor import (
    extract_detail_raw,
)
from src.crawler.extractors.detail_extractor_nuxt import (
    extract_detail_raw_from_nuxt,
)
from src.crawler.extractors.list_extractor import (
    create_session as create_list_session,
)
from src.crawler.extractors.list_extractor import (
    extract_list_raw,
)
from src.crawler.extractors.list_extractor_nuxt import (
    extract_list_raw_from_nuxt,
    get_total_from_nuxt,
)
from src.crawler.extractors.types import (
    CombinedRawData,
    DetailRawData,
    ListRawData,
)

__all__ = [
    # Types
    "ListRawData",
    "DetailRawData",
    "CombinedRawData",
    # List extractor (BS4/HTML)
    "extract_list_raw",
    "create_list_session",
    # List extractor (NUXT/Playwright)
    "extract_list_raw_from_nuxt",
    "get_total_from_nuxt",
    # Detail extractor (BS4/HTML)
    "extract_detail_raw",
    "create_detail_session",
    # Detail extractor (NUXT/Playwright)
    "extract_detail_raw_from_nuxt",
    # Combiner
    "combine_raw_data",
    "combine_with_detail_only",
]
