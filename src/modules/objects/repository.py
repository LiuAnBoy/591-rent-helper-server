"""
Object Repository.

Data access layer for object (listing) operations.
"""

import re
from typing import Optional

from asyncpg import Pool
from loguru import logger

from src.modules.objects.models import RentalObject
from src.utils.mappings import convert_other_to_codes
from src.utils.parsers import parse_floor

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

        async with self._pool.acquire() as conn:
            # Parse price to integer
            price_int = int(obj.price.replace(",", "")) if obj.price else 0

            # Extract layout number from string (e.g., "2房1廳" -> 2, "開放格局" -> 0)
            layout_num = None
            if obj.layout_str:
                if obj.layout_str == "開放格局":
                    layout_num = 0
                else:
                    match = re.search(r"(\d+)房", obj.layout_str)
                    if match:
                        layout_num = int(match.group(1))

            # Parse floor info from floor_name
            floor_str = obj.floor_name if hasattr(obj, "floor_name") else None
            floor, total_floor, is_rooftop = parse_floor(floor_str)

            # Use object values (merged from detail) or fallback to parsed values
            final_floor = obj.floor if obj.floor is not None else floor
            final_total_floor = obj.total_floor if obj.total_floor is not None else total_floor
            final_is_rooftop = obj.is_rooftop if obj.is_rooftop else is_rooftop
            final_bathroom = obj.bathroom if obj.bathroom is not None else None

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
                obj.shape,                                                 # $14 shape (from detail)
                obj.area,                                                  # $15
                final_floor,                                               # $16 floor (INTEGER)
                floor_str,                                                 # $17 floor_str
                final_total_floor,                                         # $18 total_floor
                final_bathroom,                                            # $19 bathroom (from detail)
                convert_other_to_codes(obj.tags or []),                    # $20 other
                obj.options or [],                                         # $21 options (from detail)
                obj.fitment,                                               # $22 fitment (from detail)
                obj.tags or [],                                            # $23 tags
                obj.surrounding.type if obj.surrounding else None,         # $24
                obj.surrounding.desc if obj.surrounding else None,         # $25
                obj.surrounding.distance if obj.surrounding else None,     # $26
                final_is_rooftop,                                          # $27 is_rooftop
                obj.gender or "all",                                       # $28 gender (from detail)
                obj.pet_allowed,                                           # $29 pet_allowed (from detail)
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

        objects_log.info(f"Saved objects: {new_count} new, {updated_count} updated")
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
