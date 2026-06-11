"""Source manifest / registry tests."""

import pytest

from src.crawler import registry


def test_source_keys_from_manifest():
    assert registry.source_keys() == ["591"]


def test_source_catalog_has_key_and_name():
    catalog = registry.source_catalog()
    assert catalog == [{"key": "591", "name": "591 租屋網"}]


def test_source_default_fetch_all_known():
    assert registry.source_default_fetch_all("591") is True


def test_source_default_fetch_all_unknown_raises():
    with pytest.raises(KeyError):
        registry.source_default_fetch_all("nope")


def test_get_source_unknown_raises():
    with pytest.raises(KeyError):
        registry.get_source("nope", redis=None)
