-- 迁移：补齐初始模板键（幂等）
-- 版本：2025.09.19.5

-- 确保 templates 表存在（若不存在，迁移会失败，需先执行基础 schema）

INSERT OR IGNORE INTO templates (key, content) VALUES
('binding_code_prompt', '🔑 请输入您的绑定码：'),
('error_general', '❌ 系统暂时无法处理您的请求。请稍后重试。'),
('binding_code_request', '🔑 要上榜，您需要一个绑定码。请联系管理员获取您的绑定码。'),
('invalid_binding_code', '❌ 绑定码无效或已过期。请联系管理员获取新的绑定码。'),
('merchant_info_template', '📋 {name}\n📍 地区: {province} - {region}\n💰 价格: P{p_price} | PP{pp_price}'),
('binding_success', '🎉 注册成功！您的商户资料已成功创建并激活。'),
('binding_btn_preview', '📋 预览信息'),
('merchant_registration_pending', '⏳ 您的注册正在处理中，请稍候。'),
('binding_callback_failed', '处理失败，请重试'),
('system_initializing', '系统初始化中，请稍候…'),
('quick_bind_success', '绑定成功！系统将引导你完善资料。'),
('merchant_already_registered', '您已注册，当前状态：{status_display}'),
('merchant_account_suspended', '您的账号已被暂停，请联系管理员。'),
('merchant_not_registered', '您还不是商户，请先发送“上榜流程”并完成绑定。'),
('error_system', '❌'),
('merchant_panel_title', '商户面板'),
('merchant_panel_basic_info', '基本信息'),
('merchant_panel_status_desc', '状态说明'),
('merchant_panel_status_pending_submission', '请在机器人中继续完善信息后再提交审核。'),
('merchant_panel_status_pending_approval', '资料已提交，等待管理员审核。'),
('merchant_panel_status_approved', '已审核通过，等待发布。'),
('merchant_panel_status_published', '已发布，当前活跃。'),
('merchant_panel_status_expired', '已过期或被暂停。'),
('merchant_panel_error', '获取商户面板信息失败，请稍后重试。'),
('merchant_help_welcome', '👋 欢迎使用商户助手。'),
('merchant_help_register', '发送“上榜流程”开始注册，或输入绑定码完成绑定。'),
('merchant_help_existing', '已注册商户可发送“商户面板”查看状态与管理。'),
('admin_unauthorized', '❌ 你没有管理员权限。'),
('admin_help', '管理员命令：/set_button /help 等。'),
('status_cancelled', '❌ 操作已取消。'),
('user_welcome_message', '👋 欢迎！这是你的主菜单。'),
('user_no_profile', 'ℹ️ 暂无个人资料，请先完善信息。'),
('data_invalid_format', '格式错误'),
('user_profile_title', '📋 用户资料'),
('user_profile_level', '等级：{level_name}'),
('user_profile_xp', '经验值：{xp}'),
('user_profile_points', '积分：{points}'),
('user_profile_orders', '完成订单：{order_count}'),
('user_profile_badges', '勋章：{badges_text}');

-- 同步 schema_version 到 2025.09.19.5（如果需要）
INSERT OR REPLACE INTO system_config (config_key, config_value, description)
VALUES ('schema_version', '2025.09.19.5', '数据库架构版本');

