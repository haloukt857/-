-- migration_2025_09_21_1_移除旧版region_category并规范地区结构.sql
-- 描述: 移除 merchants 表中的 legacy 字段（region, category, province_id, region_id），
--       保留并统一使用 city_id + district_id + merchant_type 等结构化字段。
--       重建表以删除无用列，并保留既有数据与索引/触发器。

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 1) 创建新表（无 region/category/province_id/region_id）
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
    district_id INTEGER,
    p_price INTEGER,
    pp_price INTEGER,
    custom_description TEXT,
    user_info TEXT,
    channel_link TEXT,
    show_in_region_search INTEGER DEFAULT 0,
    channel_chat_id TEXT,
    publish_time DATETIME,
    expiration_time DATETIME,
    FOREIGN KEY (district_id) REFERENCES districts(id)
);

-- 2) 迁移数据到新表
INSERT INTO merchants_new (
    id, telegram_chat_id, name, contact_info, profile_data, status, created_at, updated_at,
    merchant_type, city_id, district_id, p_price, pp_price, custom_description, user_info,
    channel_link, show_in_region_search, channel_chat_id, publish_time, expiration_time
) 
SELECT 
    id, telegram_chat_id, name, contact_info, profile_data, status, created_at, updated_at,
    merchant_type, city_id, district_id, p_price, pp_price, custom_description, user_info,
    channel_link, COALESCE(show_in_region_search, 0), channel_chat_id, publish_time, expiration_time
FROM merchants;

-- 3) 替换旧表
DROP TABLE merchants;
ALTER TABLE merchants_new RENAME TO merchants;

-- 4) 重新创建必要索引（若存在则忽略）
CREATE INDEX IF NOT EXISTS idx_merchants_telegram_chat_id ON merchants(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_merchants_channel_chat_id ON merchants(channel_chat_id);
CREATE INDEX IF NOT EXISTS idx_merchants_publish_time ON merchants(publish_time);
CREATE INDEX IF NOT EXISTS idx_merchants_expiration_time ON merchants(expiration_time);
CREATE INDEX IF NOT EXISTS idx_merchants_status ON merchants(status);
CREATE INDEX IF NOT EXISTS idx_merchants_district ON merchants(district_id);

-- 5) 重建更新时间触发器
DROP TRIGGER IF EXISTS update_merchants_timestamp;
CREATE TRIGGER IF NOT EXISTS update_merchants_timestamp 
    AFTER UPDATE ON merchants
    FOR EACH ROW
    BEGIN
        UPDATE merchants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- 6) 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.21.1', '移除旧版region/category并规范地区结构');

COMMIT;
PRAGMA foreign_keys = ON;

