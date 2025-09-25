-- 补充商户注册与面板提示模板（避免Bot端模板缺失）

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_registration_pending', '您的注册正在处理中，请稍候。');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_panel_status_desc', '📊 当前状态说明：');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_panel_status_pending_submission', '• 您的账户已创建，等待完善信息\n• 管理员将协助您完成资料设置');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_panel_status_pending_approval', '• 您的信息已提交，正在等待管理员审核');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_panel_status_approved', '• 恭喜！您的信息已审核通过，即将发布');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_panel_status_published', '• 您的商户信息已在频道发布，可正常接单');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_panel_status_expired', '• 您的账户已暂停，请联系管理员重新激活');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_help_welcome', '👋 欢迎使用商家服务！');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_help_register', '🔹 如果您想注册成为商家：\n   发送：上榜流程');

INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_help_existing', '🔹 如果您已是注册商家：\n   发送：/panel 或 面板 - 查看商户面板\n   • 查看账户状态和信息\n   • 了解订单情况\n   • 联系客服支持');

