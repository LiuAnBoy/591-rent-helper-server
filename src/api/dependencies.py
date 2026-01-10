"""
API Dependencies.

Shared dependencies for API routes (authentication, etc.)
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Header
from loguru import logger

from src.connections.postgres import get_postgres
from src.modules.users import User, UserRepository


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        authorization: Authorization header (Bearer token)

    Returns:
        Authenticated User

    Raises:
        HTTPException: If not authenticated
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="未提供認證資訊",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="認證格式錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Get repository and decode token
    postgres = await get_postgres()
    repo = UserRepository(postgres.pool)

    payload = repo.decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="認證已過期或無效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user_id = int(payload.get("sub", 0))
    user = await repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="用戶不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.enabled:
        raise HTTPException(
            status_code=403,
            detail="帳號已被停用"
        )

    return user


# Type alias for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
