-- 迁移：媒体表与商户频道信息
-- 版本：2025.09.19.6

-- 媒体表（幂等）
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    telegram_file_id TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('photo','video')),
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_media_merchant ON media(merchant_id);
CREATE INDEX IF NOT EXISTS idx_media_sort ON media(sort_order);

-- 商户：发布频道 chat_id（可为负数的Telegram聊天ID或字符串）
ALTER TABLE merchants ADD COLUMN channel_chat_id TEXT;

-- 版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.19.6', '数据库架构版本');

