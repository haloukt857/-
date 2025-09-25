-- 补充管理员相关模板（生产/本地统一通过迁移落库）
-- 说明：避免运行时多重兜底，使用迁移作为唯一数据修复路径

INSERT OR IGNORE INTO templates (key, content) VALUES
('admin_help', '🔧 管理员命令:\n\n/set_button - 配置自定义消息和按钮\n/view_stats - 查看点击和交互统计\n/generate_code - 生成商户绑定码\n/help - 显示此帮助信息');

INSERT OR IGNORE INTO templates (key, content) VALUES
('admin_unauthorized', '🚫 仅管理员可使用此功能。');

