-- migration_2025_09_22_6_修复频道模板换行符.sql
-- 描述: 将 channel_post_template 中的字面 "\n" 改为真实换行，确保预览与发送显示正常。

BEGIN TRANSACTION;

UPDATE templates
SET content = REPLACE(REPLACE(REPLACE(content, '\r\n', CHAR(10)), '\n', CHAR(10)), '\t', CHAR(9))
WHERE key = 'channel_post_template';

COMMIT;

INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.22.6', '修复频道模板换行符');

