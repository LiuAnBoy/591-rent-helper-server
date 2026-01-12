-- Migration: Floor Field Redesign
-- Description: Change floor from VARCHAR range code to INTEGER numeric value
--              Add total_floor field for total building floors
--
-- ============================================
-- Floor Value Mapping (新設計)
-- ============================================
--   Normal floor: 1, 2, 3... (positive integer)
--   Rooftop addition: 0 (is_rooftop=true)
--   Basement B1: -1 (is_rooftop=false)
--   Basement B2: -2 (is_rooftop=false)
--
-- ============================================
-- Current Data Format (舊格式)
-- ============================================
--
-- [Subscriptions 訂閱表]
--   floor TEXT[] = ['1_1', '2_6', '6_12', '13_']
--   範圍代碼:
--     '1_1'  = 1樓      (floor = 1)
--     '2_6'  = 2-6層    (floor = 2~6)
--     '6_12' = 6-12層   (floor = 6~12)
--     '13_'  = 12樓以上  (floor >= 13)
--
--   Example: floor = ['1_1', '2_6']
--     → 需要 1樓 或 2-6層
--     → 遷移為: floor_min = 1, floor_max = 6
--
-- [Objects 物件表]
--   floor VARCHAR(20) = 樓層代碼 (通常為 NULL)
--   floor_str VARCHAR(50) = 原始字串，如:
--     "3F/5F"       → floor=3, total_floor=5
--     "頂層加蓋/5F"  → floor=0, total_floor=5, is_rooftop=true
--     "B1/10F"      → floor=-1, total_floor=10
--     "B2/8F"       → floor=-2, total_floor=8
--
-- ============================================

BEGIN;

-- ============================================
-- 1. Objects Table - Schema Changes
-- ============================================

-- 1.1 Add new columns
ALTER TABLE objects
ADD COLUMN IF NOT EXISTS total_floor INTEGER;

-- 1.2 Backup old floor column
ALTER TABLE objects
RENAME COLUMN floor TO floor_range_old;

-- 1.3 Add new floor column as INTEGER
ALTER TABLE objects
ADD COLUMN floor INTEGER;

-- ============================================
-- 2. Objects Table - Data Migration
-- ============================================

-- 2.1 Parse floor_str to extract floor number
--     Handles: "3F/5F", "頂層加蓋/5F", "B1/10F", "B2/8F"
UPDATE objects
SET floor = CASE
    -- Rooftop: 頂 + 加 → floor = 0
    WHEN floor_str LIKE '%頂%' AND floor_str LIKE '%加%' THEN 0
    -- Basement B1: starts with B1 → floor = -1
    WHEN floor_str ~* '^B1' THEN -1
    -- Basement B2: starts with B2 → floor = -2
    WHEN floor_str ~* '^B2' THEN -2
    -- Basement B3: starts with B3 → floor = -3
    WHEN floor_str ~* '^B3' THEN -3
    -- Normal floor: extract first number (e.g., "3F/5F" → 3)
    WHEN floor_str ~ '^\d+' THEN (regexp_match(floor_str, '^(\d+)'))[1]::INTEGER
    ELSE NULL
END
WHERE floor_str IS NOT NULL AND floor_str != '';

-- 2.2 Parse floor_str to extract total_floor
--     Pattern: "/5F" → 5
UPDATE objects
SET total_floor = (regexp_match(floor_str, '/(\d+)F'))[1]::INTEGER
WHERE floor_str ~ '/\d+F';

-- 2.3 Update is_rooftop based on floor_str (if not already set)
UPDATE objects
SET is_rooftop = TRUE
WHERE floor_str LIKE '%頂%' AND floor_str LIKE '%加%'
  AND (is_rooftop IS NULL OR is_rooftop = FALSE);

-- ============================================
-- 3. Subscriptions Table - Schema Changes
-- ============================================

-- 3.1 Add floor_min and floor_max columns
ALTER TABLE subscriptions
ADD COLUMN IF NOT EXISTS floor_min INTEGER,
ADD COLUMN IF NOT EXISTS floor_max INTEGER;

-- 3.2 Backup old floor column
ALTER TABLE subscriptions
RENAME COLUMN floor TO floor_range_old;

-- ============================================
-- 4. Subscriptions Table - Data Migration
-- ============================================

-- 4.1 Create helper function to parse floor ranges
CREATE OR REPLACE FUNCTION parse_floor_range(range_code TEXT)
RETURNS TABLE(min_floor INTEGER, max_floor INTEGER) AS $$
BEGIN
    CASE range_code
        WHEN '1_1' THEN   -- 1樓
            RETURN QUERY SELECT 1, 1;
        WHEN '2_6' THEN   -- 2-6層
            RETURN QUERY SELECT 2, 6;
        WHEN '6_12' THEN  -- 6-12層
            RETURN QUERY SELECT 6, 12;
        WHEN '13_' THEN   -- 12樓以上
            RETURN QUERY SELECT 13, NULL::INTEGER;
        ELSE
            RETURN QUERY SELECT NULL::INTEGER, NULL::INTEGER;
    END CASE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 4.2 Migrate subscription floor ranges
--     floor_range_old = ['1_1', '2_6'] → floor_min = 1, floor_max = 6
--     取所有範圍的 min 和 max
WITH floor_bounds AS (
    SELECT
        s.id,
        MIN(p.min_floor) AS overall_min,
        MAX(COALESCE(p.max_floor, 999)) AS overall_max
    FROM subscriptions s
    CROSS JOIN LATERAL unnest(s.floor_range_old) AS range_code
    CROSS JOIN LATERAL parse_floor_range(range_code) AS p
    WHERE s.floor_range_old IS NOT NULL
      AND array_length(s.floor_range_old, 1) > 0
    GROUP BY s.id
)
UPDATE subscriptions s
SET
    floor_min = fb.overall_min,
    floor_max = CASE
        WHEN fb.overall_max = 999 THEN NULL  -- 13_ 無上限
        ELSE fb.overall_max
    END
FROM floor_bounds fb
WHERE s.id = fb.id;

-- 4.3 Drop helper function
DROP FUNCTION IF EXISTS parse_floor_range(TEXT);

-- ============================================
-- 5. Create Indexes
-- ============================================

-- Objects indexes
CREATE INDEX IF NOT EXISTS idx_objects_floor_new ON objects(floor);
CREATE INDEX IF NOT EXISTS idx_objects_total_floor ON objects(total_floor);

-- Subscriptions indexes
CREATE INDEX IF NOT EXISTS idx_subscriptions_floor_min ON subscriptions(floor_min);
CREATE INDEX IF NOT EXISTS idx_subscriptions_floor_max ON subscriptions(floor_max);

-- Drop old indexes (will be recreated if needed)
DROP INDEX IF EXISTS idx_objects_floor;

-- ============================================
-- 6. Add Comments
-- ============================================

COMMENT ON COLUMN objects.floor IS 'Current floor: positive=normal, 0=rooftop, negative=basement (B1=-1, B2=-2)';
COMMENT ON COLUMN objects.total_floor IS 'Total floors in building';
COMMENT ON COLUMN objects.floor_range_old IS 'DEPRECATED: Old range code. Remove after verification.';

COMMENT ON COLUMN subscriptions.floor_min IS 'Minimum floor filter (inclusive)';
COMMENT ON COLUMN subscriptions.floor_max IS 'Maximum floor filter (inclusive, NULL=no limit)';
COMMENT ON COLUMN subscriptions.floor_range_old IS 'DEPRECATED: Old range array. Remove after verification.';

COMMIT;

-- ============================================
-- Migration Verification Queries
-- ============================================
-- Run these to verify the migration:
--
-- -- Check objects migration
-- SELECT id, floor_str, floor, total_floor, is_rooftop, floor_range_old
-- FROM objects
-- WHERE floor_str IS NOT NULL
-- LIMIT 20;
--
-- -- Check subscriptions migration
-- SELECT id, name, floor_range_old, floor_min, floor_max
-- FROM subscriptions
-- WHERE floor_range_old IS NOT NULL
-- LIMIT 20;

-- ============================================
-- Cleanup (run after verification)
-- ============================================
-- ALTER TABLE objects DROP COLUMN floor_range_old;
-- ALTER TABLE subscriptions DROP COLUMN floor_range_old;
