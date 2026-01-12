"""Crawler modules."""

from src.crawler.rent591 import Rent591Crawler
from src.crawler.detail_fetcher import DetailFetcher, get_detail_fetcher
from src.crawler.detail_fetcher_bs4 import DetailFetcherBs4, get_bs4_fetcher
from src.crawler.detail_fetcher_playwright import (
    DetailFetcherPlaywright,
    get_playwright_fetcher,
)

__all__ = [
    "Rent591Crawler",
    "DetailFetcher",
    "DetailFetcherBs4",
    "DetailFetcherPlaywright",
    "get_detail_fetcher",
    "get_bs4_fetcher",
    "get_playwright_fetcher",
]
