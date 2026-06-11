"""
Source registry / manifest.

Single declaration of every crawl origin. Add an origin = implement ``Source``
under ``sources/<name>/`` and append one ``SourceDescriptor`` to ``SOURCES``;
the core resolves sources / metadata / policy through the helpers below and
never imports a concrete source directly.

Sources need a Redis connection (for the seen-set early-stop), so descriptors
carry a factory that builds the source on demand.
"""

from collections.abc import Callable
from dataclasses import dataclass

from src.connections.redis import RedisConnection
from src.crawler.base import Source
from src.crawler.sources.x591.source import X591Source


@dataclass(frozen=True)
class SourceDescriptor:
    """One crawl origin's full declaration.

    Attributes:
        key: Stable origin id, matches ``DBReadyData["source"]`` (e.g. "591").
        name: Human display name for UI / TG label (e.g. "591 租屋網").
        factory: Builds the Source given a Redis connection.
        fetch_all: Default detail-fetch policy (overridable via settings.sources).
    """

    key: str
    name: str
    factory: Callable[[RedisConnection], Source]
    fetch_all: bool = True


# ▼ 加新來源只改這裡一筆 ▼
SOURCES: list[SourceDescriptor] = [
    SourceDescriptor(
        key=X591Source.key,
        name="591 租屋網",
        factory=lambda redis: X591Source(redis),
        fetch_all=True,
    ),
]

_BY_KEY: dict[str, SourceDescriptor] = {d.key: d for d in SOURCES}


def source_keys() -> list[str]:
    """Return the registered source keys (e.g. ['591'])."""
    return [d.key for d in SOURCES]


def source_catalog() -> list[dict]:
    """Return ``[{"key", "name"}]`` for UI / TG label rendering."""
    return [{"key": d.key, "name": d.name} for d in SOURCES]


def source_default_fetch_all(key: str) -> bool:
    """Manifest default fetch_all for ``key``.

    Raises:
        KeyError: if no source is registered for ``key``.
    """
    return _BY_KEY[key].fetch_all


def get_source(key: str, redis: RedisConnection) -> Source:
    """Build the source registered under ``key``.

    Raises:
        KeyError: if no source is registered for ``key``.
    """
    return _BY_KEY[key].factory(redis)


def all_sources(redis: RedisConnection) -> list[Source]:
    """Build one instance of every registered source."""
    return [d.factory(redis) for d in SOURCES]
