"""Authentication routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.connections.postgres import get_postgres
from src.modules.users import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    UserRepository,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_repository() -> UserRepository:
    """Get user repository instance."""
    postgres = await get_postgres()
    return UserRepository(postgres.pool)


@router.post("/register", status_code=201)
async def register(data: UserCreate) -> dict:
    """
    Register a new user.

    Args:
        data: User registration data (email, password)

    Returns:
        Success status
    """
    repo = await get_repository()

    try:
        user = await repo.create(email=data.email, password=data.password)

        if not user:
            raise HTTPException(
                status_code=400,
                detail="此 Email 已被註冊"
            )

        logger.info(f"New user registered: {data.email}")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="註冊失敗")


@router.post("/login")
async def login(data: UserLogin) -> dict:
    """
    Login and get access token.

    Args:
        data: Login credentials (email, password)

    Returns:
        Access token
    """
    repo = await get_repository()

    try:
        user = await repo.authenticate(email=data.email, password=data.password)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Email 或密碼錯誤"
            )

        # Create access token
        token, expires_in = repo.create_access_token(user.id, user.email, user.role)

        logger.info(f"User logged in: {data.email}")

        return {"token": token}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="登入失敗")


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
        verify_and_parse_init_data,
        UserProviderRepository,
    )

    settings = Settings()
    bot_token = settings.telegram.bot_token

    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        raise HTTPException(status_code=500, detail="Telegram 登入未設定")

    # Debug logging
    logger.debug(f"Received initData length: {len(data.initData)}")
    logger.debug(f"initData preview: {data.initData[:100]}...")

    # Verify and parse initData
    auth_data = verify_and_parse_init_data(data.initData, bot_token)

    if not auth_data:
        logger.warning("Failed to verify/parse initData")
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
            logger.info(f"Telegram user logged in: {telegram_user.id}")
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
            logger.info(f"New Telegram user created: {telegram_user.id} -> user {user.id}")

        # Create access token
        token, expires_in = user_repo.create_access_token(
            user.id, user.email, user.role
        )

        # Get user providers for response
        providers = await provider_repo.get_by_user(user.id)

        return {
            "token": token,
            "user": {
                "id": user.id,
                "name": user.name,
                "role": user.role,
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
        logger.error(f"Telegram login failed: {e}")
        raise HTTPException(status_code=500, detail="Telegram 登入失敗")