# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

591 租屋爬蟲通知系統 - A crawler system that automatically scrapes rental listings from Taiwan's 591.com.tw, matches them against user subscriptions, and sends Telegram notifications.

**Tech Stack:**
- Python 3.12+ with FastAPI
- PostgreSQL 16+ (asyncpg)
- Redis 7+ (caching & pub/sub)
- Playwright + BeautifulSoup4 (web scraping)
- python-telegram-bot (notifications)
- APScheduler (job scheduling)
- uv (package management)

## Common Commands

### Development Setup

```bash
# Install dependencies
uv sync

# Install Playwright browser
uv run playwright install chromium

# Start database services (Docker)
docker compose -f docker-compose.dev.yml up -d

# Run migrations
./deploy.sh migrate

# Start API server
uv run uvicorn src.api.main:app --reload
```

### Testing & Quality

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src

# Linting
uv run ruff check .

# Format code
uv run ruff format .

# Type checking
uv run mypy src
```

### Docker Operations

```bash
# Development (DB only)
docker compose -f docker-compose.dev.yml up -d

# Production deployment
./deploy.sh           # Auto-detect init/update
./deploy.sh init      # Force initial deployment
./deploy.sh update    # Force update deployment
./deploy.sh migrate   # Run migrations only
```

### Manual Crawler Testing

```bash
# Test list fetchers
python scripts/test_list_bs4.py --region 1 --limit 5
python scripts/test_list_playwright.py --region 1 --limit 5

# Test detail fetchers
python scripts/test_detail_bs4.py <object_id>
python scripts/test_detail_playwright.py <object_id>
```

## Architecture

```
scripts/                   # Manual test scripts
├── test_list_bs4.py      # BS4 list fetcher test
├── test_list_playwright.py # Playwright list fetcher test
├── test_detail_bs4.py    # BS4 detail fetcher test
└── test_detail_playwright.py # Playwright detail fetcher test

src/
├── api/                    # FastAPI application
│   ├── main.py            # App entry point, lifespan management
│   ├── dependencies.py    # Dependency injection (DB, Redis pools)
│   └── routes/            # API endpoints (auth, users, subscriptions, bindings)
│
├── channels/              # Notification channels (platform-agnostic)
│   ├── commands/          # Command handlers (start, help, list, notify, status)
│   │   ├── base.py       # Abstract command class
│   │   └── registry.py   # Command registration
│   └── telegram/          # Telegram implementation
│       ├── bot.py        # Bot wrapper
│       ├── handler.py    # Message routing
│       └── formatter.py  # Message formatting
│
├── connections/           # Database connections
│   ├── postgres.py       # asyncpg connection pool
│   └── redis.py          # Redis connection
│
├── crawler/               # Source-pluggable scraping (see docs/ADDING_A_SOURCE.md)
│   ├── base.py            # Source Protocol + ListBatch/DetailBatch
│   ├── contract.py        # DBReadyData (standardized output contract, all sources)
│   ├── registry.py        # Source registry (get_source / all_sources)
│   ├── workers.py         # Generic worker-count helpers
│   └── sources/
│       └── x591/          # 591 source (first impl; template for new sources)
│           ├── source.py             # X591Source: drives pipeline, emits DBReadyData
│           ├── raw_types.py          # 591 raw TypedDicts
│           ├── combiner.py           # Merge list + detail raw
│           ├── transformers.py       # 591 raw → DBReadyData
│           ├── list_fetcher*.py      # List fetchers (BS4 → Playwright fallback)
│           └── detail_fetcher*.py    # Detail fetchers (BS4 → Playwright fallback)
│
├── jobs/                  # Background jobs (source-agnostic core)
│   ├── scheduler.py      # APScheduler configuration
│   ├── checker.py        # Main crawl job (drives Source: fetch_list → pre-filter → fetch_detail → save → match → notify)
│   ├── broadcaster.py    # Telegram notification sender
│   └── instant_notify.py # Immediate notification on subscription changes (uses Source.fetch_detail)
│
├── matching/              # Subscription matching module
│   ├── matcher.py        # Core matching logic (match_quick, match_full)
│   └── pre_filter.py     # Pre-filter functions for detail fetching
│
├── middleware/            # FastAPI middleware
│   ├── cors.py           # CORS configuration
│   └── logging.py        # Request logging
│
├── modules/               # Domain modules (repository pattern)
│   ├── users/            # User management
│   ├── providers/        # Auth providers (Telegram) & Redis sync
│   ├── subscriptions/    # Subscription CRUD & matching
│   └── objects/          # Rental object storage
│
└── utils/
    └── mappings/         # Constants and code mappings (package)
        ├── kind.py       # Rental kind codes
        ├── shape.py      # Building shape codes
        ├── fitment.py    # Fitment level codes
        ├── options.py    # Equipment option codes
        ├── other.py      # Feature ("other") codes
        └── sections/     # Region/section code tables (taipei, new_taipei)
```

> Adding a new rental source (dd-room, yungching, …) is a self-contained task:
> add `src/crawler/sources/<name>/`, implement the `Source` interface, register
> it in `registry.py`. The core and presentation layers do not change. Full
> guide: **`docs/ADDING_A_SOURCE.md`**.

## Testing Crawlers

If you need to test or debug crawler logic, use the scripts in `scripts/`:
- `test_list_bs4.py` / `test_list_playwright.py` - Test list fetching independently
- `test_detail_bs4.py` / `test_detail_playwright.py` - Test detail fetching independently

These scripts allow testing crawler components without running the full application.

## Key Patterns

### Source Plugin Architecture
Each rental origin is a `Source` (`src/crawler/base.py`) under `src/crawler/sources/<name>/`,
emitting standardized `DBReadyData` (`src/crawler/contract.py`). The core (checker / matcher /
repository) and presentation (channels) are source-agnostic; new origins register in
`src/crawler/registry.py`. **Full guide: `docs/ADDING_A_SOURCE.md`.**

### Crawler Fallback Strategy (591 source, internal)
- **List pages:** BS4 (3 retries) → Playwright fallback
- **Detail pages:** BS4 (3 retries) → Playwright fallback

### Notification Anti-Flood
- Per-subscription: a sub's first baseline scan is silent (suppressed until it has been seen once).
- Per-region: a region with no seen history (fresh start / flushed / expired seen set) treats the
  round as a **silent baseline** — objects saved + seen set seeded + subs marked initialized, but
  nothing notified. Next (warm) round notifies only genuinely-new listings.

### Repository Pattern
Each module in `src/modules/` follows:
- `models.py` - Pydantic models
- `repository.py` - Database operations (async)

## Database

PostgreSQL tables: `users`, `subscriptions`, `objects`, `crawler_runs`, `recent_objects` (view)

- `crawler_runs` — Tracks crawler execution status + broadcast results (total/success/failed/errors)

Migrations in `migrations/` folder, tracked via `schema_migrations` table.

## Environment Variables

Key variables (see `.env.example` for full list):
- `PG_*` - PostgreSQL connection
- `REDIS_*` - Redis connection
- `TELEGRAM_BOT_TOKEN` - Bot authentication
- `TELEGRAM_ADMIN_ID` - Admin notifications
- `JWT_SECRET` - API authentication
- `CRAWLER_INTERVAL_MINUTES` - Crawl frequency (default: 10)

## Test Coverage

**Total: 319 unit tests**

⚠️ **IMPORTANT: If you modify any code in the areas below, run `uv run pytest` to verify tests pass.**

### Unit Tests (`tests/unit/`)

| Module | Test File | Tests | Coverage |
|--------|-----------|-------|----------|
| `src/channels/telegram/formatter.py` | `test_formatter.py` | 25 | Message formatting, HTML escaping, gender line, command results |
| `src/crawler/sources/x591/` (extractors + combiner + detail success) | `test_extractors.py` | 51 | Data extraction, NUXT parsing, HTML parsing, raw data combining, rooftop preservation, `_is_valid_detail` |
| `src/crawler/sources/x591/` (full pipeline golden) | `test_pipeline_golden.py` | 2 | Exact `raw → DBReadyData` output (list+detail / list-only); refactor safety net |
| `src/crawler/sources/x591/source.py` (lifecycle) | `test_x591_source.py` | 3 | X591Source owns fresh fetchers; never closes injected ones |
| `src/matching/` | `test_matcher.py`, `test_pre_filter.py` | 139 | Subscription matching, parsing, floor extraction, pre-filtering, unknown/zero price+section exclusion |
| `src/crawler/sources/x591/transformers.py` | `test_transformers.py` | 80 | All data transformers (price + extra-fee, kind-from-name, floor, layout, area, gender, etc.) |
| `src/jobs/checker.py` (orchestration) | `test_checker_orchestration.py` | 13 | check() flow: pagination early-stop, pre-filter→detail, has_detail merge, seen-set, notify suppression, cold-region silent baseline, force_notify |
| `src/jobs/instant_notify.py` (orchestration) | `test_instant_notify_orchestration.py` | 6 | notify flow: redis-hit match, detail backfill+merge, pre-filter skip, redis-miss DB fallback |

### Test Details

**Channels (`test_formatter.py`)**
- `TestFormatObject` - Rental object formatting for Telegram
- `TestEscapeHtml` - HTML special character escaping
- `TestFormatCommandResult` - Bot command response formatting

**Crawler (`test_extractors.py`)**
- `TestCombineRawData` - Merging list + detail raw data (incl. rooftop marker preserved from list when detail reports a plain floor)
- `TestParseItemRawFromNuxt` - Playwright NUXT data parsing
- `TestParseItemRaw` / `TestParseDetailRaw` - BS4 HTML parsing (incl. `.pattern`-scoped fields, gender, fitment from structured value not free text)
- `TestExtractSurrounding` - Surrounding info extraction
- `TestIsValidDetail` - Shared BS4/Playwright detail success criterion (title + price)

**Matching (`test_matcher.py`, `test_pre_filter.py`)**
- `TestParsePriceValue` / `TestParseAreaValue` - Value parsing from raw strings
- `TestMatchQuick` - Quick matching (price/area; unknown/zero price excluded when a price filter is set)
- `TestMatchObjectToSubscription` - Full subscription matching (all criteria)
- `TestMatchFloor` / `TestExtractFloorNumber` - Floor extraction and matching
- `TestShouldFetchDetail` / `TestFilterObjects` - Pre-filter logic

**Utils (`test_transformers.py`)**
- Transform functions: ID, price (incl. extra-fee stripping), floor, layout, area, address, shape, fitment, gender (full-sentence forms), pet, options, surrounding
- `TestTransformToDbReady` - Full transformation pipeline (incl. kind derived from kind_name)

**Jobs orchestration (`test_checker_orchestration.py`, `test_instant_notify_orchestration.py`)**
- Characterization tests: drive a real `Checker` / `InstantNotifier` with faked deps, asserting on the observable boundary (dependency calls + result dict), not internals — so they survived the Source-ification refactor.
- `TestCheckOrchestration` - empty-page-1 failure, pagination early-stop / page-2-on-all-new, pre-filter limiting detail (incl. non-price/area + unknown-section), has_detail merge, seen-set seeding, initialized-sub broadcast vs uninitialized suppression, **cold-region silent baseline** + `force_notify` override, crawler_run success
- `TestInstantNotify` - redis-hit detailed match, has_detail=false backfill + merge fidelity, pre-filter skip, match-without-service_id, redis-miss DB load + cache populate

### Manual Test Scripts (`scripts/`)

```bash
# List fetchers (test ID extraction, pagination)
uv run python scripts/test_list_bs4.py --region 1 --limit 5
uv run python scripts/test_list_playwright.py --region 1 --limit 5

# Detail fetchers (test 404 handling, data parsing)
uv run python scripts/test_detail_bs4.py <object_id>
uv run python scripts/test_detail_playwright.py <object_id>

# Test 404 handling
uv run python scripts/test_detail_bs4.py 99999999
```

### Not Yet Covered

The following areas do not have unit tests:
- `src/api/` - API routes, dependencies
- `src/connections/` - Database connections
- `src/modules/` - Repository layer
- `src/jobs/` - `broadcaster.py` (incl. retry), `scheduler.py` (orchestration only). `checker.py` / `instant_notify.py` now have characterization coverage (see table above)
- `src/crawler/sources/x591/*_fetcher.py` - Fetcher orchestrators (only extractors, `_is_valid_detail`, the golden pipeline, and source lifecycle tested)
