-- 订阅验证配置标准化迁移
-- 目的：
-- 1) 若缺失则初始化 subscription_verification_config 配置（与最新代码一致）
-- 2) 若已存在则将旧键名统一为新键名（channel_id->chat_id, channel_name->display_name, channel_url->join_link）

-- 1) 初始化（若不存在则插入默认配置）
INSERT OR IGNORE INTO system_config (config_key, config_value, description)
VALUES (
  'subscription_verification_config',
  '{"enabled": false, "required_subscriptions": [], "verification_message": "请先订阅必需的频道", "bypass_for_premium": false}',
  '频道订阅验证配置'
);

-- 2) 统一旧键名为最新键名（仅当包含旧键时执行替换）
UPDATE system_config
SET config_value = REPLACE(config_value, '"channel_id"', '"chat_id"')
WHERE config_key = 'subscription_verification_config' AND instr(config_value, '"channel_id"') > 0;

UPDATE system_config
SET config_value = REPLACE(config_value, '"channel_name"', '"display_name"')
WHERE config_key = 'subscription_verification_config' AND instr(config_value, '"channel_name"') > 0;

UPDATE system_config
SET config_value = REPLACE(config_value, '"channel_url"', '"join_link"')
WHERE config_key = 'subscription_verification_config' AND instr(config_value, '"channel_url"') > 0;

