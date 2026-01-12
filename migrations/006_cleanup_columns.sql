-- Migration: Remove unused columns and fix view
-- Date: 2026-01-12

-- Drop old view (has wrong column mappings)
DROP VIEW IF EXISTS recent_objects;

-- Remove deprecated/unused columns
ALTER TABLE objects DROP COLUMN IF EXISTS floor_range_old;
ALTER TABLE objects DROP COLUMN IF EXISTS raw_data;

-- Recreate view with correct columns
CREATE VIEW recent_objects AS
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
    bathroom,
    other,
    options,
    fitment,
    tags,
    surrounding_type,
    surrounding_desc,
    surrounding_distance,
    first_seen_at,
    last_seen_at,
    created_at,
    updated_at,
    is_active,
    is_rooftop,
    gender,
    pet_allowed
FROM objects
WHERE first_seen_at > (now() - '7 days'::interval)
  AND is_active = true
ORDER BY first_seen_at DESC;
