# -*- coding: utf-8 -*-
"""
测试运行器 - 独立运行商户入驻流程测试
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.db_binding_codes import BindingCodesManager
from database.db_merchants import MerchantManager  
from dialogs.states import MerchantOnboardingStates, StateData, StateValidator
from utils.enums import MERCHANT_STATUS

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MerchantOnboardingTestRunner:
    """商户入驻测试运行器"""
    
    def __init__(self):
        self.test_results = []
        self.test_user_id = 98765
        
    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("开始商户入驻流程测试")
        print("=" * 60)
        
        # 执行所有测试方法
        test_methods = [
            self.test_binding_code_generation,
            self.test_binding_code_validation,
            self.test_merchant_creation,
            self.test_fsm_states_definition,
            self.test_architecture_issues,
            self.test_status_transitions,
            self.test_error_scenarios
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                self.record_result(test_method.__name__, False, str(e))
                logger.error(f"测试 {test_method.__name__} 失败: {e}")
        
        self.print_summary()
    
    def record_result(self, test_name, success, details=None):
        """记录测试结果"""
        self.test_results.append({
            'test_name': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now()
        })
    
    async def test_binding_code_generation(self):
        """测试绑定码生成功能"""
        print("\n🔧 测试1: 绑定码生成功能")
        
        try:
            # 生成绑定码
            binding_code = await BindingCodesManager.generate_binding_code(24)
            
            # 验证格式
            assert len(binding_code) == 8, f"绑定码长度错误: {len(binding_code)}"
            assert binding_code.isupper(), "绑定码应该是大写字母"
            assert binding_code.isalnum(), "绑定码应该只包含字母和数字"
            
            print(f"  ✅ 绑定码生成成功: {binding_code}")
            
            # 验证唯一性
            second_code = await BindingCodesManager.generate_binding_code(24)
            assert binding_code != second_code, "绑定码应该是唯一的"
            
            print(f"  ✅ 绑定码唯一性验证通过: {second_code}")
            
            self.record_result('test_binding_code_generation', True, f"生成绑定码: {binding_code}, {second_code}")
            
        except Exception as e:
            self.record_result('test_binding_code_generation', False, str(e))
            raise
    
    async def test_binding_code_validation(self):
        """测试绑定码验证和使用流程"""
        print("\n🔐 测试2: 绑定码验证和使用")
        
        try:
            # 生成新绑定码
            binding_code = await BindingCodesManager.generate_binding_code()
            print(f"  生成测试绑定码: {binding_code}")
            
            # 测试有效绑定码
            result = await BindingCodesManager.validate_and_use_binding_code(
                binding_code, self.test_user_id
            )
            
            assert result['success'] == True, f"绑定码验证失败: {result['message']}"
            assert result['merchant_id'] is not None, "应该返回商户ID"
            assert '绑定成功' in result['message'], "消息应该包含成功提示"
            
            print(f"  ✅ 绑定码验证成功，商户ID: {result['merchant_id']}")
            
            # 测试重复使用
            duplicate_result = await BindingCodesManager.validate_and_use_binding_code(
                binding_code, self.test_user_id + 1
            )
            
            assert duplicate_result['success'] == False, "重复使用应该失败"
            print(f"  ✅ 重复使用检查通过: {duplicate_result['message']}")
            
            # 测试无效格式
            invalid_result = await BindingCodesManager.validate_and_use_binding_code(
                'INVALID', self.test_user_id + 2
            )
            assert invalid_result['success'] == False, "无效格式应该失败"
            print(f"  ✅ 无效格式检查通过: {invalid_result['message']}")
            
            self.record_result('test_binding_code_validation', True, f"商户ID: {result['merchant_id']}")
            
        except Exception as e:
            self.record_result('test_binding_code_validation', False, str(e))
            raise
    
    async def test_merchant_creation(self):
        """测试商户创建和数据管理"""
        print("\n👤 测试3: 商户创建和数据管理")
        
        try:
            # 生成绑定码并创建商户
            binding_code = await BindingCodesManager.generate_binding_code()
            result = await BindingCodesManager.validate_and_use_binding_code(
                binding_code, self.test_user_id + 10
            )
            
            merchant_id = result['merchant_id']
            print(f"  创建商户ID: {merchant_id}")
            
            # 验证商户信息
            merchant = await MerchantManager.get_merchant(merchant_id)
            assert merchant is not None, "商户应该存在"
            assert merchant['telegram_chat_id'] == self.test_user_id + 10, "TG用户ID应该匹配"
            assert merchant['status'] == 'pending_submission', "初始状态应该是待提交"
            assert merchant['name'] == '待完善', "初始名称应该是待完善"
            
            print(f"  ✅ 商户基础信息验证通过")
            
            # 测试信息更新
            update_data = {
                'name': '测试商户名称',
                'custom_description': '这是一个测试商户',
                'p_price': '500',
                'pp_price': '800',
                'contact_info': '测试联系方式',
                'status': 'pending_approval'
            }
            
            update_success = await MerchantManager.update_merchant(merchant_id, update_data)
            assert update_success == True, "更新应该成功"
            
            # 验证更新结果
            updated_merchant = await MerchantManager.get_merchant(merchant_id)
            assert updated_merchant['name'] == update_data['name'], "名称更新失败"
            assert updated_merchant['status'] == 'pending_approval', "状态更新失败"
            assert updated_merchant['p_price'] == update_data['p_price'], "价格更新失败"
            
            print(f"  ✅ 商户信息更新验证通过")
            
            self.record_result('test_merchant_creation', True, f"商户ID: {merchant_id}")
            
        except Exception as e:
            self.record_result('test_merchant_creation', False, str(e))
            raise
    
    async def test_fsm_states_definition(self):
        """测试FSM状态定义和功能"""
        print("\n🔄 测试4: FSM状态机定义")
        
        try:
            # 验证状态定义存在
            expected_states = [
                'AwaitingName', 'AwaitingCity', 'AwaitingDistrict',
                'AwaitingPrice1', 'AwaitingPrice2', 'AwaitingAdvantages',
                'AwaitingDisadvantages', 'AwaitingBasicSkills', 
                'AwaitingMedia', 'AwaitingConfirmation'
            ]
            
            for state_name in expected_states:
                assert hasattr(MerchantOnboardingStates, state_name), f"缺少状态: {state_name}"
            
            print(f"  ✅ 所有FSM状态定义存在 ({len(expected_states)}个)")
            
            # 测试状态数据管理
            state_data = StateData()
            test_data = {
                'merchant_name': '测试商户',
                'city': '北京市',
                'district': '朝阳区',
                'p_price': '600'
            }
            
            for key, value in test_data.items():
                state_data.set(key, value)
            
            # 验证数据存储和获取
            for key, expected_value in test_data.items():
                actual_value = state_data.get(key)
                assert actual_value == expected_value, f"状态数据不匹配: {key}"
            
            print(f"  ✅ 状态数据管理功能正常")
            
            # 测试序列化和反序列化
            json_data = state_data.to_json()
            restored_data = StateData.from_json(json_data)
            
            for key, expected_value in test_data.items():
                actual_value = restored_data.get(key)
                assert actual_value == expected_value, f"序列化数据不匹配: {key}"
            
            print(f"  ✅ 状态数据序列化功能正常")
            
            self.record_result('test_fsm_states_definition', True, f"验证{len(expected_states)}个状态")
            
        except Exception as e:
            self.record_result('test_fsm_states_definition', False, str(e))
            raise
    
    async def test_architecture_issues(self):
        """测试架构问题和缺陷"""
        print("\n⚠️  测试5: 架构问题分析")
        
        issues_found = []
        
        try:
            # 问题1: FSM状态转换规则缺失
            from dialogs.states import StateValidator
            onboarding_states = [
                MerchantOnboardingStates.AwaitingName,
                MerchantOnboardingStates.AwaitingCity
            ]
            
            for state in onboarding_states:
                if state not in StateValidator.ALLOWED_TRANSITIONS:
                    issues_found.append(f"FSM状态 {state} 缺少转换规则")
            
            # 问题2: 状态类型识别不支持
            from dialogs.states import get_user_type_from_state
            user_type = get_user_type_from_state(MerchantOnboardingStates.AwaitingName)
            if user_type is None:
                issues_found.append("MerchantOnboardingStates 不被状态类型识别系统支持")
            
            # 问题3: 处理器实现不匹配
            from handlers.merchant import BINDING_FLOW_STEPS
            if 'title' in BINDING_FLOW_STEPS[1]:
                issues_found.append("使用7步静态配置而不是FSM状态机")
            
            # 问题4: 缺少实际FSM流程实现
            # 通过检查是否存在FSM状态处理代码来验证
            
            print(f"  发现 {len(issues_found)} 个架构问题:")
            for i, issue in enumerate(issues_found, 1):
                print(f"    {i}. {issue}")
            
            self.record_result('test_architecture_issues', True, f"发现{len(issues_found)}个问题")
            
        except Exception as e:
            self.record_result('test_architecture_issues', False, str(e))
            raise
    
    async def test_status_transitions(self):
        """测试商户状态转换"""
        print("\n📊 测试6: 商户状态转换")
        
        try:
            # 创建测试商户
            binding_code = await BindingCodesManager.generate_binding_code()
            result = await BindingCodesManager.validate_and_use_binding_code(
                binding_code, self.test_user_id + 20
            )
            merchant_id = result['merchant_id']
            
            # 测试状态转换序列
            status_sequence = [
                ('pending_submission', '待提交'),
                ('pending_approval', '等待审核'),
                ('approved', '已审核'),
                ('published', '已发布'),
                ('expired', '已过期')
            ]
            
            for status, expected_display in status_sequence:
                # 更新状态
                update_success = await MerchantManager.update_merchant_status(merchant_id, status)
                assert update_success == True, f"状态更新失败: {status}"
                
                # 验证状态
                merchant = await MerchantManager.get_merchant(merchant_id)
                assert merchant['status'] == status, f"状态不匹配: 期望{status}, 实际{merchant['status']}"
                
                # 测试状态标准化
                normalized = MERCHANT_STATUS.normalize(status)
                assert normalized == status, f"V2状态标准化失败: {status}"
                
                # 测试状态显示名称
                display_name = MERCHANT_STATUS.get_display_name(normalized)
                assert display_name == expected_display, f"状态显示名称错误: 期望{expected_display}, 实际{display_name}"
                
                print(f"    ✅ {status} -> {display_name}")
            
            print(f"  ✅ 所有状态转换验证通过")
            
            self.record_result('test_status_transitions', True, f"验证{len(status_sequence)}个状态")
            
        except Exception as e:
            self.record_result('test_status_transitions', False, str(e))
            raise
    
    async def test_error_scenarios(self):
        """测试错误场景和异常处理"""
        print("\n🚨 测试7: 错误场景处理")
        
        error_tests = []
        
        try:
            # 测试1: 空绑定码
            result1 = await BindingCodesManager.validate_and_use_binding_code('', 12345)
            if not result1['success'] and '不能为空' in result1['message']:
                error_tests.append("✅ 空绑定码错误处理正确")
            else:
                error_tests.append("❌ 空绑定码错误处理失败")
            
            # 测试2: 不存在的商户更新
            update_result = await MerchantManager.update_merchant(99999, {'name': 'test'})
            if update_result == False:
                error_tests.append("✅ 不存在商户更新错误处理正确")
            else:
                error_tests.append("❌ 不存在商户更新错误处理失败")
            
            # 测试3: 无效状态更新
            binding_code = await BindingCodesManager.generate_binding_code()
            result = await BindingCodesManager.validate_and_use_binding_code(
                binding_code, self.test_user_id + 30
            )
            merchant_id = result['merchant_id']
            
            invalid_status_result = await MerchantManager.update_merchant_status(
                merchant_id, 'invalid_status'
            )
            if invalid_status_result == False:
                error_tests.append("✅ 无效状态更新错误处理正确")
            else:
                error_tests.append("❌ 无效状态更新错误处理失败")
            
            for test_result in error_tests:
                print(f"    {test_result}")
            
            success_count = sum(1 for test in error_tests if "✅" in test)
            self.record_result('test_error_scenarios', success_count == len(error_tests), 
                             f"{success_count}/{len(error_tests)} 通过")
            
        except Exception as e:
            self.record_result('test_error_scenarios', False, str(e))
            raise
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("测试结果总结")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过测试: {passed_tests}")
        print(f"失败测试: {failed_tests}")
        print(f"通过率: {passed_tests/total_tests*100:.1f}%")
        
        print("\n详细结果:")
        for result in self.test_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  {status} {result['test_name']}")
            if result['details']:
                print(f"        {result['details']}")
        
        # 生成问题汇总
        if failed_tests > 0:
            print(f"\n🚨 发现的问题:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  • {result['test_name']}: {result['details']}")
        
        print("\n" + "=" * 60)


async def main():
    """主函数"""
    runner = MerchantOnboardingTestRunner()
    await runner.run_all_tests()


if __name__ == '__main__':
    asyncio.run(main())