-- Migration: notification_bindings -> user_providers
-- Date: 2025-01-11
-- Description: 合併 user identity 與 notification binding 功能

-- ============================================
-- 1. 修改 users 表
-- ============================================

-- 新增 name 欄位
ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(100);

-- email 改為可選 (移除 NOT NULL)
ALTER TABLE users ALTER COLUMN email DROP NOT NULL;

-- password 改為可選 (移除 NOT NULL)
ALTER TABLE users ALTER COLUMN password DROP NOT NULL;

-- ============================================
-- 2. 建立 user_providers 表
-- ============================================
CREATE TABLE IF NOT EXISTS user_providers (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider        VARCHAR(20) NOT NULL,        -- 'telegram', 'line', 'discord', 'google'
    provider_id     VARCHAR(100) NOT NULL,       -- 平台用戶 ID
    provider_data   JSONB DEFAULT '{}',          -- 額外資料 (username, avatar, first_name...)
    notify_enabled  BOOLEAN DEFAULT TRUE,        -- 是否接收通知
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(provider, provider_id)                -- 同平台同 ID 只能綁一個帳號
);

-- 建立索引
CREATE INDEX IF NOT EXISTS idx_user_providers_user_id ON user_providers(user_id);
CREATE INDEX IF NOT EXISTS idx_user_providers_provider ON user_providers(provider);
CREATE INDEX IF NOT EXISTS idx_user_providers_lookup ON user_providers(provider, provider_id);

-- 建立 updated_at trigger
DROP TRIGGER IF EXISTS update_user_providers_updated_at ON user_providers;
CREATE TRIGGER update_user_providers_updated_at
    BEFORE UPDATE ON user_providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 3. 遷移資料 (notification_bindings -> user_providers)
-- ============================================
INSERT INTO user_providers (user_id, provider, provider_id, notify_enabled, created_at, updated_at)
SELECT
    user_id,
    service AS provider,
    service_id AS provider_id,
    enabled AS notify_enabled,
    created_at,
    updated_at
FROM notification_bindings
WHERE service_id IS NOT NULL AND service_id != ''
ON CONFLICT (provider, provider_id) DO NOTHING;

-- ============================================
-- 4. 更新 subscription_stats view
-- ============================================
CREATE OR REPLACE VIEW subscription_stats AS
SELECT
    s.id,
    s.name,
    s.region,
    s.section,
    u.id as user_id,
    u.name as user_name,
    COUNT(no.id) as total_notified,
    MAX(no.notified_at) as last_notified_at
FROM subscriptions s
JOIN users u ON s.user_id = u.id
LEFT JOIN notified_objects no ON s.id = no.subscription_id
GROUP BY s.id, s.name, s.region, s.section, u.id, u.name;

-- ============================================
-- 5. 刪除舊表 (確認資料遷移完成後執行)
-- ============================================
-- 注意：執行前請確認 user_providers 資料正確
DROP TABLE IF EXISTS notification_bindings;

-- ============================================
-- 驗證
-- ============================================
-- SELECT COUNT(*) FROM user_providers;
-- SELECT * FROM user_providers LIMIT 10;
