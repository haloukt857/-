-- 兼容补丁：在 2025.09.16.2 之前，补齐可能缺失的 cities/districts 列（时间戳与 code）
-- 说明：部分早期环境已存在 cities/districts，但缺少 created_at/updated_at，
-- 或缺少 code 列，导致 2025-09-16-2 的 INSERT 语句引用这些列时报错。
-- 本补丁仅尝试添加列；如列已存在，迁移执行器会忽略“duplicate column name”并继续。

ALTER TABLE cities ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE cities ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE cities ADD COLUMN code TEXT DEFAULT '';

ALTER TABLE districts ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE districts ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE districts ADD COLUMN code TEXT DEFAULT '';
