-- 为 merchants 表增加 post_url 字段，用于保存最近一次发布的频道贴文链接
ALTER TABLE merchants ADD COLUMN post_url TEXT;

-- 记录迁移版本（若有 system_config 版本管理，可在此补充）
-- INSERT OR REPLACE INTO system_config (key, value) VALUES ('schema_version', '2025.09.27.1');

