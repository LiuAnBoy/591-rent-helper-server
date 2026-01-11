"""
FastAPI Application.

Main entry point for the API server.
"""

import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env file at startup
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

# Configure loguru format
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="DEBUG",
)

from src.api.routes import (
    auth_router,
    bindings_router,
    checker_router,
    health_router,
    subscriptions_router,
    telegram_router,
    users_router,
)
from src.api.routes.telegram import init_bot, auto_setup_webhook
from src.jobs import scheduler
from src.middleware import setup_middleware


async def sync_subscriptions_on_startup():
    """Sync all subscriptions from PostgreSQL to Redis on startup."""
    try:
        checker = scheduler.get_checker()
        count = await checker.sync_subscriptions_to_redis()
        logger.info(f"Startup: Synced {count} subscriptions to Redis")
    except Exception as e:
        logger.error(f"Failed to sync subscriptions on startup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Initialize Telegram bot and auto-setup webhook
    await init_bot()
    await auto_setup_webhook()

    # Sync subscriptions to Redis on startup
    await sync_subscriptions_on_startup()

    # Start scheduler
    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown()
    await scheduler.close_checker()
    logger.info("Server stopped")


app = FastAPI(
    title="591 Crawler API",
    description="591 rental listing crawler with notification system",
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
