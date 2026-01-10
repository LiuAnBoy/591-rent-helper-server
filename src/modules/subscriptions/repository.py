"""
Subscription Repository.

Data access layer for subscription operations.
"""

from typing import Optional

from asyncpg import Pool


class SubscriptionRepository:
    """Repository for subscription database operations."""

    def __init__(self, pool: Pool):
        """
        Initialize repository with database connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool

    async def create(self, user_id: int, data: dict) -> dict:
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
            features, options, fitment,
            exclude_rooftop, gender, pet_required
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9,
            $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
        )
        RETURNING *
        """
        async with self._pool.acquire() as conn:
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
                data.get("features"),
                data.get("options"),
                data.get("fitment"),
                data.get("exclude_rooftop", False),
                data.get("gender"),
                data.get("pet_required", False),
            )
            return dict(row)

    async def get_by_id(self, subscription_id: int) -> Optional[dict]:
        """
        Get subscription by ID.

        Args:
            subscription_id: Subscription ID

        Returns:
            Subscription record or None if not found
        """
        query = "SELECT * FROM subscriptions WHERE id = $1"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, subscription_id)
            return dict(row) if row else None

    async def get_by_user(
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

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, user_id)
            return [dict(row) for row in rows]

    async def update(
        self, subscription_id: int, data: dict
    ) -> Optional[dict]:
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
            return await self.get_by_id(subscription_id)

        values.append(subscription_id)
        query = f"""
        UPDATE subscriptions
        SET {", ".join(fields)}, updated_at = NOW()
        WHERE id = ${idx}
        RETURNING *
        """

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *values)
            return dict(row) if row else None

    async def delete(self, subscription_id: int) -> bool:
        """
        Delete a subscription.

        Args:
            subscription_id: Subscription ID

        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM subscriptions WHERE id = $1 RETURNING id"
        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, subscription_id)
            return result is not None

    async def count_by_user(self, user_id: int) -> int:
        """
        Count subscriptions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of subscriptions
        """
        query = "SELECT COUNT(*) FROM subscriptions WHERE user_id = $1"
        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, user_id)
            return result["count"]

    async def get_all_enabled(self) -> list[dict]:
        """
        Get all enabled subscriptions with notification binding info.

        Returns:
            List of all enabled subscription records with service and service_id
        """
        query = """
        SELECT 
            s.*,
            nb.service,
            nb.service_id
        FROM subscriptions s
        LEFT JOIN notification_bindings nb 
            ON s.user_id = nb.user_id AND nb.enabled = TRUE
        WHERE s.enabled = TRUE
        ORDER BY s.region, s.created_at DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]

    async def get_active_regions(self) -> list[int]:
        """
        Get all unique regions that have enabled subscriptions.

        Returns:
            List of unique region codes
        """
        query = "SELECT DISTINCT region FROM subscriptions WHERE enabled = TRUE ORDER BY region"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [row["region"] for row in rows]

    async def get_by_region(self, region: int, enabled_only: bool = True) -> list[dict]:
        """
        Get all subscriptions for a specific region.

        Args:
            region: Region code
            enabled_only: Only return enabled subscriptions

        Returns:
            List of subscription records
        """
        if enabled_only:
            query = "SELECT * FROM subscriptions WHERE region = $1 AND enabled = TRUE ORDER BY created_at DESC"
        else:
            query = "SELECT * FROM subscriptions WHERE region = $1 ORDER BY created_at DESC"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, region)
            return [dict(row) for row in rows]
