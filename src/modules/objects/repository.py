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
            is_rooftop, gender, pet_allowed, raw_data
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
            $21, $22, $23, $24, $25, $26, $27, $28, $29, $30
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
                floor,                                                     # $16 floor (INTEGER)
                floor_str,                                                 # $17 floor_str
                total_floor,                                               # $18 total_floor
                None,                                                      # $19 bathroom
                convert_other_to_codes(obj.tags or []),                     # $20 other
                [],                                                        # $21 options
                None,                                                      # $22 fitment
                obj.tags or [],                                            # $23 tags
                obj.surrounding.type if obj.surrounding else None,         # $24
                obj.surrounding.desc if obj.surrounding else None,         # $25
                obj.surrounding.distance if obj.surrounding else None,     # $26
                is_rooftop,                                                # $27
                "all",                                                     # $28 gender
                None,                                                      # $29 pet_allowed
                None,                                                      # $30 raw_data
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

    async def update_from_detail(self, object_id: int, detail: dict) -> bool:
        """
        Update object with detail page data.

        Only updates fields that are available from detail page:
            - gender: "boy" | "girl" | "all"
            - pet_allowed: True | False | None
            - shape: int | None (1=公寓, 2=電梯, 3=透天, 4=別墅)
            - options: list[str] (equipment codes)
            - fitment: int | None (99=新裝潢, 3=中檔, 4=高檔)
            - section: int | None (only if not already set)
            - kind: int | None (only if not already set)
            - floor_str: str | None (e.g., "5F/7F")
            - floor: int | None (current floor)
            - total_floor: int | None (total floors)
            - is_rooftop: bool (rooftop addition)
            - layout_str: str | None (e.g., "3房2廳2衛")
            - layout: int | None (room count from layout_str)
            - bathroom: int | None (bathroom count from layout_str)

        Args:
            object_id: Object ID to update
            detail: Detail data from detail fetcher

        Returns:
            True if updated, False if object not found
        """
        # Parse layout and bathroom from layout_str (e.g., "3房2廳2衛" or "開放格局")
        layout_str = detail.get("layout_str")
        layout_num = None
        bathroom = None
        if layout_str:
            if layout_str == "開放格局":
                layout_num = 0
            else:
                room_match = re.search(r"(\d+)房", layout_str)
                if room_match:
                    layout_num = int(room_match.group(1))
            bath_match = re.search(r"(\d+)衛", layout_str)
            if bath_match:
                bathroom = int(bath_match.group(1))

        # Convert tags to other codes
        tags = detail.get("tags", [])
        other_codes = convert_other_to_codes(tags) if tags else []

        query = """
        UPDATE objects SET
            gender = $2,
            pet_allowed = $3,
            shape = $4,
            options = $5,
            fitment = $6,
            section = COALESCE(section, $7),
            kind = COALESCE(kind, $8),
            floor_str = COALESCE($9, floor_str),
            floor = COALESCE($10, floor),
            total_floor = COALESCE($11, total_floor),
            is_rooftop = COALESCE($12, is_rooftop),
            layout_str = COALESCE($13, layout_str),
            layout = COALESCE($14, layout),
            bathroom = COALESCE($15, bathroom),
            tags = $16,
            other = $17,
            updated_at = NOW()
        WHERE id = $1
        RETURNING id
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(
                query,
                object_id,
                detail.get("gender", "all"),
                detail.get("pet_allowed"),
                detail.get("shape"),
                detail.get("options", []),
                detail.get("fitment"),
                detail.get("section"),
                detail.get("kind"),
                detail.get("floor_str"),
                detail.get("floor"),
                detail.get("total_floor"),
                detail.get("is_rooftop"),
                layout_str,
                layout_num,
                bathroom,
                tags,
                other_codes,
            )
            return result is not None

    async def update_from_details_batch(
        self,
        details: dict[int, dict],
    ) -> tuple[int, int]:
        """
        Update multiple objects with detail page data.

        Args:
            details: Dict mapping object_id to detail data

        Returns:
            Tuple of (updated_count, not_found_count)
        """
        updated_count = 0
        not_found_count = 0

        for object_id, detail in details.items():
            if await self.update_from_detail(object_id, detail):
                updated_count += 1
            else:
                not_found_count += 1

        objects_log.info(
            f"Updated from detail: {updated_count} updated, "
            f"{not_found_count} not found"
        )
        return updated_count, not_found_count
