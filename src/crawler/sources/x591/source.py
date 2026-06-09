"""
591 source implementation.

Wraps the 591 list/detail fetchers and the combine->transform pipeline behind
the generic ``Source`` interface, producing standardized ``DBReadyData``. All
591-specific orchestration (auto-pagination, the seen-set early-stop, BS4 ->
Playwright fallback inside the fetchers, list+detail merge) lives here; the core
only sees standardized objects.
"""

import asyncio

from loguru import logger

from src.connections.redis import RedisConnection
from src.crawler.base import DetailBatch, ListBatch
from src.crawler.contract import DBReadyData
from src.crawler.sources.x591.combiner import (
    combine_raw_data,
    combine_with_list_only,
)
from src.crawler.sources.x591.detail_fetcher import DetailFetcher
from src.crawler.sources.x591.list_fetcher import ListFetcher
from src.crawler.sources.x591.raw_types import CombinedRawData, ListRawData
from src.crawler.sources.x591.transformers import transform_to_db_ready

x591_log = logger.bind(module="X591")


class X591Source:
    """Source implementation for rent.591.com.tw."""

    key = "591"

    PAGE_SIZE = 30  # items per list page
    SORT = "posttime_desc"

    def __init__(
        self,
        redis: RedisConnection,
        list_fetcher: ListFetcher | None = None,
        detail_fetcher: DetailFetcher | None = None,
        detail_max_workers: int = 3,
    ):
        """
        Args:
            redis: Redis connection (used for the seen-set early-stop during
                pagination; the source does its own dedup so the core receives
                only new listings).
            list_fetcher: Injectable list fetcher (created on start() if None).
            detail_fetcher: Injectable detail fetcher (created on start() if None).
            detail_max_workers: Max parallel workers for detail fetching.
        """
        self._redis = redis
        self._list_fetcher = list_fetcher
        self._detail_fetcher = detail_fetcher
        self._detail_max_workers = detail_max_workers
        self._owns_list = False
        self._owns_detail = False
        # Raw list data kept between fetch_list and fetch_detail so detail can be
        # merged with the original list row (detail pages drop some list fields).
        self._list_raw_by_id: dict[str, ListRawData] = {}

    async def start(self) -> None:
        """Create and start owned fetchers (no-op for injected ones).

        Fresh per-instance fetchers (NOT the get_*_fetcher singletons): instant
        notify builds its own source and closes it, so sharing the singleton
        would tear down the browser the scheduled checker is still using.
        """
        if self._list_fetcher is None:
            self._list_fetcher = ListFetcher(headless=True)
            self._owns_list = True
            await self._list_fetcher.start()
        if self._detail_fetcher is None:
            self._detail_fetcher = DetailFetcher(
                playwright_max_workers=self._detail_max_workers
            )
            self._owns_detail = True
            await self._detail_fetcher.start()

    async def close(self) -> None:
        """Close only fetchers this source created (never injected ones)."""
        if self._owns_list and self._list_fetcher:
            await self._list_fetcher.close()
        if self._owns_detail and self._detail_fetcher:
            await self._detail_fetcher.close()

    async def fetch_list(self, region: int, max_pages: int) -> ListBatch:
        """Crawl list pages for a region; return new, standardized listings.

        Auto-pagination: keep fetching while a page is entirely new (so a burst
        of new listings is fully captured), and stop as soon as a page contains
        an already-seen id (we have caught up). De-dup is done here against the
        Redis seen set so only new listings reach the core.
        """
        self._list_raw_by_id = {}
        new_raw_items: list[ListRawData] = []
        total_fetched = 0

        for page in range(max_pages):
            first_row = page * self.PAGE_SIZE
            page_items = await self._list_fetcher.fetch_objects_raw(
                region=region,
                sort=self.SORT,
                first_row=first_row,
            )

            if not page_items:
                if page == 0:
                    # First page returned nothing -> fetch failure (signalled by
                    # total_fetched=0 so the core can alert).
                    return ListBatch(items=[], total_fetched=0)
                break

            total_fetched += len(page_items)

            page_ids = {int(item["id"]) for item in page_items if item.get("id")}
            new_ids_in_page = await self._redis.get_new_ids(region, page_ids)

            for item in page_items:
                if item.get("id") and int(item["id"]) in new_ids_in_page:
                    new_raw_items.append(item)

            x591_log.info(f"Page {page + 1}: {len(new_ids_in_page)}/{len(page_items)} new")

            # A page with any already-seen id means we have caught up; stop.
            if len(new_ids_in_page) < len(page_items):
                break

            # Whole page new -> there may be more; rate-limit before next page.
            if page < max_pages - 1:
                x591_log.info("All items are new, fetching next page...")
                await asyncio.sleep(1)

        # Standardize list-only (has_detail=False) and cache raw for fetch_detail.
        items: list[DBReadyData] = []
        for raw in new_raw_items:
            self._list_raw_by_id[str(raw["id"])] = raw
            items.append(transform_to_db_ready(combine_with_list_only(raw)))

        x591_log.info(
            f"Fetched {total_fetched} objects from list, {len(items)} new"
        )
        return ListBatch(items=items, total_fetched=total_fetched)

    async def fetch_detail(self, items: list[DBReadyData]) -> DetailBatch:
        """Fetch detail pages for candidates; merge and standardize.

        Two entry shapes are supported via one contract:
        - items that came from this source's ``fetch_list`` (their original list
          raw is cached) -> merge list raw + detail (full fidelity);
        - items that did not (e.g. objects loaded from the Redis cache) -> merge
          the standardized object's own list-origin fields + detail.
        """
        ids_need_detail = [
            int(item["source_id"]) for item in items if item.get("source_id")
        ]
        if not ids_need_detail:
            return DetailBatch()

        await asyncio.sleep(1)  # rate-limit between list and detail crawling
        details, not_found, failed = await self._detail_fetcher.fetch_details_batch_raw(
            ids_need_detail
        )

        enriched: dict[str, DBReadyData] = {}
        for item in items:
            source_id = item["source_id"]
            detail_raw = details.get(int(source_id))
            if not detail_raw:
                continue
            list_raw = self._list_raw_by_id.get(source_id)
            if list_raw is not None:
                combined = combine_raw_data(list_raw, detail_raw)
            else:
                combined = self._combined_from_standardized(item, detail_raw)
            enriched[source_id] = transform_to_db_ready(combined)

        failed_ids = [str(i) for i in ids_need_detail if i not in details]
        return DetailBatch(
            enriched=enriched,
            not_found=not_found,
            failed=failed,
            failed_ids=failed_ids,
        )

    @staticmethod
    def _combined_from_standardized(obj: DBReadyData, detail_raw) -> CombinedRawData:
        """Build CombinedRawData from a standardized object + fresh detail raw.

        Used when enriching an object whose original list raw is no longer
        around (e.g. loaded from the Redis cache): list-origin fields come from
        the standardized object, detail-origin fields from the detail page.
        """
        return {
            "id": str(obj["source_id"]),
            "url": obj.get("url", ""),
            "title": obj.get("title", ""),
            "price_raw": str(obj.get("price", "")),
            "tags": obj.get("tags", []),
            "kind_name": obj.get("kind_name", ""),
            "address_raw": obj.get("address", ""),
            "surrounding_type": detail_raw.get("surrounding_type"),
            "surrounding_raw": detail_raw.get("surrounding_raw"),
            "region": str(obj.get("region", "")),
            "section": str(obj.get("section", "")),
            "kind": str(obj.get("kind", "")),
            "floor_raw": detail_raw.get("floor_raw", ""),
            "layout_raw": detail_raw.get("layout_raw", ""),
            "area_raw": detail_raw.get("area_raw", ""),
            "gender_raw": detail_raw.get("gender_raw"),
            "shape_raw": detail_raw.get("shape_raw"),
            "fitment_raw": detail_raw.get("fitment_raw"),
            "options": detail_raw.get("options", []),
            "has_detail": True,
        }
