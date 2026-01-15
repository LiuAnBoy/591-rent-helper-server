-- Migration: Add has_detail column to objects table
-- For tracking whether object has complete detail data

-- Add has_detail column
ALTER TABLE objects
ADD COLUMN IF NOT EXISTS has_detail BOOLEAN NOT NULL DEFAULT false;

-- Update existing data to mark as having detail (old flow only saved objects with detail)
UPDATE objects SET has_detail = true WHERE has_detail = false;

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_objects_region_has_detail ON objects(region, has_detail);
CREATE INDEX IF NOT EXISTS idx_objects_created_at ON objects(created_at DESC);
