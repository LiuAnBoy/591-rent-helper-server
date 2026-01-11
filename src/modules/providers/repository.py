"""User Provider Repository for database operations."""

from typing import Optional

from asyncpg import Pool
from loguru import logger

from src.modules.providers.models import UserProvider

provider_log = logger.bind(module="Provider")


class UserProviderRepository:
    """Repository for user provider operations."""

    def __init__(self, pool: Pool):
        """
        Initialize repository with database pool.

        Args:
            pool: AsyncPG connection pool
        """
        self._pool = pool

    async def find_by_provider(
        self, provider: str, provider_id: str
    ) -> Optional[UserProvider]:
        """
        Find user provider by provider type and provider ID.

        Args:
            provider: Provider type (telegram, line, etc.)
            provider_id: Provider user ID

        Returns:
            UserProvider if found, None otherwise
        """
        query = """
        SELECT * FROM user_providers
        WHERE provider = $1 AND provider_id = $2
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, provider, provider_id)
            if row:
                return UserProvider(**dict(row))
            return None

    async def get_by_user(self, user_id: int) -> list[UserProvider]:
        """
        Get all providers for a user.

        Args:
            user_id: User ID

        Returns:
            List of UserProvider
        """
        query = """
        SELECT * FROM user_providers
        WHERE user_id = $1
        ORDER BY created_at
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, user_id)
            return [UserProvider(**dict(row)) for row in rows]

    async def create(
        self,
        user_id: int,
        provider: str,
        provider_id: str,
        provider_data: Optional[dict] = None,
        notify_enabled: bool = True,
    ) -> UserProvider:
        """
        Create a new user provider binding.

        Args:
            user_id: User ID
            provider: Provider type
            provider_id: Provider user ID
            provider_data: Extra provider data
            notify_enabled: Whether to enable notifications

        Returns:
            Created UserProvider
        """
        query = """
        INSERT INTO user_providers (user_id, provider, provider_id, provider_data, notify_enabled)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """
        import json

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                user_id,
                provider,
                provider_id,
                json.dumps(provider_data or {}),
                notify_enabled,
            )
            provider_log.info(f"Created provider binding: {provider}:{provider_id} -> user {user_id}")
            return UserProvider(**dict(row))

    async def update_notify_enabled(
        self, user_id: int, provider: str, enabled: bool
    ) -> Optional[UserProvider]:
        """
        Update notification enabled status.

        Args:
            user_id: User ID
            provider: Provider type
            enabled: Whether to enable notifications

        Returns:
            Updated UserProvider if found
        """
        query = """
        UPDATE user_providers
        SET notify_enabled = $3, updated_at = NOW()
        WHERE user_id = $1 AND provider = $2
        RETURNING *
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id, provider, enabled)
            if row:
                provider_log.info(f"Updated notify_enabled for user {user_id} provider {provider}: {enabled}")
                return UserProvider(**dict(row))
            return None

    async def update_provider_data(
        self, user_id: int, provider: str, provider_data: dict
    ) -> Optional[UserProvider]:
        """
        Update provider data.

        Args:
            user_id: User ID
            provider: Provider type
            provider_data: New provider data

        Returns:
            Updated UserProvider if found
        """
        import json

        query = """
        UPDATE user_providers
        SET provider_data = $3, updated_at = NOW()
        WHERE user_id = $1 AND provider = $2
        RETURNING *
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id, provider, json.dumps(provider_data))
            if row:
                return UserProvider(**dict(row))
            return None

    async def delete(self, user_id: int, provider: str) -> bool:
        """
        Delete a user provider binding.

        Args:
            user_id: User ID
            provider: Provider type

        Returns:
            True if deleted, False if not found
        """
        query = """
        DELETE FROM user_providers
        WHERE user_id = $1 AND provider = $2
        RETURNING id
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id, provider)
            if row:
                provider_log.info(f"Deleted provider binding: user {user_id} provider {provider}")
                return True
            return False

    async def get_users_by_provider(
        self, provider: str, notify_enabled: bool = True
    ) -> list[UserProvider]:
        """
        Get all users with a specific provider.

        Args:
            provider: Provider type
            notify_enabled: Filter by notification status

        Returns:
            List of UserProvider
        """
        query = """
        SELECT * FROM user_providers
        WHERE provider = $1 AND notify_enabled = $2
        ORDER BY created_at
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, provider, notify_enabled)
            return [UserProvider(**dict(row)) for row in rows]
