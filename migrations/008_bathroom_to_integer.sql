-- Migration: Change bathroom column from TEXT[] to INTEGER[]

ALTER TABLE subscriptions
ALTER COLUMN bathroom TYPE INTEGER[]
USING bathroom::INTEGER[];
