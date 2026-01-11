"""
Request Logging Middleware.

Logs all HTTP requests with method, path, status code and duration.
"""

import time

from fastapi import FastAPI, Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests."""

    async def dispatch(self, request: Request, call_next):
        """Log request method, path, status and duration."""
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} ({duration_ms:.0f}ms)"
        )

        return response


def setup_logging(app: FastAPI) -> None:
    """
    Configure logging middleware.

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(LoggingMiddleware)
