-- Migration: Move broadcast results into crawler_runs, remove notification_logs
-- Date: 2026-02-11
-- Description: Simplify broadcast logging - one record per crawler run instead of per notification

-- Step 1: Add broadcast columns to crawler_runs
ALTER TABLE crawler_runs ADD COLUMN IF NOT EXISTS broadcast_total   INTEGER DEFAULT 0;
ALTER TABLE crawler_runs ADD COLUMN IF NOT EXISTS broadcast_success INTEGER DEFAULT 0;
ALTER TABLE crawler_runs ADD COLUMN IF NOT EXISTS broadcast_failed  INTEGER DEFAULT 0;
ALTER TABLE crawler_runs ADD COLUMN IF NOT EXISTS broadcast_errors  TEXT;

-- Step 2: Drop subscription_stats view first (depends on notification_logs)
DROP VIEW IF EXISTS subscription_stats;

-- Step 3: Drop notification_logs table (created in previous migration)
DROP TABLE IF EXISTS notification_logs CASCADE;

-- Record migration
INSERT INTO schema_migrations (filename) VALUES ('20260211002_broadcast_in_crawler_runs.sql');
