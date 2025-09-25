-- 添加商家地区搜索显示控制字段
-- 迁移版本: 2025.09.04.4
-- 创建时间: 2025-09-04

-- 向前迁移 (UP) - 添加新字段
ALTER TABLE merchants ADD COLUMN show_in_region_search INTEGER DEFAULT 0;

-- 为现有活跃商家设置默认显示状态
UPDATE merchants SET show_in_region_search = 1 WHERE status = 'active';

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_merchants_region_search ON merchants(show_in_region_search);
CREATE INDEX IF NOT EXISTS idx_merchants_status_region_search ON merchants(status, show_in_region_search);

-- 版本更新到 2025.09.04.4