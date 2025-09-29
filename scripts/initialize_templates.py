#!/usr/bin/env python3
"""
模板初始化脚本
根据硬编码文本分析结果，批量创建所有必需的模板
"""

import asyncio
import logging
import os
import sys

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_templates import template_manager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 完整的模板字典 - 基于硬编码文本分析结果
COMPREHENSIVE_TEMPLATES = {
    # === 基础交互模板 ===
    'welcome_message': '👋 欢迎使用机器人！请选择您要使用的功能：',
    'help_message': 'ℹ️ 这里是帮助信息。使用 /start 查看主菜单。',
    'unknown_command': '❓ 抱歉，我不理解这个指令。请使用 /start 查看可用功能。',
    'system_initializing': '🔄 机器人正在初始化，请稍后再试...',
    
    # === 错误处理模板 ===
    'error_system': '❌ 系统发生错误，请稍后重试。',
    'error_general': '❌ 系统错误，请稍后重试或联系管理员。',
    'error_permission': '🚫 您没有权限执行此操作。',
    'error_not_authorized': '🚫 仅管理员可使用此功能。',
    'error_invalid_input': '⚠️ 输入格式不正确，请检查后重试。',
    'error_processing_failed': '❌ 处理失败，请重试',
    'error_operation_failed': '❌ 操作失败，请稍后重试',
    'error_unknown_operation': '❓ 未知操作',
    'error_insufficient_data': '⚠️ 请先添加至少一个按钮',
    'error_merchant_not_found': '❌ 商户不存在',
    'error_unknown_stats_type': '❌ 未知的统计类型',
    
    # === 绑定相关模板 ===
    'error_invalid_bind_code': '❌ 绑定码无效或已被使用。',
    'invalid_binding_code': '❌ 绑定码格式不正确。请输入8位大写字母和数字组成的绑定码。',
    'bind_success': '✅ 绑定成功！您的永久商户ID是 **{merchant_id}**。',
    'binding_success': '✅ 商户注册成功！请发送 /start 并点击“我的资料”查看与管理。',
    'binding_code_request': '🔑 要注册为商户，您需要一个绑定码。\n\n请联系管理员 {admin_username} 获取您的绑定码。',
    'binding_code_prompt': '请输入您的8位绑定码：',
    'quick_bind_success': '✅ 您已完成商户绑定！\n\n管理员正在为您完善商户信息，请耐心等待。',
    
    # === 商户状态相关模板 ===
    'merchant_already_registered': '您已经是注册商家，账户状态：{status_display}',
    'merchant_account_suspended': '您已经是注册商家，但账户已暂停。请联系管理员重新激活。',
    'merchant_registration_pending': '您的注册正在处理中，请稍候。',
    'merchant_not_registered': '❌ 您尚未注册为商户。\n发送 "上榜流程" 开始注册。',
    'merchant_panel_error': '❌ 获取面板信息失败，请稍后重试。',
    
    # === 商户面板模板 ===
    'merchant_panel_title': '🏢 商户面板',
    'merchant_panel_basic_info': '👤 基本信息：',
    'merchant_panel_status_desc': '📊 当前状态说明：',
    'merchant_panel_status_pending_submission': '• 您的账户已创建，等待完善信息\n• 管理员将协助您完成资料设置',
    'merchant_panel_status_pending_approval': '• 您的信息已提交，正在等待管理员审核',
    'merchant_panel_status_approved': '• 恭喜！您的信息已审核通过，即将发布',
    'merchant_panel_status_published': '• 您的商户信息已在频道发布，可正常接单',
    'merchant_panel_status_expired': '• 您的账户已暂停，请联系管理员重新激活',
    
    # === 用户资料相关模板 ===
    'user_welcome_message': '欢迎使用机器人！请选择您要使用的功能：',
    'user_no_profile': '您还没有个人资料，完成一次订单即可创建。',
    'user_profile_title': '👤 **我的资料**',
    'user_profile_level': '- **等级**: {level_name}',
    'user_profile_xp': '- **经验值 (XP)**: {xp}',
    'user_profile_points': '- **积分**: {points}',
    'user_profile_orders': '- **完成订单**: {order_count} 次',
    'user_profile_badges': '- **拥有勋章**: {badges_text}',
    'user_profile_card': (
        '👤 {username}    {level_name}\n'
        '═══════════════════════════\n\n'
        '    📊 成长值\n'
        '    🔥 XP: {xp}    💰 积分: {points}\n\n'
        '    🏆 战绩: {order_count} 胜\n\n'
        '    🏅 勋章: {badges_text}\n\n'
        '═══════════════════════════'
    ),
    
    # === 商户帮助信息模板 ===
    'merchant_help_welcome': '👋 欢迎使用商家服务！',
    'merchant_help_register': '🔹 如果您想注册成为商家：\n   发送：上榜流程',
    'merchant_help_existing': '🔹 如果您已是注册商家：\n   请发送 /start 并点击“我的资料”进行查看与管理\n   • 查看账户状态和信息\n   • 了解订单情况\n   • 联系客服支持',
    
    # === 绑定流程步骤模板 ===
    'binding_step_1_title': '👥 步骤 1/7: 选择商户类型',
    'binding_step_1_desc': '请选择您提供的服务类型：',
    'binding_step_2_title': '🏙️ 步骤 2/7: 选择城市',
    'binding_step_2_desc': '请选择您所在的城市：',
    'binding_step_3_title': '🌆 步骤 3/7: 选择地区',
    'binding_step_3_desc': '请选择您所在的地区：',
    'binding_step_4_title': '💰 步骤 4/7: 输入P价格',
    'binding_step_4_desc': '请输入您的P价格（数字）：',
    'binding_step_5_title': '💎 步骤 5/7: 输入PP价格',
    'binding_step_5_desc': '请输入您的PP价格（数字）：',
    'binding_step_6_title': '📝 步骤 6/7: 服务描述',
    'binding_step_6_desc': '请输入您的服务描述：',
    'binding_step_7_title': '🏷️ 步骤 7/7: 选择关键词',
    'binding_step_7_desc': '请选择相关的服务关键词（可多选）：',
    
    # === 绑定流程按钮模板 ===
    'binding_btn_teacher': '👩‍🏫 老师',
    'binding_btn_business': '🏢 商家',
    'binding_btn_cancel': '❌ 取消注册',
    'binding_btn_preview': '👁️ 预览并完成',
    'binding_btn_confirm': '✅ 确认注册',
    'binding_btn_restart': '🔄 重新填写',
    'binding_btn_continue': '✅ 确认并继续',
    'binding_btn_retry': '✏️ 重新输入',
    
    # === 绑定流程消息模板 ===
    'binding_cancelled': '❌ 注册已取消。',
    'binding_cancel_confirm': '注册已取消',
    'binding_preview_title': '📋 注册信息预览',
    'binding_preview_confirm': '请确认您的注册信息',
    'binding_completed': '🎉 注册信息收集完成！\n\n您的选择：\n{choices_text}\n\n注册成功！',
    'binding_completion_confirm': '注册完成！',
    'binding_restart_confirm': '已重置，请重新填写',
    'binding_step_confirmed': '已确认，进入下一步',
    'binding_all_completed': '所有步骤已完成！',
    'binding_confirm_failed': '确认处理失败，请重试',
    'binding_keyword_updated': '已更新关键词选择',
    'binding_selected': '已选择: {selected_value}',
    'binding_unknown_callback': '未知操作',
    'binding_callback_failed': '处理失败，请重试',
    
    # === 文本输入确认模板 ===
    'input_confirm_p_price': '✅ P价格已输入：{text}\n\n请确认是否继续下一步？',
    'input_confirm_pp_price': '✅ PP价格已输入：{text}\n\n请确认是否继续下一步？',
    'input_confirm_description': '✅ 商户描述已输入：{text}\n\n请确认是否继续下一步？',
    'input_processing_failed': '处理失败，请重试',
    
    # === 备用数据模板 ===
    'fallback_city_beijing': '北京市',
    'fallback_city_shanghai': '上海市',
    'fallback_city_guangdong': '广东省',
    'fallback_district_urban': '市区',
    'fallback_district_suburban': '郊区',
    'fallback_keyword_education': '📚 教育',
    'fallback_keyword_business': '💼 商务',
    'fallback_keyword_housekeeping': '🏠 家政',
    'fallback_keyword_art': '🎨 艺术',
    
    # === 自动回复相关模板 ===
    'auto_reply_not_initialized': '自动回复处理器未初始化',
    'auto_reply_stats_failed': '获取统计信息失败',
    'auto_reply_reload_success': '✅ 自动回复缓存已重新加载',
    'auto_reply_reload_failed': '❌ 重新加载缓存失败',
    
    # === 频道订阅验证模板 ===
    'subscription_required': '❌ 请先关注必需频道后再试',
    
    # === 管理员功能模板 ===
    'admin_welcome': '🔧 管理员面板已启用。',
    'admin_unauthorized': '🚫 仅管理员可使用此功能。',
    'admin_button_config_cancelled': '❌ 按钮配置已取消\n\n使用 /set_button 重新开始配置',
    'admin_stats_generating': '正在生成统计数据...',
    'admin_stats_failed': '生成统计数据失败，请重试',
    'admin_operation_confirmed': '已确认',
    'admin_operation_failed': '操作失败，请重试',
    'admin_preview_failed': '预览失败，请重试',
    'admin_save_failed': '保存配置失败，请重试',
    'admin_advanced_removed': '❌ 高级分析功能已移除',
    
    # === 操作成功模板 ===
    'success_operation': '✅ 操作成功！',
    'success_save': '✅ 保存成功！',
    'success_delete': '✅ 删除成功！',
    'success_confirmed': '✅ 已确认',
    
    # === 操作确认模板 ===
    'confirm_operation': '请确认操作',
    'confirm_continue': '是否继续？',
    'confirm_save_changes': '确认保存更改？',
    
    # === 通用按钮文本模板 ===
    'btn_confirm': '✅ 确认',
    'btn_cancel': '❌ 取消',
    'btn_back': '◀️ 返回',
    'btn_retry': '🔄 重试',
    'btn_continue': '➡️ 继续',
    'btn_save': '💾 保存',
    'btn_preview': '👁️ 预览',
    'btn_edit': '✏️ 编辑',
    'btn_delete': '🗑️ 删除',
    
    # === 状态信息模板 ===
    'status_processing': '🔄 正在处理...',
    'status_completed': '✅ 已完成',
    'status_pending': '⏳ 等待中',
    'status_failed': '❌ 失败',
    'status_cancelled': '❌ 已取消',
    
    # === 数据错误模板 ===
    'data_loading_failed': '数据加载失败',
    'data_not_found': '未找到相关数据',
    'data_invalid_format': '数据格式错误',
    'data_save_failed': '数据保存失败',
    
    # === 日志记录相关模板 ===
    'log_user_action': '用户操作记录',
    'log_admin_action': '管理员操作记录',
    'log_system_event': '系统事件记录',
    'log_error_event': '错误事件记录',
}

async def initialize_all_templates():
    """初始化所有模板到数据库"""
    try:
        logger.info("开始初始化模板...")
        
        # 批量创建模板
        created_count = await template_manager.bulk_create_templates(COMPREHENSIVE_TEMPLATES)
        
        logger.info(f"模板初始化完成！创建了 {created_count} 个新模板")
        
        # 获取统计信息
        stats = await template_manager.get_template_statistics()
        logger.info(f"数据库模板统计: {stats}")
        
        return created_count
        
    except Exception as e:
        logger.error(f"初始化模板失败: {e}")
        return 0

async def verify_templates():
    """验证模板完整性"""
    try:
        logger.info("开始验证模板完整性...")
        
        missing_templates = []
        
        for key in COMPREHENSIVE_TEMPLATES.keys():
            if not await template_manager.template_exists(key):
                missing_templates.append(key)
        
        if missing_templates:
            logger.warning(f"发现 {len(missing_templates)} 个缺失的模板: {missing_templates}")
            return False
        else:
            logger.info("所有模板验证通过！")
            return True
            
    except Exception as e:
        logger.error(f"验证模板失败: {e}")
        return False

async def main():
    """主函数"""
    try:
        logger.info("=== 模板初始化脚本开始 ===")
        
        # 初始化模板
        created_count = await initialize_all_templates()
        
        # 验证模板
        verification_passed = await verify_templates()
        
        logger.info("=== 模板初始化脚本完成 ===")
        logger.info(f"创建模板数量: {created_count}")
        logger.info(f"验证结果: {'通过' if verification_passed else '失败'}")
        
        return verification_passed
        
    except Exception as e:
        logger.error(f"脚本执行失败: {e}")
        return False

if __name__ == "__main__":
    # 运行初始化脚本
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
