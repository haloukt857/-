-- migration_2025_09_06_3_清理模板格式_移除所有Markdown双星号格式.sql
-- 描述: 清理模板格式-移除所有Markdown双星号格式  
-- 前置版本: 2025.09.06.2
-- 目标版本: 2025.09.06.3
-- 生成时间: 2025-09-06T02:23:34.635990

-- 向前迁移 (UP)
-- 清理templates表中的所有Markdown双星号格式

-- 清理admin_help模板
UPDATE templates SET content = REPLACE(content, '🔧 **管理员命令:**', '🔧 管理员命令:') 
WHERE key = 'admin_help';

-- 清理admin_new_merchant_notification模板  
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(content, '🏪 **新商户注册通知**', '🏪 新商户注册通知'),
                '📅 **注册时间**:', '📅 注册时间:'
            ),
            '👤 **商户信息**:', '👤 商户信息:'
        ),
        '🤖 **用户检测结果**:', '🤖 用户检测结果:'
    ),
    '💡 **检测详情**:', '💡 检测详情:'
) WHERE key = 'admin_new_merchant_notification';

-- 清理binding_confirmation模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(content, '✅ **注册信息确认**', '✅ 注册信息确认'),
                                '👤 **商户类型**:', '👤 商户类型:'
                            ),
                            '📍 **地区**:', '📍 地区:'
                        ),
                        '💰 **P价格**:', '💰 P价格:'
                    ),
                    '💎 **PP价格**:', '💎 PP价格:'
                ),
                '📝 **描述**:', '📝 描述:'
            ),
            '🏷️ **关键词**:', '🏷️关键词:'
        ),
        '🔍 **用户检测结果**:', '🔍 用户检测结果:'
    )
) WHERE key = 'binding_confirmation';

-- 清理binding_flow_complete模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(content, '🎉 **注册完成！**', '🎉 注册完成！'),
                    '📋 **您的商户信息:**', '📋 您的商户信息:'
                ),
                '👤 **类型**:', '👤 类型:'
            ),
            '📍 **地区**:', '📍 地区:'
        ),
        '💰 **价格**:', '💰 价格:'
    ),
    '🚀 **接下来您可以:**', '🚀 接下来您可以:'
) WHERE key = 'binding_flow_complete';

-- 清理binding_success模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(content, '🎉 **注册成功！**', '🎉 注册成功！'),
        '📋 **商户信息概览:**', '📋 商户信息概览:'
    ),
    '🔔 **重要提醒:**', '🔔 重要提醒:'
) WHERE key = 'binding_success';

-- 清理bot_detection_warning模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(content, '⚠️ **账号检测警告**', '⚠️ 账号检测警告'),
        '🤖 **检测结果**:', '🤖 检测结果:'
    ),
    '📝 **检测原因**:', '📝 检测原因:'
) WHERE key = 'bot_detection_warning';

-- 清理channel_info_display模板
UPDATE templates SET content = REPLACE(content, '📺 **{channel_name}**', '📺 {channel_name}') 
WHERE key = 'channel_info_display';

-- 清理custom_description_input模板
UPDATE templates SET content = REPLACE(
    REPLACE(content, '📝 **步骤 6/7: 自定义描述**', '📝 步骤 6/7: 自定义描述'),
    '💡 **描述建议：**', '💡 描述建议：'
) WHERE key = 'custom_description_input';

-- 清理description_too_long模板
UPDATE templates SET content = REPLACE(content, '❌ **描述过长**', '❌ 描述过长') 
WHERE key = 'description_too_long';

-- 清理error_binding_flow模板
UPDATE templates SET content = REPLACE(content, '❌ **绑定流程错误**', '❌ 绑定流程错误') 
WHERE key = 'error_binding_flow';

-- 清理error_database模板
UPDATE templates SET content = REPLACE(content, '❌ **数据库错误**', '❌ 数据库错误') 
WHERE key = 'error_database';

-- 清理invalid_price_format模板
UPDATE templates SET content = REPLACE(content, '❌ **价格格式错误**', '❌ 价格格式错误') 
WHERE key = 'invalid_price_format';

-- 清理keyword_selection模板
UPDATE templates SET content = REPLACE(
    REPLACE(content, '🏷️ **步骤 7/7: 选择关键词**', '🏷️ 步骤 7/7: 选择关键词'),
    '💡 **选择建议：**', '💡 选择建议：'
) WHERE key = 'keyword_selection';

-- 清理merchant_info_simple模板
UPDATE templates SET content = REPLACE(content, '📋 **{name}**', '📋 {name}') 
WHERE key = 'merchant_info_simple';

-- 清理merchant_info_template模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(content, '📋 **{name}**', '📋 {name}'),
                    '📍 **地区**:', '📍 地区:'
                ),
                '💰 **价格**:', '💰 价格:'
            ),
            '📝 **介绍**:', '📝 介绍:'
        ),
        '🏷️ **特色标签**:', '🏷️ 特色标签:'
    ),
    '📞 **联系方式**:', '📞 联系方式:'
) WHERE key = 'merchant_info_template';

-- 清理merchant_type_selection模板
UPDATE templates SET content = REPLACE(content, '🏪 **步骤 1/7: 选择商家类型**', '🏪 步骤 1/7: 选择商家类型') 
WHERE key = 'merchant_type_selection';

-- 清理order_confirmation_user模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(content, '🎉 **订单已确认！**', '🎉 订单已确认！'),
            '📋 **订单详情:**', '📋 订单详情:'
        ),
        '📞 **联系信息:**', '📞 联系信息:'
    ),
    '⏱️ **重要提醒:**', '⏱️ 重要提醒:'
) WHERE key = 'order_confirmation_user';

-- 清理order_notification_merchant模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(content, '🔔 **新订单通知**', '🔔 新订单通知'),
                '👤 **客户:**', '👤 客户:'
            ),
            '📅 **时间:**', '📅 时间:'
        ),
        '🛍️ **服务:**', '🛍️ 服务:'
    ),
    '💰 **价格:**', '💰 价格:'
) WHERE key = 'order_notification_merchant';

-- 清理p_price_input模板
UPDATE templates SET content = REPLACE(
    REPLACE(content, '💰 **步骤 4/7: 设置P价格**', '💰 步骤 4/7: 设置P价格'),
    '💡 **输入说明：**', '💡 输入说明：'
) WHERE key = 'p_price_input';

-- 清理pp_price_input模板
UPDATE templates SET content = REPLACE(
    REPLACE(content, '💎 **步骤 5/7: 设置PP价格**', '💎 步骤 5/7: 设置PP价格'),
    '💡 **输入说明：**', '💡 输入说明：'
) WHERE key = 'pp_price_input';

-- 清理province_selection模板
UPDATE templates SET content = REPLACE(content, '🌍 **步骤 2/7: 选择省份**', '🌍 步骤 2/7: 选择省份') 
WHERE key = 'province_selection';

-- 清理region_selection模板
UPDATE templates SET content = REPLACE(content, '🏙️ **步骤 3/7: 选择区域**', '🏙️ 步骤 3/7: 选择区域') 
WHERE key = 'region_selection';

-- 清理stats_template模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(content, '📊 **机器人统计**', '📊 机器人统计'),
                        '📅 **时间段:**', '📅 时间段:'
                    ),
                    '👥 **总用户数:**', '👥 总用户数:'
                ),
                '🔘 **按钮点击数:**', '🔘 按钮点击数:'
            ),
            '📝 **创建订单数:**', '📝 创建订单数:'
        ),
        '🏪 **活跃商户数:**', '🏪 活跃商户数:'
    ),
    '**热门按钮:**', '热门按钮:'
) WHERE key = 'stats_template';

-- 清理user_analysis_summary模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(content, '📊 **用户分析报告**', '📊 用户分析报告'),
                '🔍 **检测结果**:', '🔍 检测结果:'
            ),
            '📈 **置信度**:', '📈 置信度:'
        ),
        '🎯 **综合评分**:', '🎯 综合评分:'
    ),
    '💡 **建议**:', '💡 建议:'
) WHERE key = 'user_analysis_summary';

-- 清理user_info_detection模板
UPDATE templates SET content = REPLACE(
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(content, '🔍 **用户信息检测**', '🔍 用户信息检测'),
                '👤 **用户名**:', '👤 用户名:'
            ),
            '📝 **姓名**:', '📝 姓名:'
        ),
        '📊 **账号类型**:', '📊 账号类型:'
    ),
    '🤖 **机器人概率**:', '🤖 机器人概率:'
) WHERE key = 'user_info_detection';

-- 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description) 
VALUES ('schema_version', '2025.09.06.3', '清理模板格式-移除所有Markdown双星号格式');

-- 向后迁移 (DOWN) - 可选，用于回滚
-- 取消注释并添加回滚逻辑
-- UPDATE system_config SET config_value = '2025.09.06.2' WHERE config_key = 'schema_version';
