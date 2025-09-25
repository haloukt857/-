#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合测试系统使用示例

演示如何使用Telegram商户机器人V2.0综合测试系统的各种功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.config.test_config import TestConfig, ConfigTemplates
from tests.utils.test_helpers import TestResultCollector, TestReporter, PerformanceMonitor
from tests.run_comprehensive_tests import ComprehensiveTestRunner


async def example_basic_usage():
    """基础使用示例"""
    print("🧪 基础使用示例")
    print("-" * 50)
    
    # 1. 创建默认配置的测试运行器
    runner = ComprehensiveTestRunner()
    
    # 2. 运行环境检查
    print("🔍 运行环境检查...")
    env_ok = await runner.run_environment_check()
    if not env_ok:
        print("❌ 环境检查失败")
        return
    
    # 3. 初始化测试环境
    print("🚀 初始化测试环境...")
    init_ok = await runner.initialize_test_environment()
    if not init_ok:
        print("❌ 环境初始化失败")
        return
    
    # 4. 运行单个模块测试
    print("🧪 运行管理员后台测试模块...")
    result = await runner.run_single_module("admin_backend")
    
    print(f"✅ 测试完成 - 状态: {result.get('status')}")
    if "total_tests" in result:
        print(f"📊 测试统计: {result['passed_tests']}/{result['total_tests']} 通过")
    
    # 5. 清理
    await runner.cleanup()


async def example_custom_config():
    """自定义配置示例"""
    print("\n⚙️ 自定义配置示例")
    print("-" * 50)
    
    # 1. 创建自定义配置
    config = TestConfig()
    config.debug_mode = True
    config.verbose_output = True
    config.max_workers = 2
    config.enable_performance_monitoring = False
    
    # 保存配置到文件
    config_path = PROJECT_ROOT / "tests" / "config" / "example_config.json"
    config.save(str(config_path))
    print(f"📝 配置已保存到: {config_path}")
    
    # 2. 使用自定义配置创建运行器
    runner = ComprehensiveTestRunner(str(config_path))
    
    print(f"🔧 使用配置: {runner.config}")
    
    # 3. 运行指定模块
    modules_to_run = ["admin_backend", "user_experience"]
    print(f"🎯 计划运行模块: {modules_to_run}")
    
    # 这里只是演示，不实际运行
    print("✅ 配置示例完成")


async def example_performance_monitoring():
    """性能监控示例"""
    print("\n📈 性能监控示例")
    print("-" * 50)
    
    # 1. 创建性能监控器
    monitor = PerformanceMonitor()
    
    # 2. 启动监控
    monitor.start()
    print("🔄 性能监控已启动")
    
    # 3. 模拟一些工作
    await asyncio.sleep(2)
    
    # 4. 添加自定义指标
    monitor.add_custom_metric("test_duration", 1.5)
    monitor.add_custom_metric("test_memory_usage", 45.2)
    
    # 5. 获取指标
    metrics = monitor.get_metrics()
    print("📊 性能指标:")
    for metric_name, metric_value in metrics.items():
        print(f"  {metric_name}: {metric_value}")
    
    # 6. 停止监控
    monitor.stop()
    print("⏹️ 性能监控已停止")


async def example_result_collection():
    """结果收集示例"""
    print("\n📊 结果收集示例")
    print("-" * 50)
    
    # 1. 创建结果收集器
    collector = TestResultCollector()
    
    # 2. 开始收集
    collector.start_collection()
    
    # 3. 添加模拟测试结果
    collector.add_test_result("test_database_connection", "PASSED", 0.5)
    collector.add_test_result("test_user_creation", "PASSED", 1.2)
    collector.add_test_result("test_invalid_input", "FAILED", 0.3, "Validation error")
    collector.add_test_result("test_performance", "PASSED", 2.1)
    
    # 4. 添加模块结果
    module_result = {
        "status": "PASSED",
        "total_tests": 4,
        "passed_tests": 3,
        "failed_tests": 1,
        "duration": 4.1
    }
    collector.add_module_result("example_module", module_result)
    
    # 5. 添加性能数据
    collector.add_performance_data("cpu_usage", 35.5, "%")
    collector.add_performance_data("memory_usage", 128.3, "MB")
    
    # 6. 结束收集
    collector.end_collection()
    
    # 7. 获取摘要
    summary = collector.get_summary()
    print(f"📋 测试摘要:")
    print(f"  总测试数: {summary.total_tests}")
    print(f"  通过测试: {summary.passed_tests}")
    print(f"  失败测试: {summary.failed_tests}")
    print(f"  通过率: {summary.pass_rate:.1f}%")
    print(f"  总耗时: {summary.total_duration:.2f}秒")
    
    # 8. 导出为JSON
    json_file = PROJECT_ROOT / "tests" / "reports" / "example_results.json"
    collector.export_to_json(str(json_file))
    print(f"💾 结果已导出到: {json_file}")


async def example_report_generation():
    """报告生成示例"""
    print("\n📄 报告生成示例")
    print("-" * 50)
    
    # 1. 创建报告生成器
    reporter = TestReporter(output_dir="tests/reports")
    
    # 2. 准备示例报告数据
    report_data = {
        "summary": {
            "execution_time": 125.6,
            "total_modules": 3,
            "passed_modules": 2,
            "failed_modules": 1,
            "module_pass_rate": 66.7,
            "total_tests": 25,
            "passed_tests": 22,
            "failed_tests": 3,
            "test_pass_rate": 88.0
        },
        "results": {
            "admin_backend": {
                "status": "PASSED",
                "total_tests": 10,
                "passed_tests": 10,
                "duration": 45.2,
                "pass_rate": 100.0
            },
            "user_experience": {
                "status": "PASSED",
                "total_tests": 8,
                "passed_tests": 7,
                "duration": 52.1,
                "pass_rate": 87.5
            },
            "merchant_onboarding": {
                "status": "FAILED",
                "total_tests": 7,
                "passed_tests": 5,
                "duration": 28.3,
                "pass_rate": 71.4,
                "error": "FSM状态机实现缺陷"
            }
        },
        "environment": {
            "python_version": "3.12.0",
            "platform": "darwin",
            "timestamp": "2025-09-13T15:30:00"
        },
        "performance_metrics": {
            "cpu_avg": 42.3,
            "cpu_max": 68.1,
            "memory_avg": 156.7,
            "memory_max": 203.4
        }
    }
    
    # 3. 生成综合报告
    report_files = await reporter.generate_comprehensive_report(report_data)
    
    print("📄 报告已生成:")
    for report_type, file_path in report_files.items():
        print(f"  {report_type}: {file_path}")


async def example_config_templates():
    """配置模板示例"""
    print("\n📝 配置模板示例")
    print("-" * 50)
    
    # 1. 开发环境配置
    dev_config = ConfigTemplates.development()
    print(f"🔧 开发环境配置: {dev_config}")
    
    # 2. CI/CD配置
    ci_config = ConfigTemplates.ci_cd()
    print(f"🚀 CI/CD配置: {ci_config}")
    
    # 3. 性能测试配置
    perf_config = ConfigTemplates.performance()
    print(f"📊 性能测试配置: {perf_config}")
    
    # 4. 生产环境模拟配置
    prod_config = ConfigTemplates.production_simulation()
    print(f"🏭 生产环境模拟配置: {prod_config}")
    
    # 5. 保存所有模板配置
    config_dir = PROJECT_ROOT / "tests" / "config"
    
    templates = {
        "dev_config.json": dev_config,
        "ci_config.json": ci_config,
        "performance_config.json": perf_config,
        "production_sim_config.json": prod_config
    }
    
    for filename, config in templates.items():
        file_path = config_dir / filename
        config.save(str(file_path))
        print(f"💾 已保存: {file_path}")


async def main():
    """主函数 - 运行所有示例"""
    print("🎯 Telegram商户机器人V2.0综合测试系统 - 使用示例")
    print("=" * 80)
    
    try:
        # 运行各个示例
        await example_basic_usage()
        await example_custom_config()
        await example_performance_monitoring()
        await example_result_collection()
        await example_report_generation()
        await example_config_templates()
        
        print("\n🎉 所有示例运行完成！")
        print("\n📚 更多信息请查看:")
        print("  - tests/README.md - 完整使用文档")
        print("  - tests/config/test_config.py - 配置管理API")
        print("  - tests/utils/test_helpers.py - 测试工具API")
        print("  - tests/run_comprehensive_tests.py - 主测试运行器")
        
    except Exception as e:
        print(f"\n💥 示例运行出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())