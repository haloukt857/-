-- 修正媒体表：为已存在但缺列的数据库补全字段

-- 创建表（若不存在）
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id INTEGER NOT NULL,
    telegram_file_id TEXT NOT NULL,
    media_type TEXT DEFAULT 'photo',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
);

-- 尝试补充缺失列（若已存在会被忽略）
ALTER TABLE media ADD COLUMN media_type TEXT DEFAULT 'photo';
ALTER TABLE media ADD COLUMN sort_order INTEGER DEFAULT 0;

-- 索引（幂等）
CREATE INDEX IF NOT EXISTS idx_media_merchant_id ON media(merchant_id);
CREATE INDEX IF NOT EXISTS idx_media_sort_order ON media(sort_order);

