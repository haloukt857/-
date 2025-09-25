-- 迁移：移除遗留的省/区域旧表，统一使用 cities/districts
-- 描述：前后端统一使用 cities/districts 及其外键；删除历史的 provinces/regions 以避免迷惑字段。

-- 安全删除（存在才删除）
DROP TABLE IF EXISTS provinces;
DROP TABLE IF EXISTS regions;

-- 可选：删除历史兼容索引（若存在）
DROP INDEX IF EXISTS idx_provinces_name;
DROP INDEX IF EXISTS idx_regions_name;

