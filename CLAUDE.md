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
├── middleware/            # FastAPI middleware
│   ├── cors.py           # CORS configuration
│   └── logging.py        # Request logging
│
├── modules/               # Domain modules (repository pattern)
│   ├── users/            # User management
│   ├── providers/        # Auth providers (Telegram)
│   ├── subscriptions/    # Subscription CRUD & matching
│   ├── bindings/         # Channel bindings (notification toggles)
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

## Key Patterns

### Crawler Fallback Strategy
- **List pages:** BS4 (3 retries) → Playwright fallback
- **Detail pages:** BS4 (3 retries) → Playwright fallback

### Repository Pattern
Each module in `src/modules/` follows:
- `models.py` - Pydantic models
- `repository.py` - Database operations (async)

## Database

PostgreSQL tables: `users`, `subscriptions`, `objects`, `recent_objects` (view)

Migrations in `migrations/` folder, tracked via `schema_migrations` table.

## Environment Variables

Key variables (see `.env.example` for full list):
- `PG_*` - PostgreSQL connection
- `REDIS_*` - Redis connection
- `TELEGRAM_BOT_TOKEN` - Bot authentication
- `TELEGRAM_ADMIN_ID` - Admin notifications
- `JWT_SECRET` - API authentication
- `CRAWLER_INTERVAL_MINUTES` - Crawl frequency (default: 15)
