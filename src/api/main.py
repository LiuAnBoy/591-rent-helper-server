"""
FastAPI Application.

Main entry point for the API server.
"""

import logging
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env file at startup
load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from loguru import logger  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402


class InterceptHandler(logging.Handler):
    """Intercept standard logging and redirect to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Configure loguru format with default module
logger.configure(extra={"module": "Server"})
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[module]: <14}</cyan> | <level>{message}</level>",
    level="DEBUG",
)

# Intercept uvicorn logs
for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uv_logger = logging.getLogger(name)
    uv_logger.handlers = [InterceptHandler()]
    uv_logger.propagate = False

log = logger.bind(module="App")

from src.api.routes import (  # noqa: E402
    auth_router,
    bindings_router,
    checker_router,
    health_router,
    subscriptions_router,
    telegram_router,
    users_router,
)
from src.api.routes.telegram import auto_setup_webhook, init_bot  # noqa: E402
from src.jobs import scheduler  # noqa: E402
from src.middleware import setup_middleware  # noqa: E402


async def sync_subscriptions_on_startup():
    """Sync all subscriptions from PostgreSQL to Redis on startup."""
    try:
        checker = scheduler.get_checker()
        count = await checker.sync_subscriptions_to_redis()
        log.info(f"Startup: Synced {count} subscriptions to Redis")
    except Exception as e:
        log.error(f"Failed to sync subscriptions on startup: {e}")


async def init_redis_objects_cache():
    """
    Initialize Redis objects cache on startup.

    For each active region, check if Redis has cached objects.
    If not, load from DB to populate the cache.
    """
    from src.connections.postgres import get_postgres
    from src.connections.redis import get_redis
    from src.modules.objects import ObjectRepository

    try:
        redis = await get_redis()
        postgres = await get_postgres()
        repo = ObjectRepository(postgres.pool)

        # Get active regions from subscriptions
        active_regions = await redis.get_active_regions()

        if not active_regions:
            log.info("Startup: No active regions, skipping objects cache init")
            return

        log.info(
            f"Startup: Initializing Redis objects cache for {len(active_regions)} regions"
        )

        for region in active_regions:
            # Check if Redis already has objects for this region
            if await redis.has_region_objects(region):
                log.debug(f"Region {region}: objects cache already exists, skipping")
                continue

            # Load from DB
            objects = await repo.get_latest_by_region(region, 30)
            if objects:
                await redis.set_region_objects(region, objects)
                log.info(
                    f"Region {region}: loaded {len(objects)} objects from DB to Redis"
                )
            else:
                log.debug(f"Region {region}: no objects in DB")

    except Exception as e:
        log.error(f"Failed to initialize Redis objects cache: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Initialize Telegram bot and auto-setup webhook
    await init_bot()
    await auto_setup_webhook()

    # Sync subscriptions to Redis on startup
    await sync_subscriptions_on_startup()

    # Initialize Redis objects cache
    await init_redis_objects_cache()

    # Start scheduler
    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown()
    await scheduler.close_checker()
    log.info("Server stopped")


app = FastAPI(
    title="591 Crawler API",
    description="591 rental object crawler with notification system",
    version="0.1.0",
    lifespan=lifespan,
)

# Setup middleware
setup_middleware(app)

# Register routes
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(bindings_router)
app.include_router(checker_router)
app.include_router(subscriptions_router)
app.include_router(telegram_router)


# Custom exception handlers for unified error response format
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Convert HTTPException to unified error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convert validation errors to unified error format."""
    errors = exc.errors()
    if errors:
        # Get first error message
        first_error = errors[0]
        field = ".".join(str(loc) for loc in first_error.get("loc", []))
        msg = first_error.get("msg", "Validation error")
        message = f"{field}: {msg}" if field else msg
    else:
        message = "Validation error"

    return JSONResponse(
        status_code=422,
        content={"success": False, "message": message},
    )
