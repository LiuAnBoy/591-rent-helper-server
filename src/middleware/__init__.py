"""
Middleware Module.

Exports middleware setup functions for FastAPI application.
"""

from fastapi import FastAPI

from src.middleware.cors import setup_cors
from src.middleware.logging import setup_logging


def setup_middleware(app: FastAPI) -> None:
    """
    Configure all middleware for the application.

    Args:
        app: FastAPI application instance
    """
    setup_cors(app)
    setup_logging(app)
