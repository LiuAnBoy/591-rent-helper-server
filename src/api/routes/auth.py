"""Authentication routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.connections.postgres import get_postgres

auth_log = logger.bind(module="Auth")

from src.modules.users import UserRepository  # noqa: E402

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_repository() -> UserRepository:
    """Get user repository instance."""
    postgres = await get_postgres()
    return UserRepository(postgres.pool)


class TelegramLoginRequest(BaseModel):
    """Request model for Telegram Web App login."""

    initData: str = Field(..., description="Telegram Web App initData string")


@router.post("/telegram")
async def telegram_login(data: TelegramLoginRequest) -> dict:
    """
    Login via Telegram Web App.

    Verifies initData from Telegram Web App and creates/finds user.

    Args:
        data: Telegram login data containing initData

    Returns:
        JWT token and user info
    """
    from config.settings import Settings
    from src.modules.providers import (
        UserProviderRepository,
        verify_and_parse_init_data,
    )

    settings = Settings()
    bot_token = settings.telegram.bot_token

    if not bot_token:
        auth_log.error("TELEGRAM_BOT_TOKEN not configured")
        raise HTTPException(status_code=500, detail="Telegram 登入未設定")

    # Debug logging
    auth_log.debug(f"Received initData length: {len(data.initData)}")
    auth_log.debug(f"initData preview: {data.initData[:100]}...")

    # Verify and parse initData
    auth_data = verify_and_parse_init_data(data.initData, bot_token)

    if not auth_data:
        auth_log.warning("Failed to verify/parse initData")
        raise HTTPException(status_code=401, detail="Invalid Telegram auth data")

    telegram_user = auth_data.user
    provider_id = str(telegram_user.id)

    # Get repositories
    user_repo = await get_repository()
    postgres = await get_postgres()
    provider_repo = UserProviderRepository(postgres.pool)

    try:
        # Find existing user by provider
        user = await user_repo.find_by_provider("telegram", provider_id)
        auth_log.debug(f"find_by_provider result: {user}")

        if user:
            # Update provider data if user exists
            provider_data = {
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
                "language_code": telegram_user.language_code,
                "photo_url": telegram_user.photo_url,
            }
            await provider_repo.update_provider_data(user.id, "telegram", provider_data)
            auth_log.info(f"Telegram user logged in: {telegram_user.id}")
        else:
            # Create new user from Telegram
            display_name = telegram_user.first_name
            if telegram_user.last_name:
                display_name += f" {telegram_user.last_name}"

            user = await user_repo.create_from_provider(name=display_name)

            # Create provider binding
            provider_data = {
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
                "language_code": telegram_user.language_code,
                "photo_url": telegram_user.photo_url,
            }
            await provider_repo.create(
                user_id=user.id,
                provider="telegram",
                provider_id=provider_id,
                provider_data=provider_data,
            )
            auth_log.info(
                f"New Telegram user created: {telegram_user.id} -> user {user.id}"
            )

        # Create access token
        token, expires_in = user_repo.create_access_token(
            user.id, user.email, user.role
        )

        # Get user providers for response
        providers = await provider_repo.get_by_user(user.id)

        # Get max subscriptions for user's role
        max_subscriptions = await user_repo.get_role_limit(user.role)

        return {
            "token": token,
            "user": {
                "id": user.id,
                "name": user.name,
                "role": user.role,
                "max_subscriptions": max_subscriptions,
                "providers": [
                    {
                        "provider": p.provider,
                        "provider_id": p.provider_id,
                        "notify_enabled": p.notify_enabled,
                    }
                    for p in providers
                ],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        auth_log.error(f"Telegram login failed: {e}")
        raise HTTPException(status_code=500, detail="Telegram 登入失敗") from None
