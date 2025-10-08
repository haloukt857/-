-- 新增 merchant_posts 表：记录每条频道贴文(用于编辑/删除)
CREATE TABLE IF NOT EXISTS merchant_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    chat_id TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    post_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_merchant_posts_mid ON merchant_posts(merchant_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_merchant_posts_unique ON merchant_posts(merchant_id, chat_id, message_id);

-- 同步架构版本
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.10.08.1', '新增 merchant_posts 表，用于记录频道消息以支持删除/编辑');

