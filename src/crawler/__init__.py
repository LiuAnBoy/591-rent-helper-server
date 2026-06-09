"""Crawler package.

Source-agnostic core lives at the top level (``contract``, ``workers``; later
``base`` + ``registry``); 591-specific fetchers/parsers live under
``sources/x591/``. Intentionally kept import-light: submodules are imported
directly by their consumers, so importing ``src.crawler.contract`` does not drag
in heavy fetcher dependencies (e.g. Playwright).
"""
