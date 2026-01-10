"""API routes module."""

from src.api.routes.auth import router as auth_router
from src.api.routes.bindings import router as bindings_router
from src.api.routes.checker import router as checker_router
from src.api.routes.health import router as health_router
from src.api.routes.subscriptions import router as subscriptions_router
from src.api.routes.telegram import router as telegram_router
from src.api.routes.users import router as users_router

__all__ = [
    "auth_router",
    "bindings_router",
    "checker_router",
    "health_router",
    "subscriptions_router",
    "telegram_router",
    "users_router",
]
