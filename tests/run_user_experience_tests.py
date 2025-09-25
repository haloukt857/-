#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户体验测试运行器

使用方法:
    python tests/run_user_experience_tests.py

功能:
- 运行完整的用户体验测试套件
- 生成详细的测试报告
- 输出测试日志和结果统计

作者: QA测试引擎
日期: 2025-09-13
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'tests/user_experience_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """主测试运行函数"""
    logger.info("🚀 启动用户体验测试套件")
    
    try:
        # 导入测试类
        from tests.integration.test_user_experience import TestUserExperience
        
        # 创建测试实例
        test_runner = TestUserExperience()
        
        # 运行所有测试
        start_time = datetime.now()
        test_results = await test_runner.run_all_tests()
        end_time = datetime.now()
        
        # 生成最终报告
        duration = end_time - start_time
        logger.info(f"\n🏁 测试完成，总耗时: {duration}")
        
        # 统计结果
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results.values() if result['status'] == 'PASSED')
        failed_tests = sum(1 for result in test_results.values() if result['status'] == 'FAILED')
        error_tests = sum(1 for result in test_results.values() if result['status'] == 'ERROR')
        
        # 输出最终统计
        print("\n" + "="*80)
        print("📊 Telegram商户机器人V2.0 - 用户体验测试最终报告")
        print("="*80)
        print(f"测试执行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%H:%M:%S')}")
        print(f"测试总耗时: {duration}")
        print(f"总测试用例: {total_tests}")
        print(f"✅ 通过: {passed_tests}")
        print(f"❌ 失败: {failed_tests}")
        print(f"💥 异常: {error_tests}")
        print(f"🎯 成功率: {(passed_tests/total_tests)*100:.1f}%")
        print("="*80)
        
        # 详细结果
        print("\n📋 测试用例详情:")
        for test_name, result in test_results.items():
            status_symbol = {
                'PASSED': '✅',
                'FAILED': '❌', 
                'ERROR': '💥'
            }[result['status']]
            
            print(f"{status_symbol} {test_name}: {result['status']}")
            if 'error' in result:
                print(f"   🔍 错误详情: {result['error']}")
        
        print("="*80)
        
        # 关键发现和建议
        print("\n🔍 关键发现:")
        if passed_tests == total_tests:
            print("🎉 所有测试用例通过！用户体验功能完整且稳定。")
        else:
            print(f"⚠️  发现 {failed_tests + error_tests} 个问题需要关注：")
            
            failed_tests_list = [name for name, result in test_results.items() 
                               if result['status'] in ['FAILED', 'ERROR']]
            for test_name in failed_tests_list:
                print(f"   • {test_name}")
        
        print("\n📈 用户体验质量评估:")
        if (passed_tests/total_tests) >= 0.9:
            print("🌟 优秀 - 用户体验质量优异，可以投入生产使用")
        elif (passed_tests/total_tests) >= 0.7:
            print("👍 良好 - 用户体验基本满足要求，建议优化失败项")
        elif (passed_tests/total_tests) >= 0.5:
            print("⚠️  一般 - 用户体验存在明显问题，需要重点改进")
        else:
            print("🚨 需要改进 - 用户体验严重不足，不建议发布")
        
        print("\n🛠️  建议:")
        print("1. 重点关注失败的测试用例，确保核心功能稳定")
        print("2. 验证数据库连接和数据一致性")
        print("3. 测试真实用户交互场景")
        print("4. 监控系统性能和并发处理能力")
        print("5. 定期运行测试确保功能回归")
        
        print("="*80)
        
        # 退出码
        exit_code = 0 if failed_tests + error_tests == 0 else 1
        logger.info(f"测试运行器退出，退出码: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.error(f"测试运行器异常: {e}")
        print(f"\n💥 测试运行器异常: {e}")
        return 2

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)