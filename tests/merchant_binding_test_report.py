#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
商家绑定和管理模块测试脚本
测试失败时仅报告错误位置和原因，禁止修改代码
"""

import sys
import os
import asyncio
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试结果数据结构
class TestResult:
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = False
        self.error_message = ""
        self.error_location = ""
        self.details = {}
        
    def set_passed(self, details: Dict = None):
        self.passed = True
        self.details = details or {}
        
    def set_failed(self, error_message: str, error_location: str = ""):
        self.passed = False
        self.error_message = error_message
        self.error_location = error_location

class MerchantBindingTestReport:
    def __init__(self):
        self.test_results: List[TestResult] = []
        self.database_path = "data/database.db"
        
    def add_result(self, result: TestResult):
        self.test_results.append(result)
        
    def get_summary(self) -> Dict[str, Any]:
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.passed)
        failed_tests = total_tests - passed_tests
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%"
        }

    def test_database_schema_compatibility(self) -> TestResult:
        """测试数据库schema兼容性"""
        result = TestResult("数据库Schema兼容性测试")
        
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # 检查必需的表是否存在
            required_tables = ['binding_codes', 'merchants_v2_temp', 'provinces', 'regions']
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = [table for table in required_tables if table not in existing_tables]
            if missing_tables:
                result.set_failed(
                    f"缺少必需的数据库表: {', '.join(missing_tables)}",
                    "database schema check"
                )
                conn.close()
                return result
            
            # 检查binding_codes表结构
            cursor.execute("PRAGMA table_info(binding_codes)")
            binding_columns = {row[1]: row[2] for row in cursor.fetchall()}
            required_binding_cols = ['id', 'code', 'is_used', 'merchant_id', 'created_at']
            
            missing_cols = [col for col in required_binding_cols if col not in binding_columns]
            if missing_cols:
                result.set_failed(
                    f"binding_codes表缺少必需字段: {', '.join(missing_cols)}",
                    "binding_codes table structure"
                )
                conn.close()
                return result
            
            # 检查merchants_v2_temp表结构
            cursor.execute("PRAGMA table_info(merchants_v2_temp)")
            merchant_columns = {row[1]: row[2] for row in cursor.fetchall()}
            required_merchant_cols = ['id', 'telegram_chat_id', 'name', 'status']
            
            missing_merchant_cols = [col for col in required_merchant_cols if col not in merchant_columns]
            if missing_merchant_cols:
                result.set_failed(
                    f"merchants_v2_temp表缺少必需字段: {', '.join(missing_merchant_cols)}",
                    "merchants_v2_temp table structure"
                )
                conn.close()
                return result
            
            conn.close()
            result.set_passed({
                "existing_tables": len(existing_tables),
                "binding_columns": len(binding_columns),
                "merchant_columns": len(merchant_columns)
            })
            
        except Exception as e:
            result.set_failed(f"数据库连接或查询错误: {str(e)}", "database connection")
            
        return result

    def test_binding_code_generation(self) -> TestResult:
        """测试绑定码生成功能"""
        result = TestResult("绑定码生成功能测试")
        
        try:
            # 导入绑定码管理器
            from database.db_binding_codes import BindingCodesManager
            
            # 测试生成绑定码
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 生成一个测试绑定码
            test_code = loop.run_until_complete(BindingCodesManager.generate_binding_code())
            
            if not test_code:
                result.set_failed("绑定码生成失败，返回空值", "BindingCodesManager.generate_binding_code()")
                return result
            
            if len(test_code) != 8:
                result.set_failed(f"绑定码长度错误，期望8位，实际{len(test_code)}位", "binding code length validation")
                return result
            
            # 验证绑定码格式（大写字母和数字）
            if not test_code.isalnum() or not test_code.isupper():
                result.set_failed(f"绑定码格式错误，应为8位大写字母和数字: {test_code}", "binding code format validation")
                return result
            
            # 验证绑定码在数据库中存在
            code_info = loop.run_until_complete(BindingCodesManager.get_binding_code_info(test_code))
            if not code_info:
                result.set_failed(f"生成的绑定码在数据库中不存在: {test_code}", "database persistence check")
                return result
            
            result.set_passed({
                "generated_code": test_code,
                "code_length": len(test_code),
                "is_in_database": bool(code_info)
            })
            
        except ImportError as e:
            result.set_failed(f"无法导入绑定码管理器: {str(e)}", "import BindingCodesManager")
        except Exception as e:
            result.set_failed(f"绑定码生成过程中发生错误: {str(e)}", "BindingCodesManager.generate_binding_code() execution")
            
        return result

    def test_binding_code_validation_flow(self) -> TestResult:
        """测试绑定码验证流程"""
        result = TestResult("绑定码验证流程测试")
        
        try:
            from database.db_binding_codes import BindingCodesManager
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 1. 生成测试绑定码
            test_code = loop.run_until_complete(BindingCodesManager.generate_binding_code())
            test_user_id = 999999  # 使用测试用户ID
            
            # 2. 测试有效绑定码的验证和使用
            validation_result = loop.run_until_complete(
                BindingCodesManager.validate_and_use_binding_code(test_code, test_user_id)
            )
            
            if not validation_result['success']:
                result.set_failed(
                    f"有效绑定码验证失败: {validation_result['message']}", 
                    "BindingCodesManager.validate_and_use_binding_code() - valid code"
                )
                return result
            
            merchant_id = validation_result.get('merchant_id')
            if not merchant_id:
                result.set_failed("验证成功但未返回merchant_id", "validation result merchant_id")
                return result
            
            # 3. 测试已使用绑定码的重复验证
            repeat_result = loop.run_until_complete(
                BindingCodesManager.validate_and_use_binding_code(test_code, 888888)
            )
            
            if repeat_result['success']:
                result.set_failed("已使用的绑定码应该验证失败", "duplicate binding code usage")
                return result
            
            # 4. 测试无效绑定码
            invalid_result = loop.run_until_complete(
                BindingCodesManager.validate_and_use_binding_code("INVALID1", 777777)
            )
            
            if invalid_result['success']:
                result.set_failed("无效绑定码应该验证失败", "invalid binding code validation")
                return result
            
            result.set_passed({
                "test_code": test_code,
                "created_merchant_id": merchant_id,
                "validation_success": validation_result['success'],
                "duplicate_prevented": not repeat_result['success'],
                "invalid_rejected": not invalid_result['success']
            })
            
        except Exception as e:
            result.set_failed(f"绑定码验证流程测试出错: {str(e)}", "binding code validation flow")
            
        return result

    def test_merchant_data_management(self) -> TestResult:
        """测试商家数据管理功能"""
        result = TestResult("商家数据管理功能测试")
        
        try:
            from database.db_merchants import MerchantManager
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 1. 测试创建商家
            test_merchant_data = {
                'telegram_chat_id': 123456789,
                'name': '测试商家',
                'merchant_type': 'teacher',
                'status': 'pending_submission',
                'custom_description': '测试描述'
            }
            
            merchant_id = loop.run_until_complete(MerchantManager.create_merchant(test_merchant_data))
            
            if not merchant_id:
                result.set_failed("创建商家失败，返回None", "MerchantManager.create_merchant()")
                return result
            
            # 2. 测试获取商家信息
            merchant_info = loop.run_until_complete(MerchantManager.get_merchant(merchant_id))
            
            if not merchant_info:
                result.set_failed(f"获取商家信息失败，merchant_id: {merchant_id}", "MerchantManager.get_merchant()")
                return result
            
            # 验证数据完整性
            if merchant_info['name'] != test_merchant_data['name']:
                result.set_failed(
                    f"商家名称不匹配，期望: {test_merchant_data['name']}, 实际: {merchant_info['name']}", 
                    "merchant data integrity"
                )
                return result
            
            # 3. 测试根据chat_id获取商家
            merchant_by_chat = loop.run_until_complete(
                MerchantManager.get_merchant_by_chat_id(test_merchant_data['telegram_chat_id'])
            )
            
            if not merchant_by_chat or merchant_by_chat['id'] != merchant_id:
                result.set_failed("根据chat_id获取商家失败或ID不匹配", "MerchantManager.get_merchant_by_chat_id()")
                return result
            
            # 4. 测试更新商家信息
            update_data = {'name': '更新后的商家名称', 'status': 'pending_approval'}
            update_success = loop.run_until_complete(MerchantManager.update_merchant(merchant_id, update_data))
            
            if not update_success:
                result.set_failed("更新商家信息失败", "MerchantManager.update_merchant()")
                return result
            
            # 验证更新结果
            updated_merchant = loop.run_until_complete(MerchantManager.get_merchant(merchant_id))
            if updated_merchant['name'] != update_data['name']:
                result.set_failed("商家信息更新后验证失败", "merchant update verification")
                return result
            
            result.set_passed({
                "merchant_id": merchant_id,
                "original_name": test_merchant_data['name'],
                "updated_name": update_data['name'],
                "chat_id_lookup": merchant_by_chat is not None
            })
            
        except Exception as e:
            result.set_failed(f"商家数据管理测试出错: {str(e)}", "merchant data management")
            
        return result

    def test_fsm_state_definitions(self) -> TestResult:
        """测试FSM状态定义"""
        result = TestResult("FSM状态定义测试")
        
        try:
            from dialogs.states import MerchantStates, UserStates, StateValidator, StateData
            
            # 1. 测试状态类定义
            merchant_states = [
                MerchantStates.entering_binding_code,
                MerchantStates.selecting_region,
                MerchantStates.selecting_category,
                MerchantStates.entering_name,
                MerchantStates.entering_contact_info,
                MerchantStates.confirming_profile,
                MerchantStates.editing_profile
            ]
            
            for state in merchant_states:
                if not hasattr(state, 'state') or not hasattr(state, 'group'):
                    result.set_failed(f"状态{state}缺少必需属性", "state attributes check")
                    return result
            
            # 2. 测试状态转换验证器
            # 测试有效转换
            valid_transition = StateValidator.is_valid_transition(
                MerchantStates.entering_binding_code,
                MerchantStates.selecting_region
            )
            
            if not valid_transition:
                result.set_failed("有效的状态转换被错误拒绝", "StateValidator.is_valid_transition() - valid case")
                return result
            
            # 测试无效转换
            invalid_transition = StateValidator.is_valid_transition(
                MerchantStates.entering_binding_code,
                MerchantStates.confirming_profile
            )
            
            if invalid_transition:
                result.set_failed("无效的状态转换被错误接受", "StateValidator.is_valid_transition() - invalid case")
                return result
            
            # 3. 测试状态数据管理
            state_data = StateData()
            state_data.set("test_key", "test_value")
            
            if state_data.get("test_key") != "test_value":
                result.set_failed("状态数据设置/获取失败", "StateData.set()/get()")
                return result
            
            # 测试JSON序列化
            json_str = state_data.to_json()
            restored_data = StateData.from_json(json_str)
            
            if restored_data.get("test_key") != "test_value":
                result.set_failed("状态数据JSON序列化/反序列化失败", "StateData JSON serialization")
                return result
            
            result.set_passed({
                "merchant_states_count": len(merchant_states),
                "valid_transition_works": valid_transition,
                "invalid_transition_rejected": not invalid_transition,
                "state_data_serialization": True
            })
            
        except ImportError as e:
            result.set_failed(f"无法导入状态相关模块: {str(e)}", "import states module")
        except Exception as e:
            result.set_failed(f"FSM状态测试出错: {str(e)}", "FSM state testing")
            
        return result

    def test_merchant_handler_structure(self) -> TestResult:
        """测试商家处理器结构"""
        result = TestResult("商家处理器结构测试")
        
        try:
            from handlers.merchant import MerchantHandler, merchant_router
            
            # 1. 检查MerchantHandler类的关键方法
            required_methods = [
                'handle_registration_trigger',
                'handle_binding_code_input',
                'handle_binding_flow_callback',
                'handle_merchant_message'
            ]
            
            for method_name in required_methods:
                if not hasattr(MerchantHandler, method_name):
                    result.set_failed(f"MerchantHandler缺少必需方法: {method_name}", "MerchantHandler methods check")
                    return result
                
                method = getattr(MerchantHandler, method_name)
                if not callable(method):
                    result.set_failed(f"MerchantHandler.{method_name}不是可调用的", "method callability check")
                    return result
            
            # 2. 检查路由器配置
            if not merchant_router:
                result.set_failed("merchant_router未定义", "merchant_router definition")
                return result
            
            # 3. 检查绑定流程步骤配置
            from handlers.merchant import BINDING_FLOW_STEPS
            
            if not BINDING_FLOW_STEPS or not isinstance(BINDING_FLOW_STEPS, dict):
                result.set_failed("BINDING_FLOW_STEPS配置无效", "BINDING_FLOW_STEPS configuration")
                return result
            
            # 验证7步流程配置
            expected_steps = list(range(1, 8))  # 1-7
            actual_steps = list(BINDING_FLOW_STEPS.keys())
            
            if actual_steps != expected_steps:
                result.set_failed(
                    f"绑定流程步骤配置错误，期望: {expected_steps}, 实际: {actual_steps}",
                    "binding flow steps configuration"
                )
                return result
            
            # 验证每个步骤的必需字段
            for step_num, step_config in BINDING_FLOW_STEPS.items():
                required_fields = ['title', 'description', 'field']
                missing_fields = [field for field in required_fields if field not in step_config]
                
                if missing_fields:
                    result.set_failed(
                        f"步骤{step_num}缺少必需字段: {missing_fields}",
                        f"binding flow step {step_num} configuration"
                    )
                    return result
            
            result.set_passed({
                "handler_methods_count": len(required_methods),
                "binding_steps_count": len(BINDING_FLOW_STEPS),
                "router_defined": merchant_router is not None
            })
            
        except ImportError as e:
            result.set_failed(f"无法导入merchant handler: {str(e)}", "import merchant handler")
        except Exception as e:
            result.set_failed(f"merchant handler结构测试出错: {str(e)}", "merchant handler structure test")
            
        return result

    def test_web_admin_routes(self) -> TestResult:
        """测试Web管理后台路由"""
        result = TestResult("Web管理后台路由测试")
        
        try:
            from web.routes.merchants import router as merchants_router
            
            # 检查路由器是否正确定义
            if not merchants_router:
                result.set_failed("merchants router未定义", "merchants router definition")
                return result
            
            # 尝试导入其他相关Web组件
            try:
                from web.app import app
                if not app:
                    result.set_failed("Web应用未定义", "web app definition")
                    return result
            except ImportError:
                result.set_failed("无法导入Web应用", "web app import")
                return result
            
            result.set_passed({
                "merchants_router_defined": merchants_router is not None,
                "web_app_defined": True
            })
            
        except ImportError as e:
            result.set_failed(f"无法导入Web路由: {str(e)}", "import web routes")
        except Exception as e:
            result.set_failed(f"Web路由测试出错: {str(e)}", "web routes test")
            
        return result

    def run_all_tests(self) -> None:
        """运行所有测试"""
        print("🧪 开始执行商家绑定和管理模块功能测试...")
        print("=" * 60)
        
        # 执行各项测试
        tests = [
            self.test_database_schema_compatibility,
            self.test_binding_code_generation,
            self.test_binding_code_validation_flow,
            self.test_merchant_data_management,
            self.test_fsm_state_definitions,
            self.test_merchant_handler_structure,
            self.test_web_admin_routes
        ]
        
        for test_method in tests:
            print(f"\n🔍 执行: {test_method.__doc__}")
            result = test_method()
            self.add_result(result)
            
            if result.passed:
                print(f"✅ {result.test_name} - 通过")
                if result.details:
                    for key, value in result.details.items():
                        print(f"   📊 {key}: {value}")
            else:
                print(f"❌ {result.test_name} - 失败")
                print(f"   🔴 错误信息: {result.error_message}")
                if result.error_location:
                    print(f"   📍 错误位置: {result.error_location}")

    def generate_report(self) -> str:
        """生成测试报告"""
        summary = self.get_summary()
        
        report = []
        report.append("# 商家绑定和管理模块测试报告")
        report.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # 测试总结
        report.append("## 📊 测试总结")
        report.append(f"- **总测试数**: {summary['total_tests']}")
        report.append(f"- **通过测试**: {summary['passed_tests']}")
        report.append(f"- **失败测试**: {summary['failed_tests']}")
        report.append(f"- **成功率**: {summary['success_rate']}")
        report.append("")
        
        # 详细测试结果
        report.append("## 📋 详细测试结果")
        report.append("")
        
        for i, result in enumerate(self.test_results, 1):
            status_icon = "✅" if result.passed else "❌"
            report.append(f"### {i}. {status_icon} {result.test_name}")
            
            if result.passed:
                report.append("**状态**: 通过")
                if result.details:
                    report.append("**详细信息**:")
                    for key, value in result.details.items():
                        report.append(f"- {key}: {value}")
            else:
                report.append("**状态**: 失败")
                report.append(f"**错误信息**: {result.error_message}")
                if result.error_location:
                    report.append(f"**错误位置**: {result.error_location}")
            
            report.append("")
        
        # 问题总结
        failed_results = [r for r in self.test_results if not r.passed]
        if failed_results:
            report.append("## 🚨 问题总结")
            report.append("")
            for i, result in enumerate(failed_results, 1):
                report.append(f"{i}. **{result.test_name}**")
                report.append(f"   - 错误: {result.error_message}")
                if result.error_location:
                    report.append(f"   - 位置: {result.error_location}")
                report.append("")
        
        # 建议
        report.append("## 💡 建议")
        if summary['failed_tests'] == 0:
            report.append("🎉 所有测试都通过了！商家绑定和管理模块功能正常。")
        else:
            report.append("⚠️ 发现问题需要修复:")
            report.append("1. 请根据上述错误信息检查相关代码文件")
            report.append("2. 确保数据库表结构与代码期望一致")
            report.append("3. 验证所有必需的模块和依赖项都已正确导入")
            report.append("4. 检查配置文件和环境变量设置")
        
        return "\n".join(report)

def main():
    """主函数"""
    tester = MerchantBindingTestReport()
    
    try:
        # 运行所有测试
        tester.run_all_tests()
        
        # 生成和显示报告
        print("\n" + "=" * 60)
        print("📋 生成测试报告...")
        
        report = tester.generate_report()
        
        # 保存报告到文件
        report_file = "tests/merchant_binding_test_report.md"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ 测试报告已保存到: {report_file}")
        
        # 显示简要总结
        summary = tester.get_summary()
        print(f"\n🏆 测试完成: {summary['passed_tests']}/{summary['total_tests']} 通过 ({summary['success_rate']})")
        
        if summary['failed_tests'] > 0:
            print("❌ 发现问题，请查看详细报告")
            sys.exit(1)
        else:
            print("✅ 所有测试通过")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 测试执行出错: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()