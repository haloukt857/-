-- migration_2025_09_22_1_新增merchants_adv_sentence字段.sql
-- 描述: 新增 merchants.adv_sentence 字段（优势一句话，TEXT）
-- 前置版本: 2025.09.21.2
-- 目标版本: 2025.09.22.1
-- 生成时间: 2025-09-22T00:00:00

-- 向前迁移 (UP)
-- 增加字段（重复执行容错：若已存在将被忽略）
ALTER TABLE merchants ADD COLUMN adv_sentence TEXT;

-- 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.22.1', '新增 merchants.adv_sentence 字段');

-- 向后迁移 (DOWN) - 可选，用于回滚
-- SQLite 不支持直接删除列，如需回滚请手动重建表并迁移数据。
-- UPDATE system_config SET config_value = '2025.09.21.2' WHERE config_key = 'schema_version';

