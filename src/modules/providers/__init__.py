"""User Providers module for multi-platform authentication and notifications."""

from src.modules.providers.models import (
    UserProvider,
    UserProviderCreate,
    UserProviderResponse,
    TelegramAuthData,
    TelegramUser,
)
from src.modules.providers.repository import UserProviderRepository
from src.modules.providers.telegram_auth import (
    verify_init_data,
    parse_init_data,
    verify_and_parse_init_data,
)
from src.modules.providers.redis_sync import sync_user_subscriptions_to_redis

__all__ = [
    "UserProvider",
    "UserProviderCreate",
    "UserProviderResponse",
    "UserProviderRepository",
    "TelegramAuthData",
    "TelegramUser",
    "verify_init_data",
    "parse_init_data",
    "verify_and_parse_init_data",
    "sync_user_subscriptions_to_redis",
]
