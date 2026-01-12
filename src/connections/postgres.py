"""
PostgreSQL Connection Module.

Manages PostgreSQL connection pool and database operations.
"""

from typing import Optional

import asyncpg
from loguru import logger

from config.settings import get_settings
from src.modules.objects import RentalObject
from src.utils.mappings import convert_other_to_codes

pg_log = logger.bind(module="Postgres")


class PostgresConnection:
    """PostgreSQL connection manager."""

    def __init__(self):
        """Initialize PostgreSQL connection."""
        self.settings = get_settings().postgres
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Connect to PostgreSQL."""
        pg_log.info(f"Connecting to PostgreSQL at {self.settings.host}:{self.settings.port}")
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

    async def save_object(self, obj: RentalObject) -> bool:
        """
        Save a single object to database.

        Args:
            obj: RentalObject object to save

        Returns:
            True if inserted (new), False if already exists
        """
        query = """
        INSERT INTO objects (
            id, title, url, region, section, address,
            kind, kind_name, price, price_unit, price_per,
            layout, layout_str, shape, area,
            floor, floor_str, total_floor, bathroom, other, options,
            fitment, tags,
            surrounding_type, surrounding_desc, surrounding_distance,
            is_rooftop, gender, pet_allowed
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
            $21, $22, $23, $24, $25, $26, $27, $28, $29
        )
        ON CONFLICT (id) DO UPDATE SET
            last_seen_at = NOW(),
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
        """

        async with self.pool.acquire() as conn:
            # Parse price to integer
            price_int = int(obj.price.replace(",", "")) if obj.price else 0

            # Extract layout number from string (e.g., "2房1廳" -> 2)
            layout_num = None
            if obj.layout_str:
                import re
                match = re.search(r"(\d+)房", obj.layout_str)
                if match:
                    layout_num = int(match.group(1))

            # Parse floor info from floor_name
            from src.utils.parsers import parse_floor
            floor_str = obj.floor_name if hasattr(obj, "floor_name") else None
            floor, total_floor, is_rooftop = parse_floor(floor_str)

            result = await conn.fetchrow(
                query,
                obj.id,                                                    # $1
                obj.title,                                                 # $2
                obj.url,                                                   # $3
                obj.region,                                                # $4
                obj.section,                                               # $5
                obj.address,                                               # $6
                obj.kind,                                                  # $7
                obj.kind_name,                                             # $8
                price_int,                                                 # $9
                obj.price_unit,                                            # $10
                obj.price_per,                                             # $11
                layout_num,                                                # $12
                obj.layout_str,                                            # $13
                None,                                                      # $14 shape
                obj.area,                                                  # $15
                floor,                                                     # $16 floor
                floor_str,                                                 # $17 floor_str
                total_floor,                                               # $18 total_floor
                None,                                                      # $19 bathroom
                convert_other_to_codes(obj.tags or []),                    # $20 other
                [],                                                        # $21 options
                None,                                                      # $22 fitment
                obj.tags or [],                                            # $23 tags
                obj.surrounding.type if obj.surrounding else None,         # $24
                obj.surrounding.desc if obj.surrounding else None,         # $25
                obj.surrounding.distance if obj.surrounding else None,     # $26
                is_rooftop,                                                # $27
                "all",                                                     # $28 gender
                None,                                                      # $29 pet_allowed
            )
            return result["inserted"]

    async def save_objects(self, objects: list[RentalObject]) -> tuple[int, int]:
        """
        Save multiple objects to database.

        Args:
            objects: List of RentalObject objects

        Returns:
            Tuple of (new_count, updated_count)
        """
        new_count = 0
        updated_count = 0

        for obj in objects:
            is_new = await self.save_object(obj)
            if is_new:
                new_count += 1
            else:
                updated_count += 1

        pg_log.info(f"Saved objects: {new_count} new, {updated_count} updated")
        return new_count, updated_count

    async def get_object(self, object_id: int) -> Optional[dict]:
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

    # ========== Subscription Matching ==========

    async def find_matching_subscriptions(self, obj: RentalObject) -> list[dict]:
        """
        Find all subscriptions that match an object.

        Args:
            obj: RentalObject object to match against

        Returns:
            List of matching subscriptions with notification binding info
        """
        # Parse object values
        price_int = int(obj.price.replace(",", "")) if obj.price else 0

        # Extract layout number
        layout_num = None
        if obj.layout_str:
            import re
            match = re.search(r"(\d+)房", obj.layout_str)
            if match:
                layout_num = int(match.group(1))

        query = """
        SELECT
            s.*,
            up.provider AS service,
            up.provider_id AS service_id
        FROM subscriptions s
        JOIN user_providers up ON s.user_id = up.user_id
        WHERE s.enabled = TRUE
          AND up.notify_enabled = TRUE
          AND up.provider_id IS NOT NULL
          AND s.region = $1

          -- 區域 (NULL = 不限)
          AND (s.section IS NULL OR $2 = ANY(s.section))

          -- 類型 (NULL = 不限)
          AND (s.kind IS NULL OR $3 = ANY(s.kind))

          -- 租金範圍
          AND (s.price_min IS NULL OR $4 >= s.price_min)
          AND (s.price_max IS NULL OR $4 <= s.price_max)

          -- 格局 (NULL = 不限)
          AND (s.layout IS NULL OR $5 = ANY(s.layout))

          -- 坪數範圍
          AND (s.area_min IS NULL OR $6 >= s.area_min)
          AND (s.area_max IS NULL OR $6 <= s.area_max)

          -- 特色 (陣列有交集即可)
          AND (s.other IS NULL OR s.other && $7::TEXT[])

          -- 排除已推播
          AND NOT EXISTS (
              SELECT 1 FROM notified_objects no
              WHERE no.subscription_id = s.id AND no.object_id = $8
          )
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                obj.region,
                obj.section,
                obj.kind,
                price_int,
                layout_num,
                obj.area,
                obj.tags or [],
                obj.id,
            )
            return [dict(row) for row in rows]

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

    async def start_crawler_run(self, region: int, section: Optional[int] = None) -> int:
        """Record start of a crawler run. Returns run ID."""
        query = """
        INSERT INTO crawler_runs (region, section, status)
        VALUES ($1, $2, 'running')
        RETURNING id
        """
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(query, region, section)
            return result["id"]

    async def finish_crawler_run(
        self,
        run_id: int,
        status: str,
        total_fetched: int,
        new_objects: int,
        error_message: Optional[str] = None,
    ) -> None:
        """Record finish of a crawler run."""
        query = """
        UPDATE crawler_runs
        SET finished_at = NOW(),
            status = $2,
            total_fetched = $3,
            new_listings = $4,
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

    async def get_subscription(self, subscription_id: int) -> Optional[dict]:
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
_postgres: Optional[PostgresConnection] = None


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
