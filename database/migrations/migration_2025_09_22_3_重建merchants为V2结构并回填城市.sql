-- migration_2025_09_22_3_重建merchants为V2结构并回填城市.sql
-- 描述: 将 merchants 表重建为 V2 结构（仅保留 city_id/district_id 等规范字段，移除 region/category/province_id/region_id），
--       并通过 districts 反查回填 city_id，确保与当前代码一致。
-- 前置要求: 存在 districts 表，且 merchants 表存在 district_id 字段（旧库已具备）。

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 1) 创建符合 V2 结构的新表
CREATE TABLE merchants_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_chat_id BIGINT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    contact_info TEXT,
    profile_data TEXT,
    status TEXT DEFAULT 'pending_submission' CHECK (status IN ('pending_submission','pending_approval','approved','published','expired')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    merchant_type TEXT DEFAULT 'teacher',
    city_id INTEGER,
    district_id INTEGER REFERENCES districts(id),
    p_price INTEGER,
    pp_price INTEGER,
    custom_description TEXT,
    adv_sentence TEXT,
    user_info TEXT,
    channel_link TEXT,
    channel_chat_id TEXT,
    show_in_region_search INTEGER DEFAULT 0,
    publish_time DATETIME,
    expiration_time DATETIME
);

-- 2) 迁移数据：city_id 通过 districts 反查，避免引用可能不存在的旧列
INSERT INTO merchants_new (
    id, telegram_chat_id, name, contact_info, profile_data, status, created_at, updated_at,
    merchant_type, city_id, district_id, p_price, pp_price, custom_description, adv_sentence, user_info,
    channel_link, channel_chat_id, show_in_region_search, publish_time, expiration_time
)
SELECT 
    m.id, m.telegram_chat_id, m.name, m.contact_info, m.profile_data, m.status, m.created_at, m.updated_at,
    m.merchant_type,
    (SELECT d.city_id FROM districts d WHERE d.id = m.district_id) AS city_id,
    m.district_id,
    m.p_price, m.pp_price, m.custom_description, m.adv_sentence, m.user_info,
    m.channel_link, m.channel_chat_id, COALESCE(m.show_in_region_search, 0), m.publish_time, m.expiration_time
FROM merchants m;

-- 3) 替换旧表
DROP TABLE merchants;
ALTER TABLE merchants_new RENAME TO merchants;

-- 4) 必要索引
CREATE INDEX IF NOT EXISTS idx_merchants_telegram_chat_id ON merchants(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_merchants_channel_chat_id ON merchants(channel_chat_id);
CREATE INDEX IF NOT EXISTS idx_merchants_publish_time ON merchants(publish_time);
CREATE INDEX IF NOT EXISTS idx_merchants_expiration_time ON merchants(expiration_time);
CREATE INDEX IF NOT EXISTS idx_merchants_status ON merchants(status);
CREATE INDEX IF NOT EXISTS idx_merchants_district ON merchants(district_id);
CREATE INDEX IF NOT EXISTS idx_merchants_city_id ON merchants(city_id);

-- 5) 更新时间触发器
DROP TRIGGER IF EXISTS update_merchants_timestamp;
CREATE TRIGGER IF NOT EXISTS update_merchants_timestamp 
    AFTER UPDATE ON merchants
    FOR EACH ROW
    BEGIN
        UPDATE merchants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

COMMIT;
PRAGMA foreign_keys = ON;

-- 版本号更新
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.22.3', '重建 merchants 为V2结构并回填城市');

