-- 为 orders 表增加 updated_at 列，并初始化

ALTER TABLE orders ADD COLUMN updated_at DATETIME;
UPDATE orders SET updated_at = COALESCE(updated_at, created_at);

