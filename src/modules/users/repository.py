"""
User Repository.

Database operations for user management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from asyncpg import Pool
from loguru import logger

from config.settings import get_settings
from src.modules.users.models import User

users_log = logger.bind(module="Users")


class UserRepository:
    """Repository for user database operations."""

    def __init__(self, pool: Pool):
        """
        Initialize repository with database connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool
        self._settings = get_settings()

    def create_access_token(self, user_id: int, email: Optional[str], role: str) -> tuple[str, int]:
        """
        Create JWT access token.

        Args:
            user_id: User ID
            email: User email (optional)
            role: User role

        Returns:
            Tuple of (token, expires_in_seconds)
        """
        expires_in = 604800  # 7 days
        expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        payload = {
            "id": user_id,
            "email": email,
            "role": role,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }

        secret_key = self._settings.jwt_secret or "default_jwt_secret_change_me"
        token = jwt.encode(payload, secret_key, algorithm="HS256")

        return token, expires_in

    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode and verify JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload or None if invalid
        """
        try:
            secret_key = self._settings.jwt_secret or "default_jwt_secret_change_me"
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            users_log.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            users_log.warning(f"Invalid token: {e}")
            return None

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User or None if not found
        """
        query = "SELECT * FROM users WHERE id = $1"

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            if row:
                return User(**dict(row))
            return None

    async def get_role_limit(self, role: str) -> int:
        """
        Get max subscriptions limit for a role.

        Args:
            role: User role

        Returns:
            Max subscriptions allowed (-1 for unlimited)
        """
        query = "SELECT max_subscriptions FROM role_limits WHERE role = $1"

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, role)
            if row:
                return row["max_subscriptions"]
            return 3  # Default

    async def set_enabled(self, user_id: int, enabled: bool) -> bool:
        """
        Enable or disable user.

        Args:
            user_id: User ID
            enabled: Enable or disable

        Returns:
            True if updated
        """
        query = """
        UPDATE users SET enabled = $2, updated_at = NOW()
        WHERE id = $1
        RETURNING id
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, enabled)
            return result is not None

    async def create_from_provider(self, name: str) -> User:
        """
        Create a new user from provider login (without email/password).

        Args:
            name: Display name from provider

        Returns:
            Created User
        """
        query = """
        INSERT INTO users (name)
        VALUES ($1)
        RETURNING *
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, name)
            users_log.info(f"Created user from provider: {name}")
            return User(**dict(row))

    async def find_by_provider(self, provider: str, provider_id: str) -> Optional[User]:
        """
        Find user by provider type and provider ID.

        Args:
            provider: Provider type (telegram, line, etc.)
            provider_id: Provider user ID

        Returns:
            User if found, None otherwise
        """
        query = """
        SELECT u.* FROM users u
        JOIN user_providers up ON u.id = up.user_id
        WHERE up.provider = $1 AND up.provider_id = $2
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, provider, provider_id)
            if row:
                return User(**dict(row))
            return None

    async def update_name(self, user_id: int, name: str) -> bool:
        """
        Update user display name.

        Args:
            user_id: User ID
            name: New display name

        Returns:
            True if updated
        """
        query = """
        UPDATE users SET name = $2, updated_at = NOW()
        WHERE id = $1
        RETURNING id
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, name)
            return result is not None
