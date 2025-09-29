-- 迁移：新增用户单键资料模板 user_profile_card（若不存在则创建）
-- 版本：2025.09.29.2

INSERT OR IGNORE INTO templates (key, content) VALUES (
  'user_profile_card',
  '👤 我的资料\n- 用户名: {username}\n- 等级: {level_name}\n- 经验值: {xp}\n- 积分: {points}\n- 完成订单: {order_count} 次\n- 勋章: {badges_text}\n- 注册时间: {created_at}'
);

-- 可选：同步 schema 版本记录（若项目使用）
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.29.2', '新增 user_profile_card 模板');

