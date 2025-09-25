-- posting_channels 增加 role 字段以区分用途：post / review_u2m / review_m2u

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

ALTER TABLE posting_channels ADD COLUMN role TEXT NOT NULL DEFAULT 'post';

-- 可选：为 role 建立简单索引（提升按role查询性能）
CREATE INDEX IF NOT EXISTS idx_posting_channels_role ON posting_channels(role);

COMMIT;
PRAGMA foreign_keys=ON;

