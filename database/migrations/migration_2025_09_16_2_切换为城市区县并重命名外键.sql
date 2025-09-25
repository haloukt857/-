-- 切换为城市/区县唯一方案，并重命名外键
-- 前置版本: 2025.09.16.1
-- 目标版本: 2025.09.16.2

BEGIN TRANSACTION;

-- 1) 创建新表 cities / districts（如果不存在）
CREATE TABLE IF NOT EXISTS cities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    code TEXT DEFAULT '',
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS districts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city_id INTEGER NOT NULL,
    code TEXT DEFAULT '',
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE,
    UNIQUE(name, city_id)
);

-- 2) 迁移 provinces/regions 数据到 cities/districts（若旧表存在）
INSERT OR IGNORE INTO cities (id, name, code, display_order, is_active, created_at, updated_at)
    SELECT id, name, COALESCE(code, ''), COALESCE(display_order, 0), COALESCE(is_active, 1), created_at, updated_at
    FROM provinces
    WHERE NOT EXISTS (SELECT 1 FROM cities c WHERE c.id = provinces.id);

INSERT OR IGNORE INTO districts (id, name, city_id, code, display_order, is_active, created_at, updated_at)
    SELECT r.id, r.name, r.province_id AS city_id, '' as code, COALESCE(r.display_order, 0), COALESCE(r.is_active, 1), r.created_at, r.updated_at
    FROM regions r
    WHERE NOT EXISTS (SELECT 1 FROM districts d WHERE d.id = r.id);

-- 3) 重命名 merchants 外键列（省 -> 城市，区 -> 区县）
-- 仅保留唯一方案：直接改列名
ALTER TABLE merchants RENAME COLUMN province_id TO city_id;
ALTER TABLE merchants RENAME COLUMN region_id TO district_id;

-- 4) 相关索引
CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(name);
CREATE INDEX IF NOT EXISTS idx_cities_display_order ON cities(display_order);
CREATE INDEX IF NOT EXISTS idx_districts_city_id ON districts(city_id);
CREATE INDEX IF NOT EXISTS idx_districts_name ON districts(name);
CREATE INDEX IF NOT EXISTS idx_districts_display_order ON districts(display_order);
CREATE INDEX IF NOT EXISTS idx_merchants_city_id ON merchants(city_id);
CREATE INDEX IF NOT EXISTS idx_merchants_district_id ON merchants(district_id);

-- 5) 清理旧触发器（如存在）
DROP TRIGGER IF EXISTS update_provinces_timestamp;
DROP TRIGGER IF EXISTS update_regions_timestamp;
DROP TRIGGER IF EXISTS sync_merchant_region_on_province_update;
DROP TRIGGER IF EXISTS sync_merchant_region_on_region_update;

-- 6) 新触发器（与 schema_extended.sql 对齐）
CREATE TRIGGER IF NOT EXISTS update_cities_timestamp 
    AFTER UPDATE ON cities
    FOR EACH ROW
    BEGIN
        UPDATE cities SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_districts_timestamp 
    AFTER UPDATE ON districts
    FOR EACH ROW
    BEGIN
        UPDATE districts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS sync_merchant_region_on_city_update
    AFTER UPDATE ON cities
    FOR EACH ROW
    WHEN OLD.name != NEW.name
    BEGIN
        UPDATE merchants 
        SET region = (
            SELECT c.name || '-' || d.name 
            FROM cities c, districts d 
            WHERE c.id = merchants.city_id 
            AND d.id = merchants.district_id
        )
        WHERE city_id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS sync_merchant_region_on_district_update
    AFTER UPDATE ON districts
    FOR EACH ROW
    WHEN OLD.name != NEW.name
    BEGIN
        UPDATE merchants 
        SET region = (
            SELECT c.name || '-' || d.name 
            FROM cities c, districts d 
            WHERE c.id = merchants.city_id 
            AND d.id = merchants.district_id
            AND d.id = NEW.id
        )
        WHERE district_id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_merchant_region_on_location_change
    AFTER UPDATE ON merchants
    FOR EACH ROW
    WHEN (OLD.city_id != NEW.city_id OR OLD.district_id != NEW.district_id)
    AND NEW.city_id IS NOT NULL AND NEW.district_id IS NOT NULL
    BEGIN
        UPDATE merchants 
        SET region = (
            SELECT c.name || '-' || d.name 
            FROM cities c, districts d 
            WHERE c.id = NEW.city_id 
            AND d.id = NEW.district_id
        )
        WHERE id = NEW.id;
    END;

-- 7) 删除旧表（一次性切换，唯一方案）
DROP TABLE IF EXISTS regions;
DROP TABLE IF EXISTS provinces;

-- 8) 版本
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.16.2', '切换为城市/区县并重命名外键');

COMMIT;

