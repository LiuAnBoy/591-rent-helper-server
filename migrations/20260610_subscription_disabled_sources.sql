-- Per-subscription disabled sources (opt-out; empty array = receive all sources).
-- Stores Source.key values (e.g. '591', 'ddroom') the subscription should NOT notify on.
--
-- Guarded with a DO block so that on a brand-new environment where this file
-- happens to sort before init.sql, it is a harmless no-op (the table doesn't
-- exist yet; init.sql will create the column). On existing DBs (prod / dev that
-- already ran init.sql) it adds the column to the live table.
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.tables WHERE table_name = 'subscriptions'
    ) THEN
        ALTER TABLE subscriptions
            ADD COLUMN IF NOT EXISTS disabled_sources TEXT[] NOT NULL DEFAULT '{}';
    END IF;
END $$;
