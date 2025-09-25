#!/usr/bin/env python3
"""
测试模板重构后的功能
验证重构后的代码是否能正常获取模板内容
"""

import asyncio
import logging
import sys
import os

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_templates import template_manager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_core_templates():
    """测试核心模板获取"""
    logger.info("测试核心模板获取...")
    
    test_cases = [
        # 基础交互模板
        'welcome_message',
        'system_initializing',
        'error_general',
        
        # 商户相关模板
        'merchant_not_registered',
        'merchant_panel_title',
        'quick_bind_success',
        
        # 用户相关模板
        'user_welcome_message',
        'user_no_profile',
        'user_profile_title',
        
        # 管理员模板
        'admin_unauthorized',
        'admin_operation_failed',
        
        # 绑定流程模板
        'binding_btn_cancel',
        'binding_callback_failed',
    ]
    
    results = {}
    for template_key in test_cases:
        try:
            content = await template_manager.get_template(template_key)
            results[template_key] = {
                'success': True,
                'content': content[:50] + '...' if len(content) > 50 else content,
                'length': len(content)
            }
            logger.info(f"✅ {template_key}: {content[:30]}...")
        except Exception as e:
            results[template_key] = {
                'success': False,
                'error': str(e)
            }
            logger.error(f"❌ {template_key}: {e}")
    
    return results

async def test_template_formatting():
    """测试模板格式化功能"""
    logger.info("测试模板格式化功能...")
    
    test_cases = [
        {
            'key': 'merchant_already_registered',
            'format_args': {'status_display': '已激活'},
            'expected_in': '已激活'
        },
        {
            'key': 'user_profile_level',
            'format_args': {'level_name': '新手'},
            'expected_in': '新手'
        },
        {
            'key': 'binding_selected',
            'format_args': {'selected_value': '测试选项'},
            'expected_in': '测试选项'
        }
    ]
    
    results = {}
    for test_case in test_cases:
        try:
            template = await template_manager.get_template(test_case['key'])
            formatted = template.format(**test_case['format_args'])
            
            success = test_case['expected_in'] in formatted
            results[test_case['key']] = {
                'success': success,
                'formatted': formatted[:50] + '...' if len(formatted) > 50 else formatted,
                'contains_expected': success
            }
            
            if success:
                logger.info(f"✅ {test_case['key']}: 格式化成功")
            else:
                logger.warning(f"⚠️ {test_case['key']}: 格式化结果未包含预期内容")
                
        except Exception as e:
            results[test_case['key']] = {
                'success': False,
                'error': str(e)
            }
            logger.error(f"❌ {test_case['key']}: {e}")
    
    return results

async def test_fallback_behavior():
    """测试回退行为"""
    logger.info("测试回退行为...")
    
    # 测试不存在的模板
    try:
        content = await template_manager.get_template('non_existent_template')
        logger.info(f"模板不存在时的回退: {content}")
        fallback_success = '[模板缺失:' in content
    except Exception as e:
        logger.error(f"回退测试失败: {e}")
        fallback_success = False
    
    # 测试带默认值的获取
    try:
        content = await template_manager.get_template('non_existent_template', '默认内容')
        logger.info(f"带默认值的回退: {content}")
        default_success = content == '默认内容'
    except Exception as e:
        logger.error(f"默认值测试失败: {e}")
        default_success = False
    
    return {
        'fallback_behavior': fallback_success,
        'default_value_behavior': default_success
    }

async def main():
    """主测试函数"""
    logger.info("=== 模板重构测试开始 ===")
    
    try:
        # 测试核心模板
        core_results = await test_core_templates()
        
        # 测试格式化功能
        format_results = await test_template_formatting()
        
        # 测试回退行为
        fallback_results = await test_fallback_behavior()
        
        # 汇总结果
        total_tests = len(core_results) + len(format_results) + 2
        successful_tests = (
            sum(1 for r in core_results.values() if r['success']) +
            sum(1 for r in format_results.values() if r['success']) +
            sum(1 for r in fallback_results.values() if r)
        )
        
        success_rate = (successful_tests / total_tests) * 100
        
        logger.info("=== 测试结果汇总 ===")
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"成功测试数: {successful_tests}")
        logger.info(f"成功率: {success_rate:.1f}%")
        
        if success_rate >= 90:
            logger.info("🎉 测试通过！模板重构成功！")
            return True
        else:
            logger.warning("⚠️ 部分测试失败，需要检查问题")
            return False
            
    except Exception as e:
        logger.error(f"测试过程出现异常: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)