"""
Source registry.

Single place that knows which crawl origins exist. The core resolves sources
through here and never imports a concrete source directly, so adding an origin
is: implement ``Source`` under ``sources/<name>/`` and register its factory.

Sources need a Redis connection (for the seen-set early-stop), so factories take
one and build the source on demand.
"""

from collections.abc import Callable

from src.connections.redis import RedisConnection
from src.crawler.base import Source
from src.crawler.sources.x591.source import X591Source

# Factory per source key. Add new origins here.
_SOURCE_FACTORIES: dict[str, Callable[[RedisConnection], Source]] = {
    X591Source.key: lambda redis: X591Source(redis),
}


def source_keys() -> list[str]:
    """Return the registered source keys (e.g. ['591'])."""
    return list(_SOURCE_FACTORIES)


def get_source(key: str, redis: RedisConnection) -> Source:
    """Build the source registered under ``key``.

    Raises:
        KeyError: if no source is registered for ``key``.
    """
    return _SOURCE_FACTORIES[key](redis)


def all_sources(redis: RedisConnection) -> list[Source]:
    """Build one instance of every registered source."""
    return [factory(redis) for factory in _SOURCE_FACTORIES.values()]
