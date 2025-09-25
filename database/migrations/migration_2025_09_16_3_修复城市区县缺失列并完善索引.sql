-- 修复已有 cities/districts 表缺失列，确保与后端字段一致
-- 前置版本: 2025.09.16.2
-- 目标版本: 2025.09.16.3

-- cities 表补齐列（如已存在则忽略）
ALTER TABLE cities ADD COLUMN code TEXT DEFAULT '';
ALTER TABLE cities ADD COLUMN display_order INTEGER DEFAULT 0;
ALTER TABLE cities ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE cities ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- districts 表补齐列（如已存在则忽略）
ALTER TABLE districts ADD COLUMN code TEXT DEFAULT '';
ALTER TABLE districts ADD COLUMN display_order INTEGER DEFAULT 0;
ALTER TABLE districts ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE districts ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 索引幂等创建
CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(name);
CREATE INDEX IF NOT EXISTS idx_cities_display_order ON cities(display_order);
CREATE INDEX IF NOT EXISTS idx_districts_city_id ON districts(city_id);
CREATE INDEX IF NOT EXISTS idx_districts_name ON districts(name);
CREATE INDEX IF NOT EXISTS idx_districts_display_order ON districts(display_order);

-- merchants 外键索引（若遗漏）
CREATE INDEX IF NOT EXISTS idx_merchants_city_id ON merchants(city_id);
CREATE INDEX IF NOT EXISTS idx_merchants_district_id ON merchants(district_id);

-- 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.16.3', '修复城市区县缺失列并完善索引');

