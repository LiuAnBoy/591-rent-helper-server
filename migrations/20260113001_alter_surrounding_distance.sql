-- Migration: Alter surrounding_distance from VARCHAR to INTEGER
-- Date: 2026-01-13
-- Description: Change surrounding_distance column type for better querying

-- Step 1: Add new column
ALTER TABLE objects ADD COLUMN surrounding_distance_new INTEGER;

-- Step 2: Migrate data (extract number from existing VARCHAR values)
-- Example: "353公尺" -> 353, "500" -> 500
UPDATE objects
SET surrounding_distance_new = CASE
    WHEN surrounding_distance IS NULL THEN NULL
    WHEN surrounding_distance ~ '^\d+$' THEN surrounding_distance::INTEGER
    WHEN surrounding_distance ~ '\d+' THEN (regexp_match(surrounding_distance, '(\d+)'))[1]::INTEGER
    ELSE NULL
END;

-- Step 3: Drop old column and rename new one
ALTER TABLE objects DROP COLUMN surrounding_distance;
ALTER TABLE objects RENAME COLUMN surrounding_distance_new TO surrounding_distance;

-- Step 4: Add index for distance queries (optional, for "within X meters" queries)
CREATE INDEX IF NOT EXISTS idx_objects_surrounding_distance ON objects(surrounding_distance);

-- Step 5: Update recent_objects view to reflect the change
CREATE OR REPLACE VIEW recent_objects AS
SELECT
    id,
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
