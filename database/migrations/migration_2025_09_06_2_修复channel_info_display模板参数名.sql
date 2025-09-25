-- migration_2025_09_06_2_修复channel_info_display模板参数名.sql
-- 描述: 修复channel_info_display模板参数名  
-- 前置版本: 2025.09.06.1
-- 目标版本: 2025.09.06.2
-- 生成时间: 2025-09-06T01:37:23.107798

-- 向前迁移 (UP)
-- 修复channel_info_display模板，将{merchant_name}改为{channel_name}，与生产环境保持一致

-- 更新channel_info_display模板内容，匹配生产环境迁移文件中的定义
UPDATE templates SET content = '📺 **{channel_name}**

🔗 [点击关注频道]({channel_link})

关注我们的官方频道，获取最新资讯和优惠信息！'
WHERE key = 'channel_info_display';

-- 如果模板不存在则插入（防御性编程）
INSERT OR IGNORE INTO templates (key, content) VALUES 
('channel_info_display', '📺 **{channel_name}**

🔗 [点击关注频道]({channel_link})

关注我们的官方频道，获取最新资讯和优惠信息！');

-- 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description) 
VALUES ('schema_version', '2025.09.06.2', '修复channel_info_display模板参数名');

-- 向后迁移 (DOWN) - 可选，用于回滚
-- 取消注释并添加回滚逻辑
-- UPDATE system_config SET config_value = '2025.09.06.1' WHERE config_key = 'schema_version';
