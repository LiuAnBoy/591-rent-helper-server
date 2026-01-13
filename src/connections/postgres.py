"""
PostgreSQL Connection Module.

Manages PostgreSQL connection pool and database operations.
"""

import asyncpg
from loguru import logger

from config.settings import get_settings

pg_log = logger.bind(module="Postgres")


class PostgresConnection:
    """PostgreSQL connection manager."""

    def __init__(self):
        """Initialize PostgreSQL connection."""
        self.settings = get_settings().postgres
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Connect to PostgreSQL."""
        pg_log.info(
            f"Connecting to PostgreSQL at {self.settings.host}:{self.settings.port}"
        )
        self._pool = await asyncpg.create_pool(
            host=self.settings.host,
            port=self.settings.port,
            user=self.settings.user,
            password=self.settings.password,
            database=self.settings.database,
            min_size=2,
            max_size=self.settings.pool_max,
        )
        pg_log.info("PostgreSQL connected successfully")

    async def close(self) -> None:
        """Close PostgreSQL connection pool."""
        if self._pool:
            await self._pool.close()
            pg_log.info("PostgreSQL connection closed")

    @property
    def pool(self) -> asyncpg.Pool:
        """Get connection pool."""
        if not self._pool:
            raise RuntimeError("PostgreSQL not connected. Call connect() first.")
        return self._pool

    # ========== Object Operations ==========

    async def get_object(self, object_id: int) -> dict | None:
        """Get object by ID."""
        query = "SELECT * FROM objects WHERE id = $1"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, object_id)

    async def object_exists(self, object_id: int) -> bool:
        """Check if object exists in database."""
        query = "SELECT 1 FROM objects WHERE id = $1"
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, object_id)
            return result is not None

    # ========== Notified Objects ==========

    async def is_notified(self, subscription_id: int, object_id: int) -> bool:
        """Check if an object has been notified for a subscription."""
        query = """
        SELECT 1 FROM notified_objects
        WHERE subscription_id = $1 AND object_id = $2
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, subscription_id, object_id)
            return result is not None

    async def mark_notified(self, subscription_id: int, object_id: int) -> None:
        """Mark an object as notified for a subscription."""
        query = """
        INSERT INTO notified_objects (subscription_id, object_id)
        VALUES ($1, $2)
        ON CONFLICT (subscription_id, object_id) DO NOTHING
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, subscription_id, object_id)

    # ========== Crawler Runs ==========

    async def start_crawler_run(self, region: int) -> int:
        """Record start of a crawler run. Returns run ID."""
        query = """
        INSERT INTO crawler_runs (region, status)
        VALUES ($1, 'running')
        RETURNING id
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, region)
            return result["id"]

    async def finish_crawler_run(
        self,
        run_id: int,
        status: str,
        total_fetched: int,
        new_objects: int,
        error_message: str | None = None,
    ) -> None:
        """Record finish of a crawler run."""
        query = """
        UPDATE crawler_runs
        SET finished_at = NOW(),
            status = $2,
            total_fetched = $3,
            new_objects = $4,
            error_message = $5
        WHERE id = $1
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                query, run_id, status, total_fetched, new_objects, error_message
            )

    # ========== Subscription CRUD ==========

    async def create_subscription(self, user_id: int, data: dict) -> dict:
        """
        Create a new subscription.

        Args:
            user_id: User ID
            data: Subscription data

        Returns:
            Created subscription record
        """
        query = """
        INSERT INTO subscriptions (
            user_id, name, region, section, kind,
            price_min, price_max, layout, shape,
            area_min, area_max, floor, bathroom,
            other, options, fitment, notice,
            keywords, exclude_keywords
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9,
            $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
        )
        RETURNING *
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                user_id,
                data["name"],
                data["region"],
                data.get("section"),
                data.get("kind"),
                data.get("price_min"),
                data.get("price_max"),
                data.get("layout"),
                data.get("shape"),
                data.get("area_min"),
                data.get("area_max"),
                data.get("floor"),
                data.get("bathroom"),
                data.get("other"),
                data.get("options"),
                data.get("fitment"),
                data.get("notice"),
                data.get("keywords"),
                data.get("exclude_keywords"),
            )
            return dict(row)

    async def get_subscription(self, subscription_id: int) -> dict | None:
        """Get subscription by ID."""
        query = "SELECT * FROM subscriptions WHERE id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, subscription_id)
            return dict(row) if row else None

    async def get_subscriptions_by_user(
        self, user_id: int, enabled_only: bool = False
    ) -> list[dict]:
        """
        Get all subscriptions for a user.

        Args:
            user_id: User ID
            enabled_only: Only return enabled subscriptions

        Returns:
            List of subscription records
        """
        if enabled_only:
            query = "SELECT * FROM subscriptions WHERE user_id = $1 AND enabled = TRUE ORDER BY created_at DESC"
        else:
            query = "SELECT * FROM subscriptions WHERE user_id = $1 ORDER BY created_at DESC"

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, user_id)
            return [dict(row) for row in rows]

    async def update_subscription(
        self, subscription_id: int, data: dict
    ) -> dict | None:
        """
        Update a subscription.

        Args:
            subscription_id: Subscription ID
            data: Fields to update

        Returns:
            Updated subscription record or None if not found
        """
        # Build dynamic update query
        fields = []
        values = []
        idx = 1

        for key, value in data.items():
            if value is not None:
                fields.append(f"{key} = ${idx}")
                values.append(value)
                idx += 1

        if not fields:
            return await self.get_subscription(subscription_id)

        values.append(subscription_id)
        query = f"""
        UPDATE subscriptions
        SET {", ".join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        RETURNING *
        """

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
            return dict(row) if row else None

    async def delete_subscription(self, subscription_id: int) -> bool:
        """
        Delete a subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM subscriptions WHERE id = $1 RETURNING id"
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, subscription_id)
            return result is not None

    async def count_user_subscriptions(self, user_id: int) -> int:
        """Count subscriptions for a user."""
        query = "SELECT COUNT(*) FROM subscriptions WHERE user_id = $1"
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id)
            return result["count"]


# Singleton instance
_postgres: PostgresConnection | None = None


async def get_postgres() -> PostgresConnection:
    """Get PostgreSQL connection singleton."""
    global _postgres
    if _postgres is None:
        _postgres = PostgresConnection()
        await _postgres.connect()
    return _postgres


async def close_postgres() -> None:
    """Close PostgreSQL connection."""
    global _postgres
    if _postgres:
        await _postgres.close()
        _postgres = None
