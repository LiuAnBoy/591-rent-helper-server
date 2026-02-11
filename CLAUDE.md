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
├── crawler/               # Web scraping modules
│   ├── list_fetcher.py           # List fetcher orchestrator
│   ├── list_fetcher_bs4.py       # BS4 list parser
│   ├── list_fetcher_playwright.py # Playwright list fetcher
│   ├── detail_fetcher.py         # Detail fetcher orchestrator (with fallback)
│   ├── detail_fetcher_bs4.py     # BS4 detail parser
│   └── detail_fetcher_playwright.py # Playwright detail fetcher
│
├── jobs/                  # Background jobs
│   ├── scheduler.py      # APScheduler configuration
│   ├── checker.py        # Main crawl job (list → filter → detail → save → notify)
│   ├── broadcaster.py    # Telegram notification sender
│   └── instant_notify.py # Immediate notification on subscription changes
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
    ├── mappings.py       # Constants and code mappings
    └── parsers/          # Data parsing utilities
        ├── detail.py     # Detail page data parser
        ├── layout.py     # Layout string parser (e.g., "3房2廳" → 3)
        ├── floor.py      # Floor string parser (e.g., "3/12" → floor info)
        ├── shape.py      # Building shape parser
        ├── fitment.py    # Fitment level parser
        └── rule.py       # Rule/restriction parser
```

## Testing Crawlers

If you need to test or debug crawler logic, use the scripts in `scripts/`:
- `test_list_bs4.py` / `test_list_playwright.py` - Test list fetching independently
- `test_detail_bs4.py` / `test_detail_playwright.py` - Test detail fetching independently

These scripts allow testing crawler components without running the full application.

## Key Patterns

### Crawler Fallback Strategy
- **List pages:** BS4 (3 retries) → Playwright fallback
- **Detail pages:** BS4 (3 retries) → Playwright fallback

### Repository Pattern
Each module in `src/modules/` follows:
- `models.py` - Pydantic models
- `repository.py` - Database operations (async)

## Database

PostgreSQL tables: `users`, `subscriptions`, `objects`, `notification_logs`, `crawler_runs`, `recent_objects` (view)

- `notification_logs` — Records every notification attempt (success/failed) with provider info and error details

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

**Total: 225 unit tests**

⚠️ **IMPORTANT: If you modify any code in the areas below, run `uv run pytest` to verify tests pass.**

### Unit Tests (`tests/unit/`)

| Module | Test File | Tests | Coverage |
|--------|-----------|-------|----------|
| `src/channels/telegram/formatter.py` | `test_formatter.py` | 22 | Message formatting, HTML escaping, command results |
| `src/crawler/` (extractors) | `test_extractors.py` | 29 | Data extraction, NUXT parsing, HTML parsing, raw data combining |
| `src/matching/` | `test_matcher.py`, `test_pre_filter.py` | 100 | Subscription matching, parsing, floor extraction, pre-filtering |
| `src/utils/` (transformers) | `test_transformers.py` | 74 | All data transformers (price, floor, layout, area, address, etc.) |

### Test Details

**Channels (`test_formatter.py`)**
- `TestFormatObject` - Rental object formatting for Telegram
- `TestEscapeHtml` - HTML special character escaping
- `TestFormatCommandResult` - Bot command response formatting

**Crawler (`test_extractors.py`)**
- `TestCombineRawData` - Merging list + detail raw data
- `TestParseItemRawFromNuxt` - Playwright NUXT data parsing
- `TestParseItemRaw` / `TestParseDetailRaw` - BS4 HTML parsing
- `TestExtractSurrounding` - Surrounding info extraction

**Matching (`test_matcher.py`, `test_pre_filter.py`)**
- `TestParsePriceValue` / `TestParseAreaValue` - Value parsing from raw strings
- `TestMatchQuick` - Quick matching (price/area only)
- `TestMatchObjectToSubscription` - Full subscription matching (all criteria)
- `TestMatchFloor` / `TestExtractFloorNumber` - Floor extraction and matching
- `TestShouldFetchDetail` / `TestFilterObjects` - Pre-filter logic

**Utils (`test_transformers.py`)**
- Transform functions: ID, price, floor, layout, area, address, shape, fitment, gender, pet, options, surrounding
- `TestTransformToDbReady` - Full transformation pipeline

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
- `src/jobs/broadcaster.py`, `instant_notify.py` - Notification jobs (orchestration only)
- `src/crawler/*_fetcher.py` - Fetcher orchestrators (only extractors tested)
