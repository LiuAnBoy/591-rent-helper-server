"""User Providers module for multi-platform authentication and notifications."""

from src.modules.providers.models import (
    TelegramAuthData,
    TelegramUser,
    UserProvider,
    UserProviderCreate,
    UserProviderResponse,
)
from src.modules.providers.redis_sync import (
    remove_subscription_from_redis,
    sync_subscription_to_redis,
    sync_user_subscriptions_to_redis,
)
from src.modules.providers.repository import UserProviderRepository
from src.modules.providers.telegram_auth import (
    parse_init_data,
    verify_and_parse_init_data,
    verify_init_data,
)

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
    "sync_subscription_to_redis",
    "remove_subscription_from_redis",
    "sync_user_subscriptions_to_redis",
]
