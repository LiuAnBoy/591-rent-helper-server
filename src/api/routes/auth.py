"""Authentication routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

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


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: UserCreate) -> dict:
    """
    Register a new user.

    Args:
        data: User registration data (email, password)

    Returns:
        Created user data
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

        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "enabled": user.enabled,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="註冊失敗")


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin) -> dict:
    """
    Login and get access token.

    Args:
        data: Login credentials (email, password)

    Returns:
        Access token and expiry info
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
        token, expires_in = repo.create_access_token(user.id, user.email)

        logger.info(f"User logged in: {data.email}")

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": expires_in,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="登入失敗")
