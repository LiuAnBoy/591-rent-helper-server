-- 591 Crawler Database Schema
-- Based on ptt-alertor architecture

-- ============================================
-- Helper function for auto-updating updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 1. Role Limits (角色權限表)
-- ============================================
CREATE TABLE IF NOT EXISTS role_limits (
    id                  SERIAL PRIMARY KEY,
    role                VARCHAR(20) UNIQUE NOT NULL,
    max_subscriptions   INTEGER NOT NULL DEFAULT 3,
    description         VARCHAR(100),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Default roles
INSERT INTO role_limits (role, max_subscriptions, description) VALUES
    ('admin', -1, '管理員，無限制'),
    ('vip', 20, 'VIP 用戶'),
    ('user', 3, '一般用戶')
ON CONFLICT (role) DO NOTHING;

CREATE TRIGGER update_role_limits_updated_at
    BEFORE UPDATE ON role_limits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 2. Users (使用者表)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100),                    -- 顯示名稱 (從 provider 取得)
    email       VARCHAR(255) UNIQUE,             -- 可選，傳統登入用
    password    VARCHAR(255),                    -- 可選，傳統登入用
    role        VARCHAR(20) DEFAULT 'user' REFERENCES role_limits(role),
    enabled     BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 3. User Providers (使用者登入與通知綁定)
--    合併 identity + notification 功能
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

CREATE INDEX IF NOT EXISTS idx_user_providers_user_id ON user_providers(user_id);
CREATE INDEX IF NOT EXISTS idx_user_providers_provider ON user_providers(provider);
CREATE INDEX IF NOT EXISTS idx_user_providers_lookup ON user_providers(provider, provider_id);

CREATE TRIGGER update_user_providers_updated_at
    BEFORE UPDATE ON user_providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 4. Subscriptions (訂閱表)
-- ============================================
CREATE TABLE IF NOT EXISTS subscriptions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,      -- 訂閱名稱，方便識別

    -- ========== 位置 ==========
    region          INTEGER NOT NULL,           -- 縣市代碼 (1=台北市, 3=新北市)
    section         INTEGER[],                  -- 區域代碼 (可多選) [5,10,8]

    -- ========== 物件類型 kind ==========
    -- 1=整層住家, 2=獨立套房, 3=分租套房, 4=雅房, 8=車位, 24=其他
    kind            INTEGER[],                  -- [1,2,3]

    -- ========== 租金 price ==========
    price_min       INTEGER,                    -- 最低租金
    price_max       INTEGER,                    -- 最高租金

    -- ========== 格局 layout ==========
    -- 1=1房, 2=2房, 3=3房, 4=4房以上
    layout          INTEGER[],                  -- [1,2]

    -- ========== 建物型態 shape ==========
    -- 1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅
    shape           INTEGER[],                  -- [1,2]

    -- ========== 坪數 area ==========
    area_min        DECIMAL(10, 2),             -- 最小坪數
    area_max        DECIMAL(10, 2),             -- 最大坪數

    -- ========== 樓層 floor ==========
    floor_min       INTEGER,                    -- 最低樓層
    floor_max       INTEGER,                    -- 最高樓層

    -- ========== 衛浴 bathroom ==========
    -- 1=1衛, 2=2衛, 3=3衛, 4=4衛以上
    bathroom        INTEGER[],                  -- [1, 2]

    -- ========== 特色 other ==========
    -- newPost=新上架, near_subway=近捷運, pet=可養寵物, cook=可開伙,
    -- cartplace=有車位, lift=有電梯, balcony_1=有陽台, lease=可短期租賃,
    -- social-housing=社會住宅, rental-subsidy=租金補貼, elderly-friendly=高齡友善,
    -- tax-deductible=可報稅, naturalization=可入籍
    other        TEXT[],                     -- ['pet', 'near_subway', 'cook']

    -- ========== 設備 option ==========
    -- cold=冷氣, washer=洗衣機, icebox=冰箱, hotwater=熱水器,
    -- naturalgas=天然瓦斯, broadband=網路, bed=床
    options         TEXT[],                     -- ['cold', 'washer', 'icebox']

    -- ========== 裝潢 fitment ==========
    -- 99=新裝潢, 3=中檔裝潢, 4=高檔裝潢
    fitment         INTEGER[],                  -- [99, 3, 4]

    -- ========== 須知 (獨立欄位) ==========
    exclude_rooftop BOOLEAN DEFAULT FALSE,      -- 排除頂樓加蓋
    gender          VARCHAR(10) DEFAULT NULL,   -- 性別限制 (boy=限男, girl=限女, NULL=不限)
    pet_required    BOOLEAN DEFAULT FALSE,      -- 需要可養寵物

    -- ========== 狀態 ==========
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_region ON subscriptions(region);
CREATE INDEX IF NOT EXISTS idx_subscriptions_enabled ON subscriptions(enabled);
CREATE INDEX IF NOT EXISTS idx_subscriptions_floor_min ON subscriptions(floor_min);
CREATE INDEX IF NOT EXISTS idx_subscriptions_floor_max ON subscriptions(floor_max);

CREATE TRIGGER update_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 5. Objects (物件表)
-- ============================================
CREATE TABLE IF NOT EXISTS objects (
    -- Primary key (591 物件 ID)
    id              INTEGER PRIMARY KEY,

    -- ========== 基本資訊 ==========
    title           VARCHAR(500) NOT NULL,
    url             VARCHAR(300),

    -- ========== 位置 ==========
    region          INTEGER NOT NULL,           -- 縣市代碼 (1=台北市, 3=新北市)
    section         INTEGER,                    -- 區域代碼
    address         VARCHAR(200),               -- 完整地址

    -- ========== 物件類型 kind ==========
    -- 1=整層住家, 2=獨立套房, 3=分租套房, 4=雅房, 8=車位, 24=其他
    kind            INTEGER,
    kind_name       VARCHAR(50),

    -- ========== 租金 price ==========
    price           INTEGER NOT NULL,           -- 租金 (數值)
    price_unit      VARCHAR(20) DEFAULT '元/月',
    price_per       DECIMAL(10, 2),             -- 每坪單價

    -- ========== 格局/坪數 ==========
    -- layout: 1=1房, 2=2房, 3=3房, 4=4房以上
    -- shape: 1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅
    layout          INTEGER,                    -- 房數
    layout_str      VARCHAR(50),                -- 原始格局字串 (2房1廳)
    shape           INTEGER,                    -- 建物型態
    area            DECIMAL(10, 2),             -- 坪數

    -- ========== 樓層 ==========
    floor           INTEGER,                    -- 樓層數字
    floor_str       VARCHAR(50),                -- 原始樓層字串 (3F/5F)
    total_floor     INTEGER,                    -- 總樓層
    is_rooftop      BOOLEAN DEFAULT FALSE,      -- 是否頂樓加蓋 (from floor_name)

    -- ========== 衛浴 ==========
    -- 1=1衛, 2=2衛, 3=3衛, 4+=4衛以上
    bathroom        INTEGER,

    -- ========== 特色/設備/裝潢 ==========
    -- other: newPost, near_subway, pet, cook, cartplace, lift, balcony_1, lease,
    --        social-housing, rental-subsidy, elderly-friendly, tax-deductible, naturalization
    -- options: cold=冷氣, washer=洗衣機, icebox=冰箱, hotwater=熱水器,
    --          naturalgas=天然瓦斯, broadband=網路, bed=床
    -- fitment: 99=新裝潢, 3=中檔裝潢, 4=高檔裝潢
    other           TEXT[],
    options         TEXT[],
    fitment         INTEGER,

    -- ========== 須知 ==========
    gender          VARCHAR(10) DEFAULT 'all',  -- 性別限制 (boy/girl/all, from service.rule)
    pet_allowed     BOOLEAN DEFAULT NULL,       -- 可否養寵物 (from service.rule)

    -- ========== 標籤 ==========
    tags            TEXT[],                     -- 原始 591 tags

    -- ========== 周邊資訊 ==========
    surrounding_type     VARCHAR(20),           -- 類型 (metro, bus)
    surrounding_desc     VARCHAR(100),          -- 站名 (信義安和站)
    surrounding_distance INTEGER,               -- 距離 (公尺)

    -- ========== 時間戳記 ==========
    first_seen_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),  -- 首次爬到的時間
    last_seen_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW(),  -- 最後爬到的時間
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- ========== 狀態 ==========
    is_active       BOOLEAN DEFAULT TRUE,       -- 物件是否還在線上
    has_detail      BOOLEAN NOT NULL DEFAULT false  -- 是否已有完整 detail 資料
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_objects_region_section ON objects(region, section);
CREATE INDEX IF NOT EXISTS idx_objects_kind ON objects(kind);
CREATE INDEX IF NOT EXISTS idx_objects_price ON objects(price);
CREATE INDEX IF NOT EXISTS idx_objects_layout ON objects(layout);
CREATE INDEX IF NOT EXISTS idx_objects_shape ON objects(shape);
CREATE INDEX IF NOT EXISTS idx_objects_area ON objects(area);
CREATE INDEX IF NOT EXISTS idx_objects_floor ON objects(floor);
CREATE INDEX IF NOT EXISTS idx_objects_total_floor ON objects(total_floor);
CREATE INDEX IF NOT EXISTS idx_objects_bathroom ON objects(bathroom);
CREATE INDEX IF NOT EXISTS idx_objects_fitment ON objects(fitment);
CREATE INDEX IF NOT EXISTS idx_objects_other ON objects USING GIN(other);
CREATE INDEX IF NOT EXISTS idx_objects_options ON objects USING GIN(options);
CREATE INDEX IF NOT EXISTS idx_objects_is_rooftop ON objects(is_rooftop);
CREATE INDEX IF NOT EXISTS idx_objects_gender ON objects(gender);
CREATE INDEX IF NOT EXISTS idx_objects_pet_allowed ON objects(pet_allowed);
CREATE INDEX IF NOT EXISTS idx_objects_surrounding_distance ON objects(surrounding_distance);
CREATE INDEX IF NOT EXISTS idx_objects_first_seen_at ON objects(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_objects_is_active ON objects(is_active);
CREATE INDEX IF NOT EXISTS idx_objects_region_created_at ON objects(region, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_objects_region_has_detail ON objects(region, has_detail);
CREATE INDEX IF NOT EXISTS idx_objects_created_at ON objects(created_at DESC);

CREATE TRIGGER update_objects_updated_at
    BEFORE UPDATE ON objects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================
-- 6. Crawler Runs (爬蟲執行記錄)
--    追蹤爬蟲執行狀態 + 推播結果
-- ============================================
CREATE TABLE IF NOT EXISTS crawler_runs (
    id                SERIAL PRIMARY KEY,
    region            INTEGER NOT NULL,
    started_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    finished_at       TIMESTAMP WITH TIME ZONE,
    status            VARCHAR(20) DEFAULT 'running',  -- running, success, failed
    total_fetched     INTEGER DEFAULT 0,
    new_objects       INTEGER DEFAULT 0,
    error_message     TEXT,
    broadcast_total   INTEGER DEFAULT 0,      -- 推播總數
    broadcast_success INTEGER DEFAULT 0,      -- 推播成功數
    broadcast_failed  INTEGER DEFAULT 0,      -- 推播失敗數
    broadcast_errors  TEXT                    -- 推播失敗詳情（成功為 NULL）
);

CREATE INDEX IF NOT EXISTS idx_crawler_runs_started_at ON crawler_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawler_runs_region ON crawler_runs(region);

-- ============================================
-- Views (視圖)
-- ============================================

-- 活躍物件視圖 (最近 7 天)
CREATE OR REPLACE VIEW recent_objects AS
SELECT
    id,
    title,
    url,
    region,
    section,
    address,
    kind,
    kind_name,
    price,
    price_unit,
    price_per,
    layout,
    layout_str,
    shape,
    area,
    floor,
    floor_str,
    total_floor,
    is_rooftop,
    bathroom,
    other,
    options,
    fitment,
    gender,
    pet_allowed,
    tags,
    surrounding_type,
    surrounding_desc,
    surrounding_distance,
    first_seen_at,
    last_seen_at,
    created_at,
    updated_at,
    is_active,
    has_detail
FROM objects
WHERE first_seen_at > NOW() - INTERVAL '7 days'
  AND is_active = TRUE
ORDER BY first_seen_at DESC;
