"""
Source interface (the per-origin crawl contract).

A ``Source`` encapsulates everything origin-specific about producing rental
objects: list crawling, pagination, detail fetching and the raw->standardized
transform. Past this boundary the result is always ``DBReadyData`` — the core
(dedup / pre-filter / save / match / notify) and the presentation layer never
see raw, origin-specific shapes.

Adding a new origin = add a ``sources/<name>/`` package implementing this
protocol and register it; the core does not change.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from src.crawler.contract import DBReadyData


@dataclass
class ListBatch:
    """Result of ``Source.fetch_list`` for one region.

    Attributes:
        items: New (not-yet-seen) listings, already standardized, with
            ``has_detail=False``. The source is responsible for pagination and
            for excluding already-seen items.
        total_fetched: Total listings fetched across all pages this call,
            including already-seen ones (used for crawler-run accounting). A
            value of 0 means the first list page returned nothing (fetch
            failure), which the core surfaces as an error.
    """

    items: list[DBReadyData] = field(default_factory=list)
    total_fetched: int = 0


@dataclass
class DetailBatch:
    """Result of ``Source.fetch_detail`` for a set of candidate items.

    Attributes:
        enriched: Standardized objects with ``has_detail=True``, keyed by
            ``source_id``. Only contains items whose detail was fetched
            successfully.
        not_found: Count of candidates whose detail page was a 404.
        failed: Count of candidates whose detail fetch errored (non-404).
        failed_ids: source_ids of every candidate with no successful detail.
            The fetcher reports only aggregate not_found/failed counts (not
            per-id status), so this list includes both 404s and errors; it is
            used for an admin alert that only fires when ``failed`` > 0.
    """

    enriched: dict[str, DBReadyData] = field(default_factory=dict)
    not_found: int = 0
    failed: int = 0
    failed_ids: list[str] = field(default_factory=list)


@runtime_checkable
class Source(Protocol):
    """Contract every crawl origin implements.

    The core iterates registered sources and drives them through this protocol
    only; it has no knowledge of 591 / dd-room / etc. specifics.
    """

    key: str  # stable origin id, e.g. "591" — matches DBReadyData["source"]

    async def start(self) -> None:
        """Acquire any resources (browsers, sessions)."""
        ...

    async def close(self) -> None:
        """Release resources acquired in start()."""
        ...

    async def fetch_list(self, region: int, max_pages: int) -> ListBatch:
        """Crawl a region's list pages and return new, standardized listings.

        The source handles its own pagination and de-duplicates against
        already-seen items (so only genuinely new listings are returned), and
        keeps whatever internal state it needs to later enrich them.
        """
        ...

    async def fetch_detail(self, items: list[DBReadyData]) -> DetailBatch:
        """Fetch detail pages for the given candidates and return enriched data.

        ``items`` are standardized objects previously returned by
        ``fetch_list`` (identified by ``source_id``). Returns the successfully
        enriched objects (``has_detail=True``) keyed by ``source_id``.
        """
        ...
