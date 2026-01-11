-- Migration: Add index for instant notification feature
-- This index optimizes the query: SELECT * FROM objects WHERE region = $1 ORDER BY created_at DESC LIMIT 10

CREATE INDEX IF NOT EXISTS idx_objects_region_created_at
ON objects (region, created_at DESC);
