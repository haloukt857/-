-- migration_2025_09_01_1_完整修复Railway部署问题_订单筛选_模板数据_错误消息_JavaScript等.sql
-- 描述: 完整修复Railway部署问题：订单筛选、模板数据、错误消息、JavaScript等  
-- 前置版本: 2025.09.01.1
-- 目标版本: 2025.09.01.1
-- 生成时间: 2025-09-01T12:10:13.199425

-- 向前迁移 (UP)
-- 完整修复Railway部署问题：确保所有关键模板存在

-- 1. 确保关键模板数据存在（INSERT OR IGNORE防止重复）
INSERT OR IGNORE INTO templates (key, content) VALUES
('merchant_info_template', '📋 {name} ({merchant_type})

📍 地区: {province} - {region}
💰 价格: P{p_price} | PP{pp_price}

📝 介绍: {custom_description}

🏷️ 特色标签: {keywords}

📞 联系方式: {contact_info}'),

('order_notification_merchant', '🔔 **新订单通知**

👤 **用户**: {customer_name}
📱 **ID**: {customer_id}  
🛍️ **订单**: {order_description}
📞 **联系**: {customer_contact}
💰 **金额**: {amount}

⏰ **时间**: {order_time}
📋 **备注**: {notes}

请及时处理此订单！'),

('merchant_welcome', '🎉 **欢迎加入商户平台！**

您的商户信息已成功录入系统。
📋 **商户名**: {name}
🏷️ **类型**: {merchant_type}
🗺️ **地区**: {region}

✅ 现在用户可以通过搜索找到您的商户信息
💡 如需修改信息，请联系管理员'),

('binding_success_admin', '✅ **商户绑定成功**

🏪 **商户**: {merchant_name}
👤 **用户**: {user_name} (ID: {user_id})
🔑 **绑定码**: {binding_code}
📱 **联系**: {contact}
⏰ **时间**: {binding_time}'),

('order_received', '✅ **订单已收到**

感谢您的订单！商户已收到通知。
📋 **订单详情**: {order_description}
⏰ **提交时间**: {order_time}

商户会尽快与您联系，请保持电话畅通。'),

('error_template', '❌ **操作失败**

{error_message}

如需帮助，请联系管理员。'),

('channel_info_display', '📺 **{channel_name}**

🔗 [点击关注频道]({channel_link})

关注我们的官方频道，获取最新资讯和优惠信息！');

-- 2. 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description) 
VALUES ('schema_version', '2025.09.01.3', '强制执行模板迁移：添加channel_info_display模板');

-- 向后迁移 (DOWN) - 可选，用于回滚
-- 取消注释并添加回滚逻辑
-- UPDATE system_config SET config_value = '2025.09.01.1' WHERE config_key = 'schema_version';
