-- migration_2025_09_22_4_补建merchants更新时间触发器.sql
-- 描述: 补建 merchants 表的更新时间触发器，避免上一版拆分执行导致触发器未创建。

BEGIN TRANSACTION;
DROP TRIGGER IF EXISTS update_merchants_timestamp;
CREATE TRIGGER IF NOT EXISTS update_merchants_timestamp 
    AFTER UPDATE ON merchants
    FOR EACH ROW
    BEGIN
        UPDATE merchants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
COMMIT;

INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.22.4', '补建 merchants 更新时间触发器');

