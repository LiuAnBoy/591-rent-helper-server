-- Migration: Drop unused floor_range_old column from subscriptions
-- This column was replaced by floor_min/floor_max in 004_floor_redesign.sql

ALTER TABLE subscriptions DROP COLUMN IF EXISTS floor_range_old;
