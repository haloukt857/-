-- 绑定码表增加隐藏周期字段（用于发布后自动计算到期日）
ALTER TABLE binding_codes ADD COLUMN plan_days INTEGER;
ALTER TABLE binding_codes ADD COLUMN plan_tag TEXT;

-- 迁移版本记录
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.25.1', '绑定码增加plan_days/plan_tag');

