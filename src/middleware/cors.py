"""
CORS Middleware Configuration.

Handles Cross-Origin Resource Sharing settings.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def setup_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware for the application.

    Args:
        app: FastAPI application instance
    """
    origins = os.getenv("CORS_ORIGINS", "*").split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
