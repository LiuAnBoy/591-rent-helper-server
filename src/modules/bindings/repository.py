"""
Notification Binding Repository.

Database operations for notification bindings (Telegram, Line, etc.)
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from asyncpg import Pool
from loguru import logger

from src.modules.bindings.models import NotificationBinding


class BindingRepository:
    """Repository for notification binding database operations."""

    BIND_CODE_LENGTH = 10
    BIND_CODE_EXPIRY_MINUTES = 10

    def __init__(self, pool: Pool):
        """
        Initialize repository with database connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool

    @staticmethod
    def generate_bind_code() -> str:
        """
        Generate a 10-character alphanumeric bind code.

        Returns:
            Random alphanumeric string (uppercase letters and digits)
        """
        alphabet = string.ascii_uppercase + string.digits
        return "".join(
            secrets.choice(alphabet) for _ in range(BindingRepository.BIND_CODE_LENGTH)
        )

    async def create_bind_code(self, user_id: int, service: str) -> str:
        """
        Create or update a bind code for a user.

        If binding already exists, updates the bind code.
        If not, creates a new binding record.

        Args:
            user_id: User ID
            service: Service type (telegram, line, etc.)

        Returns:
            Generated bind code
        """
        code = self.generate_bind_code()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.BIND_CODE_EXPIRY_MINUTES
        )

        query = """
        INSERT INTO notification_bindings (
            user_id, service, bind_code, bind_code_expires_at
        ) VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, service) DO UPDATE SET
            bind_code = $3,
            bind_code_expires_at = $4,
            updated_at = NOW()
        RETURNING *
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id, service, code, expires_at)
            logger.info(
                f"Generated bind code for user {user_id} service {service}: {code}"
            )
            return code

    async def verify_bind_code(
        self, service: str, code: str, service_id: str
    ) -> Optional[int]:
        """
        Verify a bind code and complete the binding.

        Args:
            service: Service type (telegram, line, etc.)
            code: Bind code to verify
            service_id: Service user ID (e.g., chat_id)

        Returns:
            user_id if successful, None if code invalid or expired
        """
        # Find binding with matching code
        query = """
        SELECT * FROM notification_bindings
        WHERE service = $1
          AND bind_code = $2
          AND bind_code_expires_at > NOW()
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, service, code)

            if not row:
                logger.warning(f"Invalid or expired bind code: {code}")
                return None

            user_id = row["user_id"]

            # Check if service_id is already bound to another user
            existing = await conn.fetchrow(
                """
                SELECT user_id FROM notification_bindings
                WHERE service = $1 AND service_id = $2 AND user_id != $3
                """,
                service,
                service_id,
                user_id,
            )

            if existing:
                logger.warning(
                    f"Service ID {service_id} already bound to user {existing['user_id']}"
                )
                return None

            # Complete the binding
            update_query = """
            UPDATE notification_bindings
            SET service_id = $1,
                bind_code = NULL,
                bind_code_expires_at = NULL,
                updated_at = NOW()
            WHERE user_id = $2 AND service = $3
            RETURNING *
            """

            await conn.fetchrow(update_query, service_id, user_id, service)
            logger.info(
                f"Binding completed: user {user_id} -> {service}:{service_id}"
            )
            return user_id

    async def get_binding_by_user(
        self, user_id: int, service: str
    ) -> Optional[NotificationBinding]:
        """
        Get binding by user ID and service.

        Args:
            user_id: User ID
            service: Service type (telegram, line, etc.)

        Returns:
            NotificationBinding or None if not found
        """
        query = """
        SELECT * FROM notification_bindings
        WHERE user_id = $1 AND service = $2
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id, service)
            if row:
                return NotificationBinding(**dict(row))
            return None

    async def get_binding_by_service_id(
        self, service: str, service_id: str
    ) -> Optional[NotificationBinding]:
        """
        Get binding by service ID (e.g., chat_id).

        Args:
            service: Service type (telegram, line, etc.)
            service_id: Service user ID

        Returns:
            NotificationBinding or None if not found
        """
        query = """
        SELECT * FROM notification_bindings
        WHERE service = $1 AND service_id = $2
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, service, service_id)
            if row:
                return NotificationBinding(**dict(row))
            return None

    async def get_bindings_by_user(self, user_id: int) -> list[NotificationBinding]:
        """
        Get all bindings for a user.

        Args:
            user_id: User ID

        Returns:
            List of NotificationBinding objects
        """
        query = """
        SELECT * FROM notification_bindings
        WHERE user_id = $1
        ORDER BY service
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, user_id)
            return [NotificationBinding(**dict(row)) for row in rows]

    async def delete_binding(self, user_id: int, service: str) -> bool:
        """
        Delete a binding.

        Args:
            user_id: User ID
            service: Service type

        Returns:
            True if deleted, False if not found
        """
        query = """
        DELETE FROM notification_bindings
        WHERE user_id = $1 AND service = $2
        RETURNING id
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, service)
            if result:
                logger.info(f"Deleted binding: user {user_id} service {service}")
                return True
            return False

    async def set_enabled(self, user_id: int, service: str, enabled: bool) -> bool:
        """
        Enable or disable a binding.

        Args:
            user_id: User ID
            service: Service type
            enabled: Enable or disable

        Returns:
            True if updated, False if not found
        """
        query = """
        UPDATE notification_bindings
        SET enabled = $3, updated_at = NOW()
        WHERE user_id = $1 AND service = $2
        RETURNING id
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id, service, enabled)
            return result is not None

    async def get_enabled_bindings_by_user_ids(
        self, user_ids: list[int], service: str
    ) -> dict[int, str]:
        """
        Get enabled bindings for multiple users.

        Args:
            user_ids: List of user IDs
            service: Service type

        Returns:
            Dict mapping user_id to service_id
        """
        if not user_ids:
            return {}

        query = """
        SELECT user_id, service_id FROM notification_bindings
        WHERE user_id = ANY($1)
          AND service = $2
          AND service_id IS NOT NULL
          AND enabled = TRUE
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, user_ids, service)
            return {row["user_id"]: row["service_id"] for row in rows}
