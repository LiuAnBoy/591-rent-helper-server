"""Crawler modules."""

from src.crawler.rent591 import Rent591Crawler
from src.crawler.object_detail import ObjectDetailCrawler, get_detail_crawler

__all__ = ["Rent591Crawler", "ObjectDetailCrawler", "get_detail_crawler"]
