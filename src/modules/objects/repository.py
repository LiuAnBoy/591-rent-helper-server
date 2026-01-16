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

    async def save_batch(self, objects: list[DBReadyData]) -> int:
        """
        Batch save objects to database (UPSERT).

        For existing objects with has_detail=true, preserves detail fields.
        For new objects, inserts with provided has_detail value.

        Args:
            objects: List of DBReadyData dictionaries

        Returns:
            Number of newly inserted objects
        """
        if not objects:
            return 0

        query = """
        INSERT INTO objects (
            id, title, url, region, section, address,
            kind, kind_name, price, price_unit,
            layout, layout_str, shape, area,
            floor, floor_str, total_floor, bathroom, other, options,
            fitment, tags,
            surrounding_type, surrounding_desc, surrounding_distance,
            is_rooftop, gender, pet_allowed, has_detail
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
            $21, $22, $23, $24, $25, $26, $27, $28, $29
        )
        ON CONFLICT (id) DO UPDATE SET
            last_seen_at = NOW(),
            updated_at = NOW(),
            -- Only update detail fields if new data has_detail=true and existing has_detail=false
            floor = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.floor ELSE objects.floor END,
            floor_str = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.floor_str ELSE objects.floor_str END,
            total_floor = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.total_floor ELSE objects.total_floor END,
            is_rooftop = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.is_rooftop ELSE objects.is_rooftop END,
            layout = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.layout ELSE objects.layout END,
            layout_str = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.layout_str ELSE objects.layout_str END,
            bathroom = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.bathroom ELSE objects.bathroom END,
            area = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.area ELSE objects.area END,
            shape = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.shape ELSE objects.shape END,
            fitment = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.fitment ELSE objects.fitment END,
            gender = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.gender ELSE objects.gender END,
            pet_allowed = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.pet_allowed ELSE objects.pet_allowed END,
            options = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.options ELSE objects.options END,
            other = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.other ELSE objects.other END,
            surrounding_type = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.surrounding_type ELSE objects.surrounding_type END,
            surrounding_desc = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.surrounding_desc ELSE objects.surrounding_desc END,
            surrounding_distance = CASE WHEN EXCLUDED.has_detail AND NOT objects.has_detail THEN EXCLUDED.surrounding_distance ELSE objects.surrounding_distance END,
            has_detail = CASE WHEN EXCLUDED.has_detail THEN TRUE ELSE objects.has_detail END
        RETURNING (xmax = 0) AS inserted
        """

        inserted_count = 0
        async with self._pool.acquire() as conn:
            for data in objects:
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
                    data["has_detail"],  # $29
                )
                if result["inserted"]:
                    inserted_count += 1

        objects_log.info(f"Batch saved {len(objects)} objects, {inserted_count} new")
        return inserted_count

    async def update_with_detail(
        self, object_id: int, detail_data: DBReadyData
    ) -> bool:
        """
        Update object with detail data and set has_detail=true.

        Args:
            object_id: Object ID to update
            detail_data: DBReadyData containing detail fields

        Returns:
            True if updated, False if object not found
        """
        query = """
        UPDATE objects SET
            floor = $2,
            floor_str = $3,
            total_floor = $4,
            is_rooftop = $5,
            layout = $6,
            layout_str = $7,
            bathroom = $8,
            area = $9,
            shape = $10,
            fitment = $11,
            gender = $12,
            pet_allowed = $13,
            options = $14,
            other = $15,
            surrounding_type = $16,
            surrounding_desc = $17,
            surrounding_distance = $18,
            has_detail = true,
            updated_at = NOW()
        WHERE id = $1
        RETURNING id
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(
                query,
                object_id,  # $1
                detail_data["floor"],  # $2
                detail_data["floor_str"],  # $3
                detail_data["total_floor"],  # $4
                detail_data["is_rooftop"],  # $5
                detail_data["layout"],  # $6
                detail_data["layout_str"],  # $7
                detail_data["bathroom"],  # $8
                detail_data["area"],  # $9
                detail_data["shape"],  # $10
                detail_data["fitment"],  # $11
                detail_data["gender"],  # $12
                detail_data["pet_allowed"],  # $13
                detail_data["options"],  # $14
                detail_data["other"],  # $15
                detail_data["surrounding_type"],  # $16
                detail_data["surrounding_desc"],  # $17
                detail_data["surrounding_distance"],  # $18
            )
            if result:
                objects_log.debug(f"Updated object {object_id} with detail")
                return True
            return False

    async def update_batch_with_detail(self, objects: list[DBReadyData]) -> int:
        """
        Batch update objects with detail data.

        Args:
            objects: List of DBReadyData dictionaries with detail

        Returns:
            Number of objects updated
        """
        if not objects:
            return 0

        updated = 0
        for obj in objects:
            if await self.update_with_detail(obj["id"], obj):
                updated += 1

        objects_log.info(f"Batch updated {updated} objects with detail")
        return updated
