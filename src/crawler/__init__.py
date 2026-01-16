"""Crawler modules."""

from src.crawler.combiner import (
    combine_raw_data,
    combine_with_detail_only,
    combine_with_list_only,
)
from src.crawler.detail_fetcher import DetailFetcher, get_detail_fetcher
from src.crawler.detail_fetcher_bs4 import DetailFetcherBs4
from src.crawler.detail_fetcher_playwright import DetailFetcherPlaywright
from src.crawler.list_fetcher import ListFetcher, get_list_fetcher
from src.crawler.list_fetcher_bs4 import ListFetcherBs4
from src.crawler.list_fetcher_playwright import ListFetcherPlaywright
from src.crawler.types import CombinedRawData, DetailRawData, ListRawData

__all__ = [
    # Types
    "ListRawData",
    "DetailRawData",
    "CombinedRawData",
    # Combiner
    "combine_raw_data",
    "combine_with_detail_only",
    "combine_with_list_only",
    # List fetchers
    "ListFetcher",
    "ListFetcherBs4",
    "ListFetcherPlaywright",
    "get_list_fetcher",
    # Detail fetchers
    "DetailFetcher",
    "DetailFetcherBs4",
    "DetailFetcherPlaywright",
    "get_detail_fetcher",
]
