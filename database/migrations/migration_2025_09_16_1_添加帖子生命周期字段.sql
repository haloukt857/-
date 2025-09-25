-- migration_2025_09_16_1_添加帖子生命周期字段.sql
-- 描述: 为 merchants 表添加 publish_time 和 expiration_time 字段，并创建相关索引
-- 前置版本: 2025.09.06.3
-- 目标版本: 2025.09.16.1

-- 添加字段（若不存在则添加，由于SQLite不直接支持IF NOT EXISTS，失败可忽略由框架容错）
ALTER TABLE merchants ADD COLUMN publish_time DATETIME;
ALTER TABLE merchants ADD COLUMN expiration_time DATETIME;

-- 创建索引（幂等）
CREATE INDEX IF NOT EXISTS idx_merchants_publish_time ON merchants(publish_time);
CREATE INDEX IF NOT EXISTS idx_merchants_expiration_time ON merchants(expiration_time);

-- 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.16.1', '添加帖子生命周期字段 publish_time / expiration_time');

