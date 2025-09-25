-- migration_2025_09_06_1_修复缺失的show_in_region_search字段.sql
-- 描述: 修复缺失的show_in_region_search字段  
-- 前置版本: 2025.09.04.4
-- 目标版本: 2025.09.06.1
-- 生成时间: 2025-09-06T00:02:41.545939

-- 向前迁移 (UP) - 添加缺失的show_in_region_search字段
-- 检查字段是否存在，如果不存在则添加
-- 使用更安全的方法检查列是否存在
PRAGMA table_info(merchants);

-- 添加show_in_region_search字段（如果不存在）
ALTER TABLE merchants ADD COLUMN show_in_region_search INTEGER DEFAULT 0;

-- 为现有活跃商家设置默认显示状态
UPDATE merchants SET show_in_region_search = 1 WHERE status = 'active';

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_merchants_region_search ON merchants(show_in_region_search);
CREATE INDEX IF NOT EXISTS idx_merchants_status_region_search ON merchants(status, show_in_region_search);

-- 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description) 
VALUES ('schema_version', '2025.09.06.1', '修复缺失的show_in_region_search字段');

-- 向后迁移 (DOWN) - 可选，用于回滚
-- 取消注释并添加回滚逻辑
-- UPDATE system_config SET config_value = '2025.09.04.4' WHERE config_key = 'schema_version';
