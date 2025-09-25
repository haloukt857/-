-- 模板数据初始化脚本
-- 确保所有必需的模板在数据库中存在
-- 注意：只插入templates表实际存在的字段 (key, content)

INSERT OR IGNORE INTO templates (key, content) VALUES

-- 管理员消息模板
('admin_help', '
🔧 管理员命令:

/set_button - 配置自定义消息和按钮
/view_stats - 查看点击和交互统计
/generate_code - 生成商户绑定码
/help - 显示此帮助信息
    '),
('admin_unauthorized', '🚫 仅管理员可使用此功能。'),

-- 绑定流程核心模板
('binding_code_request', '🔑 要上榜，您需要一个绑定码。

请联系管理员 @{admin_username} 获取您的绑定码。'),

('binding_code_prompt', '
🔑 请输入您的绑定码：
    '),

('binding_success', '🎉 **注册成功！**

✅ 恭喜！您的商户资料已成功创建并激活。

📋 **商户信息概览:**
👤 商户名称: {name}
🏷️ 商户类型: {merchant_type}
📍 服务地区: {province} - {region}
💰 服务价格: P{p_price} | PP{pp_price}

🔔 **重要提醒:**
• 现在您可以通过机器人接收客户咨询
• 客户可通过分享链接找到您的服务
• 请保持联系方式畅通以便客户联系'),

('invalid_binding_code', '❌ 绑定码无效或已过期。请联系管理员获取新的绑定码。'),

-- 商家信息模板
('merchant_info_template', '📋 **{name}** ({merchant_type})

📍 **地区**: {province} - {region}
💰 **价格**: P{p_price} | PP{pp_price}

📝 **介绍**: {custom_description}

🏷️ **特色标签**: {keywords}

📞 **联系方式**: {contact_info}'),

('merchant_info_simple', '📋 **{name}** ({merchant_type})
📍 {province} - {region} | 💰 P{p_price}/PP{pp_price}
🏷️ {keywords}
📞 {contact_info}'),

-- 频道贴文模板（含deeplink HTML，占位符已经预组装HTML片段）
('channel_post_template', '{adv_html}

💃🏻昵称：{nickname_html}
🌈地区：{district_html}
🎫课费：{price_p_html}      {price_pp_html}
🏷️标签：{tags_html}
✍️评价：「{report_html}」

🎉优惠：{offer_html}'),

('merchant_welcome', '🏪 欢迎来到商户注册系统！

要开始注册，请发送"上榜流程"来开始注册过程。'),

-- 订单相关模板
('order_confirmation_user', '🎉 **订单已确认！**

✅ 您的 {service_type} 请求已成功发送给商户。

📋 **订单详情:**
🏷️ 服务类型: {service_type}
👤 商户名称: {name}
📍 服务地区: {province} - {region}
💰 服务价格: P{p_price} | PP{pp_price}

📞 **联系信息:**
{merchant_contact}

⏱️ **重要提醒:**
• 商户将在24小时内主动联系您
• 请保持电话畅通，方便安排服务时间
• 如有疑问可直接联系上述联系方式'),

('order_notification_merchant', '🔔 **新订单通知**

👤 **客户:** {username} {user_handle}
📅 **时间:** {order_time}
🛍️ **服务:** {service_type}
💰 **价格:** {price}

请联系客户安排服务。'),

-- 错误消息模板
('error_general', '❌ 系统暂时无法处理您的请求。请稍后重试。

如需帮助请联系客服。'),

('error_merchant_not_found', '❌ 未找到商户。请检查链接并重试。'),

('error_database', '❌ **数据库错误**

系统暂时无法处理您的请求。请稍后重试。

如果问题持续存在，请联系管理员。'),

-- 历史键 welcome_private 已淘汰，统一使用 user_* 标准键名

-- 绑定流程步骤模板
('merchant_type_selection', '🏪 **步骤 1/7: 选择商家类型**

请选择您要注册的商家类型：

每种类型提供不同的服务模式和功能。选择最符合您业务需求的类型。'),

('province_selection', '🌍 **步骤 2/7: 选择省份**

请选择您的商户所在省份：

我们会根据地区为您提供本地化的服务和推荐。'),

('region_selection', '🏙️ **步骤 3/7: 选择区域**

您选择的省份: {province_name}

请选择您的具体所在区域：'),

('p_price_input', '💰 **步骤 4/7: 设置P价格**

请输入您的P价格（主要服务价格）：

💡 **输入说明：**
• 请输入数字金额（如：100）
• 支持小数点（如：99.5）
• 这将作为您的主要服务定价'),

('pp_price_input', '💎 **步骤 5/7: 设置PP价格**

您的P价格: ¥{p_price}

请输入您的PP价格（高级服务价格）：

💡 **输入说明：**
• 请输入数字金额（如：200）
• 支持小数点（如：199.5）
• 这将作为您的高级服务定价
• 通常PP价格高于P价格'),

('custom_description_input', '📝 **步骤 6/7: 自定义描述**

请输入您的商户自定义描述：

💡 **描述建议：**
• 介绍您的主要服务和特色
• 可以包含联系方式或营业时间
• 不超过200个字符
• 这将显示在您的商户信息中

发送您的描述内容，或发送"跳过"使用默认描述。'),

('keyword_selection', '🏷️ **步骤 7/7: 选择关键词**

请选择适合您商户的关键词标签（可多选）：

已选择关键词: {selected_keywords}

💡 **选择建议：**
• 选择与您服务相关的关键词
• 多个关键词有助于客户找到您
• 点击关键词进行选择/取消选择
• 选择完成后点击"完成选择"'),

('binding_confirmation', '✅ **注册信息确认**

请确认以下信息是否正确：

👤 **商户类型**: {merchant_type}
📍 **地区**: {province} - {region}
💰 **P价格**: ¥{p_price}
💎 **PP价格**: ¥{pp_price}
📝 **描述**: {description}
🏷️ **关键词**: {keywords}

🔍 **用户检测结果**: {user_analysis}

确认无误请点击"确认注册"，需要修改请点击"重新填写"。'),

-- 商户订单通知模板已存在，移除重复定义

-- 用户中心与通用数据校验模板（标准前缀 user_*）
('user_welcome_message','👋 欢迎！这是你的主菜单。'),
('user_no_profile','ℹ️ 暂无个人资料，请先完善信息。'),
('data_invalid_format','格式错误'),
('user_profile_title','📋 用户资料'),
('user_profile_level','等级：{level_name}'),
('user_profile_xp','经验值：{xp}'),
('user_profile_points','积分：{points}'),
('user_profile_orders','完成订单：{order_count}'),
('user_profile_badges','勋章：{badges_text}');
