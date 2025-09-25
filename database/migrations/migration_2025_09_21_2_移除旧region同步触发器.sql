-- migration_2025_09_21_2_移除旧region同步触发器.sql
-- 描述: 删除所有依赖 merchants.region 的历史触发器，彻底切换到结构化地区字段

BEGIN TRANSACTION;

-- 删除历史触发器（如果存在）
DROP TRIGGER IF EXISTS sync_merchant_region_on_city_update;
DROP TRIGGER IF EXISTS sync_merchant_region_on_district_update;
DROP TRIGGER IF EXISTS update_merchant_region_on_location_change;

-- 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.21.2', '移除旧region同步触发器');

COMMIT;

