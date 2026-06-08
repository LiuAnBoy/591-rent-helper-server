-- Migration: objects multi-source support
-- Date: 2026-06-09
-- Description: Make objects table source-aware so multiple rental sources can coexist.
--   - rename current id (591 listing id) -> source_id, widen to VARCHAR(50)
--   - add source column (backfill existing rows as '591')
--   - add UUID surrogate primary key (DB-generated)
--   - dedup via UNIQUE(source, source_id)
--   - rebuild recent_objects view exposing source/source_id
--
-- NOTE: One-time migration for the EXISTING (prod) database. For fresh deploys,
-- migrations/init.sql is updated to the final schema directly; after prod is
-- migrated, fold this into init.sql and remove this file (single-init convention).

BEGIN;

-- recent_objects depends on the id column, drop it first
DROP VIEW IF EXISTS recent_objects;

-- 1. current id (591 listing id) -> source_id, widen type for alphanumeric source ids
ALTER TABLE objects RENAME COLUMN id TO source_id;
ALTER TABLE objects ALTER COLUMN source_id TYPE VARCHAR(50) USING source_id::text;

-- 2. add source (backfill existing rows as 591 via default)
ALTER TABLE objects ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT '591';

-- 3. add UUID surrogate id (DB generates one per existing row)
ALTER TABLE objects ADD COLUMN id UUID NOT NULL DEFAULT gen_random_uuid();

-- 4. swap primary key: drop old PK (was on the renamed source_id column), add new PK on id
ALTER TABLE objects DROP CONSTRAINT objects_pkey;
ALTER TABLE objects ADD CONSTRAINT objects_pkey PRIMARY KEY (id);

-- 5. dedup key
ALTER TABLE objects ADD CONSTRAINT objects_source_source_id_key UNIQUE (source, source_id);

-- 6. force explicit source on future inserts
ALTER TABLE objects ALTER COLUMN source DROP DEFAULT;

-- 7. index for lookups by source
CREATE INDEX IF NOT EXISTS idx_objects_source ON objects(source);

-- 8. rebuild view (expose source/source_id)
CREATE VIEW recent_objects AS
SELECT
    id,
    source,
    source_id,
    title,
    url,
    region,
    section,
    address,
    kind,
    kind_name,
    price,
    price_unit,
    price_per,
    layout,
    layout_str,
    shape,
    area,
    floor,
    floor_str,
    total_floor,
    is_rooftop,
    bathroom,
    other,
    options,
    fitment,
    gender,
    pet_allowed,
    tags,
    surrounding_type,
    surrounding_desc,
    surrounding_distance,
    first_seen_at,
    last_seen_at,
    created_at,
    updated_at,
    is_active
FROM objects
WHERE first_seen_at > NOW() - INTERVAL '7 days'
  AND is_active = TRUE
ORDER BY first_seen_at DESC;

COMMIT;
