"""
User Repository.

Database operations for user management.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from asyncpg import Pool
from loguru import logger

from config.settings import get_settings
from src.modules.users.models import User


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

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using SHA256 with salt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        # Simple SHA256 hash - consider using bcrypt for production
        salt = "591crawler_salt"
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password
            hashed: Hashed password from database

        Returns:
            True if password matches
        """
        return UserRepository.hash_password(password) == hashed

    def create_access_token(self, user_id: int, email: str) -> tuple[str, int]:
        """
        Create JWT access token.

        Args:
            user_id: User ID
            email: User email

        Returns:
            Tuple of (token, expires_in_seconds)
        """
        expires_in = 86400  # 24 hours
        expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        payload = {
            "sub": str(user_id),
            "email": email,
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
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    async def create(self, email: str, password: str) -> Optional[User]:
        """
        Create a new user.

        Args:
            email: User email
            password: Plain text password

        Returns:
            Created User or None if email exists
        """
        hashed_password = self.hash_password(password)

        query = """
        INSERT INTO users (email, password)
        VALUES ($1, $2)
        ON CONFLICT (email) DO NOTHING
        RETURNING *
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, email, hashed_password)
            if row:
                logger.info(f"Created user: {email}")
                return User(**dict(row))
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

    async def get_by_email(self, email: str) -> Optional[dict]:
        """
        Get user by email (includes password hash for authentication).

        Args:
            email: User email

        Returns:
            User dict with password or None if not found
        """
        query = "SELECT * FROM users WHERE email = $1"

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, email)
            if row:
                return dict(row)
            return None

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user with email and password.

        Args:
            email: User email
            password: Plain text password

        Returns:
            User if authenticated, None otherwise
        """
        user_data = await self.get_by_email(email)

        if not user_data:
            return None

        if not user_data.get("enabled", True):
            logger.warning(f"Disabled user attempted login: {email}")
            return None

        if not self.verify_password(password, user_data["password"]):
            return None

        # Return User without password
        return User(
            id=user_data["id"],
            email=user_data["email"],
            role=user_data["role"],
            enabled=user_data["enabled"],
            created_at=user_data["created_at"],
            updated_at=user_data["updated_at"],
        )

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

    async def update_password(self, user_id: int, new_password: str) -> bool:
        """
        Update user password.

        Args:
            user_id: User ID
            new_password: New plain text password

        Returns:
            True if updated
        """
        hashed = self.hash_password(new_password)
        query = """
        UPDATE users SET password = $2, updated_at = NOW()
        WHERE id = $1
        RETURNING id
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, hashed)
            return result is not None

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
