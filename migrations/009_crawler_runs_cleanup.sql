-- Migration: Clean up crawler_runs table
-- 1. Remove unused section column
-- 2. Rename new_listings to new_objects

ALTER TABLE crawler_runs DROP COLUMN IF EXISTS section;
ALTER TABLE crawler_runs RENAME COLUMN new_listings TO new_objects;
