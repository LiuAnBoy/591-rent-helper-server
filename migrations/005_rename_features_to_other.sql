-- Rename features column to other (to match 591 API parameter name)
-- subscriptions table
ALTER TABLE subscriptions RENAME COLUMN features TO other;

-- objects table
ALTER TABLE objects RENAME COLUMN features TO other;

-- Rename index
DROP INDEX IF EXISTS idx_objects_features;
CREATE INDEX IF NOT EXISTS idx_objects_other ON objects USING GIN(other);
