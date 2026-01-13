"""
Object Repository.

Data access layer for rental object operations.
"""

from asyncpg import Pool
from loguru import logger

from src.utils import DBReadyData

objects_log = logger.bind(module="Objects")


class ObjectRepository:
    """Repository for object database operations."""

    def __init__(self, pool: Pool):
        """
        Initialize repository with database connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool

    async def save(self, data: DBReadyData) -> bool:
        """
        Save DBReadyData to database.

        Args:
            data: DBReadyData with all fields already transformed

        Returns:
            True if inserted (new), False if already exists
        """
        query = """
        INSERT INTO objects (
            id, title, url, region, section, address,
            kind, kind_name, price, price_unit,
            layout, layout_str, shape, area,
            floor, floor_str, total_floor, bathroom, other, options,
            fitment, tags,
            surrounding_type, surrounding_desc, surrounding_distance,
            is_rooftop, gender, pet_allowed
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
            $21, $22, $23, $24, $25, $26, $27, $28
        )
        ON CONFLICT (id) DO UPDATE SET
            last_seen_at = NOW(),
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(
                query,
                data["id"],  # $1
                data["title"],  # $2
                data["url"],  # $3
                data["region"],  # $4
                data["section"],  # $5
                data["address"],  # $6
                data["kind"],  # $7
                data["kind_name"],  # $8
                data["price"],  # $9
                data["price_unit"],  # $10
                data["layout"],  # $11
                data["layout_str"],  # $12
                data["shape"],  # $13
                data["area"],  # $14
                data["floor"],  # $15
                data["floor_str"],  # $16
                data["total_floor"],  # $17
                data["bathroom"],  # $18
                data["other"],  # $19
                data["options"],  # $20
                data["fitment"],  # $21
                data["tags"],  # $22
                data["surrounding_type"],  # $23
                data["surrounding_desc"],  # $24
                data["surrounding_distance"],  # $25
                data["is_rooftop"],  # $26
                data["gender"],  # $27
                data["pet_allowed"],  # $28
            )
            return result["inserted"]

    async def get_by_id(self, object_id: int) -> dict | None:
        """
        Get object by ID.

        Args:
            object_id: Object ID

        Returns:
            Object record or None if not found
        """
        query = "SELECT * FROM objects WHERE id = $1"
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, object_id)
            return dict(row) if row else None

    async def exists(self, object_id: int) -> bool:
        """
        Check if object exists in database.

        Args:
            object_id: Object ID

        Returns:
            True if exists, False otherwise
        """
        query = "SELECT 1 FROM objects WHERE id = $1"
        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(query, object_id)
            return result is not None

    async def get_latest_by_region(self, region: int, limit: int = 10) -> list[dict]:
        """
        Get latest objects for a specific region.

        Args:
            region: Region code (1=台北, 3=新北, etc.)
            limit: Maximum number of objects to return

        Returns:
            List of object dictionaries, ordered by created_at DESC
        """
        query = """
        SELECT * FROM objects
        WHERE region = $1
        ORDER BY created_at DESC
        LIMIT $2
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, region, limit)
            return [dict(row) for row in rows]
