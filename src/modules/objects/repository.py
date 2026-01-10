"""
Object Repository.

Data access layer for object (listing) operations.
"""

import re
from typing import Optional

from asyncpg import Pool
from loguru import logger

from src.modules.objects.models import RentalObject


class ObjectRepository:
    """Repository for object database operations."""

    def __init__(self, pool: Pool):
        """
        Initialize repository with database connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self._pool = pool

    async def save(self, obj: RentalObject) -> bool:
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
            floor, floor_str, bathroom, features, options,
            fitment, tags,
            surrounding_type, surrounding_desc, surrounding_distance,
            is_rooftop, gender, pet_allowed, raw_data
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

        async with self._pool.acquire() as conn:
            # Parse price to integer
            price_int = int(obj.price.replace(",", "")) if obj.price else 0

            # Extract layout number from string (e.g., "2房1廳" -> 2)
            layout_num = None
            if obj.layout_str:
                match = re.search(r"(\d+)房", obj.layout_str)
                if match:
                    layout_num = int(match.group(1))

            # Detect rooftop from floor_name
            is_rooftop = False
            floor_str = obj.floor_name if hasattr(obj, "floor_name") else None
            if floor_str and "頂" in floor_str and "加蓋" in floor_str:
                is_rooftop = True

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
                None,                                                      # $16 floor
                floor_str,                                                 # $17
                None,                                                      # $18 bathroom
                obj.tags or [],                                            # $19 features
                [],                                                        # $20 options
                None,                                                      # $21 fitment
                obj.tags or [],                                            # $22 tags
                obj.surrounding.type if obj.surrounding else None,         # $23
                obj.surrounding.desc if obj.surrounding else None,         # $24
                obj.surrounding.distance if obj.surrounding else None,     # $25
                is_rooftop,                                                # $26
                "all",                                                     # $27 gender
                None,                                                      # $28 pet_allowed
                None,                                                      # $29 raw_data
            )
            return result["inserted"]

    async def save_many(self, objects: list[RentalObject]) -> tuple[int, int]:
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
            is_new = await self.save(obj)
            if is_new:
                new_count += 1
            else:
                updated_count += 1

        logger.info(f"Saved objects: {new_count} new, {updated_count} updated")
        return new_count, updated_count

    async def get_by_id(self, object_id: int) -> Optional[dict]:
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
