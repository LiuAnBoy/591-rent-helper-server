"""
Object Repository.

Data access layer for rental object operations.
"""

from asyncpg import Pool
from loguru import logger

from src.crawler.contract import DBReadyData

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
            source, source_id, title, url, region, section, address,
            kind, kind_name, price, price_unit,
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
        ON CONFLICT (source, source_id) DO UPDATE SET
            last_seen_at = NOW(),
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
        """

        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(
                query,
                data["source"],  # $1
                data["source_id"],  # $2
                data["title"],  # $3
                data["url"],  # $4
                data["region"],  # $5
                data["section"],  # $6
                data["address"],  # $7
                data["kind"],  # $8
                data["kind_name"],  # $9
                data["price"],  # $10
                data["price_unit"],  # $11
                data["layout"],  # $12
                data["layout_str"],  # $13
                data["shape"],  # $14
                data["area"],  # $15
                data["floor"],  # $16
                data["floor_str"],  # $17
                data["total_floor"],  # $18
                data["bathroom"],  # $19
                data["other"],  # $20
                data["options"],  # $21
                data["fitment"],  # $22
                data["tags"],  # $23
                data["surrounding_type"],  # $24
                data["surrounding_desc"],  # $25
                data["surrounding_distance"],  # $26
                data["is_rooftop"],  # $27
                data["gender"],  # $28
                data["pet_allowed"],  # $29
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
            source, source_id, title, url, region, section, address,
            kind, kind_name, price, price_unit,
            layout, layout_str, shape, area,
            floor, floor_str, total_floor, bathroom, other, options,
            fitment, tags,
            surrounding_type, surrounding_desc, surrounding_distance,
            is_rooftop, gender, pet_allowed, has_detail
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
            $21, $22, $23, $24, $25, $26, $27, $28, $29, $30
        )
        ON CONFLICT (source, source_id) DO UPDATE SET
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
        async with self._pool.acquire() as conn, conn.transaction():
            # Wrap the whole batch in one transaction: a single bad row (e.g. a
            # value overflow) rolls back the entire batch instead of leaving the
            # DB half-written and out of sync with the Redis seen set.
            for data in objects:
                result = await conn.fetchrow(
                    query,
                    data["source"],  # $1
                    data["source_id"],  # $2
                    data["title"],  # $3
                    data["url"],  # $4
                    data["region"],  # $5
                    data["section"],  # $6
                    data["address"],  # $7
                    data["kind"],  # $8
                    data["kind_name"],  # $9
                    data["price"],  # $10
                    data["price_unit"],  # $11
                    data["layout"],  # $12
                    data["layout_str"],  # $13
                    data["shape"],  # $14
                    data["area"],  # $15
                    data["floor"],  # $16
                    data["floor_str"],  # $17
                    data["total_floor"],  # $18
                    data["bathroom"],  # $19
                    data["other"],  # $20
                    data["options"],  # $21
                    data["fitment"],  # $22
                    data["tags"],  # $23
                    data["surrounding_type"],  # $24
                    data["surrounding_desc"],  # $25
                    data["surrounding_distance"],  # $26
                    data["is_rooftop"],  # $27
                    data["gender"],  # $28
                    data["pet_allowed"],  # $29
                    data["has_detail"],  # $30
                )
                if result["inserted"]:
                    inserted_count += 1

        objects_log.info(f"Batch saved {len(objects)} objects, {inserted_count} new")
        return inserted_count

    # Shared UPDATE for detail backfill (used by single + batch variants)
    _UPDATE_DETAIL_QUERY = """
        UPDATE objects SET
            floor = $3,
            floor_str = $4,
            total_floor = $5,
            is_rooftop = $6,
            layout = $7,
            layout_str = $8,
            bathroom = $9,
            area = $10,
            shape = $11,
            fitment = $12,
            gender = $13,
            pet_allowed = $14,
            options = $15,
            other = $16,
            surrounding_type = $17,
            surrounding_desc = $18,
            surrounding_distance = $19,
            has_detail = true,
            updated_at = NOW()
        WHERE source = $1 AND source_id = $2
        RETURNING source_id
    """

    @staticmethod
    def _detail_update_args(source: str, source_id: str, d: DBReadyData) -> tuple:
        """Positional args ($1..$19) for _UPDATE_DETAIL_QUERY."""
        return (
            source,  # $1
            source_id,  # $2
            d["floor"],  # $3
            d["floor_str"],  # $4
            d["total_floor"],  # $5
            d["is_rooftop"],  # $6
            d["layout"],  # $7
            d["layout_str"],  # $8
            d["bathroom"],  # $9
            d["area"],  # $10
            d["shape"],  # $11
            d["fitment"],  # $12
            d["gender"],  # $13
            d["pet_allowed"],  # $14
            d["options"],  # $15
            d["other"],  # $16
            d["surrounding_type"],  # $17
            d["surrounding_desc"],  # $18
            d["surrounding_distance"],  # $19
        )

    async def update_with_detail(self, detail_data: DBReadyData) -> bool:
        """
        Update object with detail data and set has_detail=true.

        Args:
            detail_data: DBReadyData containing source/source_id + detail fields

        Returns:
            True if updated, False if object not found
        """
        async with self._pool.acquire() as conn:
            result = await conn.fetchrow(
                self._UPDATE_DETAIL_QUERY,
                *self._detail_update_args(
                    detail_data["source"], detail_data["source_id"], detail_data
                ),
            )
            if result:
                objects_log.debug(
                    f"Updated object {detail_data['source']}:{detail_data['source_id']} with detail"
                )
                return True
            return False

    async def update_batch_with_detail(self, objects: list[DBReadyData]) -> int:
        """
        Batch update objects with detail data in a single transaction.

        All-or-nothing: a mid-batch failure rolls back every row so the DB does
        not end up partially backfilled (and out of sync with the Redis cache,
        which the caller refreshes only after this returns).

        Args:
            objects: List of DBReadyData dictionaries with detail

        Returns:
            Number of objects updated
        """
        if not objects:
            return 0

        updated = 0
        async with self._pool.acquire() as conn, conn.transaction():
            for obj in objects:
                result = await conn.fetchrow(
                    self._UPDATE_DETAIL_QUERY,
                    *self._detail_update_args(obj["source"], obj["source_id"], obj),
                )
                if result:
                    updated += 1

        objects_log.info(f"Batch updated {updated} objects with detail")
        return updated
