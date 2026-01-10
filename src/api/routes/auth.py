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
