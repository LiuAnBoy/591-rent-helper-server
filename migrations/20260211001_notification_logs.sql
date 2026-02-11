-- Migration: Replace notified_objects with notification_logs
-- Date: 2026-02-11
-- Description: New table to log all notification attempts (success + failed) with error details

-- Step 1: Create new table
CREATE TABLE IF NOT EXISTS notification_logs (
    id              SERIAL PRIMARY KEY,
    crawler_run_id  INTEGER REFERENCES crawler_runs(id) ON DELETE SET NULL,
    object_id       INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    provider        VARCHAR(20) NOT NULL,       -- telegram, line, etc.
    status          VARCHAR(20) NOT NULL,       -- success / failed
    error_message   TEXT,                       -- failure reason (NULL if success)
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(subscription_id, object_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_notification_logs_object_id ON notification_logs(object_id);
CREATE INDEX IF NOT EXISTS idx_notification_logs_subscription_id ON notification_logs(subscription_id);
CREATE INDEX IF NOT EXISTS idx_notification_logs_crawler_run_id ON notification_logs(crawler_run_id);
CREATE INDEX IF NOT EXISTS idx_notification_logs_status ON notification_logs(status);
CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at ON notification_logs(created_at DESC);

-- Step 2: Migrate existing data (all records are telegram, all are success)
INSERT INTO notification_logs (object_id, subscription_id, provider, status, created_at)
SELECT object_id, subscription_id, 'telegram', 'success', notified_at
FROM notified_objects
ON CONFLICT (subscription_id, object_id, provider) DO NOTHING;

-- Step 3: Drop old view first (column names changed, CREATE OR REPLACE won't work)
DROP VIEW IF EXISTS subscription_stats;

CREATE VIEW subscription_stats AS
SELECT
    s.id,
    s.name,
    s.region,
    s.section,
    u.id as user_id,
    u.name as user_name,
    COUNT(nl.id) as total_notified,
    MAX(nl.created_at) as last_notified_at
FROM subscriptions s
JOIN users u ON s.user_id = u.id
LEFT JOIN notification_logs nl ON s.id = nl.subscription_id
GROUP BY s.id, s.name, s.region, s.section, u.id, u.name;

-- Step 4: Drop old table (CASCADE in case of leftover dependencies)
DROP TABLE IF EXISTS notified_objects CASCADE;

-- Record migration
INSERT INTO schema_migrations (filename) VALUES ('20260211001_notification_logs.sql');
