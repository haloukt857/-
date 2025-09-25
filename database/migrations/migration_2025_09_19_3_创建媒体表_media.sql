-- 创建媒体表（与代码查询字段一致）
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    telegram_file_id TEXT NOT NULL,
    media_type TEXT DEFAULT 'photo',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_media_merchant_id ON media(merchant_id);
CREATE INDEX IF NOT EXISTS idx_media_sort_order ON media(sort_order);

