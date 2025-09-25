# -*- coding: utf-8 -*-
"""
商户入驻流程集成测试 (V2.0)
测试基于FSM状态机的对话式信息收集系统
"""

import asyncio
import pytest
import tempfile
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dialogs.states import MerchantOnboardingStates, StateData, StateValidator
from database.db_merchants import MerchantManager
from database.db_binding_codes import BindingCodesManager
from handlers.merchant import MerchantHandler
from utils.enums import MERCHANT_STATUS


class TestMerchantOnboardingFlow:
    """商户入驻流程集成测试类"""
    
    @pytest.fixture
    async def setup_test_environment(self):
        """设置测试环境"""
        # 创建模拟Bot实例
        mock_bot = Mock()
        mock_bot.send_message = AsyncMock()
        mock_bot.get_chat = AsyncMock()
        
        # 创建商户处理器
        merchant_handler = MerchantHandler(mock_bot)
        
        return {
            'bot': mock_bot,
            'handler': merchant_handler,
            'test_user_id': 12345,
            'test_binding_code': 'TESTAB12'
        }
    
    @pytest.mark.asyncio
    async def test_binding_code_validation_and_merchant_creation(self, setup_test_environment):
        """测试绑定码验证和商户创建流程"""
        env = await setup_test_environment
        
        # 1. 测试绑定码生成
        binding_code = await BindingCodesManager.generate_binding_code(24)
        assert len(binding_code) == 8
        assert binding_code.isupper()
        assert binding_code.isalnum()
        
        # 2. 测试绑定码验证和使用
        result = await BindingCodesManager.validate_and_use_binding_code(
            binding_code, env['test_user_id']
        )
        
        assert result['success'] == True
        assert result['merchant_id'] is not None
        assert '绑定成功' in result['message']
        
        # 3. 验证商户档案创建
        merchant = await MerchantManager.get_merchant(result['merchant_id'])
        assert merchant is not None
        assert merchant['telegram_chat_id'] == env['test_user_id']
        assert merchant['status'] == 'pending_submission'
        assert merchant['name'] == '待完善'
        
        # 4. 测试重复绑定检查
        duplicate_result = await BindingCodesManager.validate_and_use_binding_code(
            binding_code, env['test_user_id']
        )
        assert duplicate_result['success'] == False
        assert '已绑定' in duplicate_result['message']
    
    @pytest.mark.asyncio
    async def test_fsm_state_machine_definitions(self):
        """测试FSM状态机定义和验证"""
        
        # 1. 测试状态定义完整性
        expected_states = [
            'AwaitingName', 'AwaitingCity', 'AwaitingDistrict',
            'AwaitingPrice1', 'AwaitingPrice2', 'AwaitingAdvantages',
            'AwaitingDisadvantages', 'AwaitingBasicSkills', 
            'AwaitingMedia', 'AwaitingConfirmation'
        ]
        
        for state_name in expected_states:
            assert hasattr(MerchantOnboardingStates, state_name)
        
        # 2. 测试状态数据管理
        state_data = StateData()
        state_data.set('merchant_name', '测试商户')
        state_data.set('city', '北京市')
        state_data.set('district', '朝阳区')
        
        assert state_data.get('merchant_name') == '测试商户'
        assert state_data.get('city') == '北京市'
        assert state_data.get('nonexistent', 'default') == 'default'
        
        # 3. 测试状态序列化
        json_data = state_data.to_json()
        restored_data = StateData.from_json(json_data)
        assert restored_data.get('merchant_name') == '测试商户'
        assert restored_data.get('city') == '北京市'
    
    @pytest.mark.asyncio 
    async def test_fsm_state_transitions(self):
        """测试FSM状态转换逻辑"""
        
        # 1. 测试有效状态转换
        from_state = MerchantOnboardingStates.AwaitingName
        to_state = MerchantOnboardingStates.AwaitingCity
        
        # 注意：当前StateValidator只定义了MerchantStates的转换规则
        # 需要扩展支持MerchantOnboardingStates
        
        # 2. 测试状态恢复机制
        recovery_state = StateValidator.get_recovery_state('merchant')
        assert recovery_state is not None
        
        # 3. 测试状态类型识别
        from dialogs.states import get_user_type_from_state
        user_type = get_user_type_from_state(from_state)
        # 由于MerchantOnboardingStates不在映射中，会返回None
        # 这表明状态管理系统需要完善
    
    @pytest.mark.asyncio
    async def test_merchant_onboarding_flow_simulation(self, setup_test_environment):
        """模拟完整的商户入驻流程"""
        env = await setup_test_environment
        
        # 1. 创建绑定码并绑定
        binding_code = await BindingCodesManager.generate_binding_code()
        bind_result = await BindingCodesManager.validate_and_use_binding_code(
            binding_code, env['test_user_id']
        )
        
        merchant_id = bind_result['merchant_id']
        assert merchant_id is not None
        
        # 2. 模拟FSM状态机流程数据收集
        merchant_data = {
            'name': '测试商户名称',
            'city': '北京市', 
            'district': '朝阳区',
            'p_price': '500',
            'pp_price': '800',
            'advantages': '专业可靠，经验丰富',
            'disadvantages': '时间有限',
            'basic_skills': '基础技能描述',
            'media_files': ['test_file_id_1', 'test_file_id_2']
        }
        
        # 3. 更新商户信息（模拟FSM收集完成）
        update_success = await MerchantManager.update_merchant(merchant_id, {
            'name': merchant_data['name'],
            'custom_description': merchant_data['advantages'],
            'p_price': merchant_data['p_price'],
            'pp_price': merchant_data['pp_price'],
            'status': 'pending_approval',
            'profile_data': merchant_data
        })
        
        assert update_success == True
        
        # 4. 验证更新后的商户状态
        updated_merchant = await MerchantManager.get_merchant(merchant_id)
        assert updated_merchant['name'] == merchant_data['name']
        assert updated_merchant['status'] == 'pending_approval'
        assert updated_merchant['p_price'] == merchant_data['p_price']
        
        # 5. 测试状态标准化
        normalized_status = MERCHANT_STATUS.normalize(updated_merchant['status'])
        assert normalized_status == MERCHANT_STATUS.PENDING_APPROVAL.value
        
        display_name = MERCHANT_STATUS.get_display_name(normalized_status)
        assert display_name == '等待审核'
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, setup_test_environment):
        """测试异常处理和错误恢复"""
        env = await setup_test_environment
        
        # 1. 测试无效绑定码
        invalid_result = await BindingCodesManager.validate_and_use_binding_code(
            'INVALID1', env['test_user_id']
        )
        assert invalid_result['success'] == False
        assert '无效' in invalid_result['message']
        
        # 2. 测试空绑定码
        empty_result = await BindingCodesManager.validate_and_use_binding_code(
            '', env['test_user_id']
        )
        assert empty_result['success'] == False
        assert '不能为空' in empty_result['message']
        
        # 3. 测试格式错误的绑定码
        format_error_result = await BindingCodesManager.validate_and_use_binding_code(
            'abc123', env['test_user_id']  # 小写字母
        )
        # 注意：当前实现会自动转换为大写，所以这个测试需要调整
        
        # 4. 测试不存在的商户更新
        nonexistent_update = await MerchantManager.update_merchant(99999, {'name': 'test'})
        assert nonexistent_update == False
    
    @pytest.mark.asyncio
    async def test_merchant_status_transitions(self, setup_test_environment):
        """测试商户状态转换"""
        env = await setup_test_environment
        
        # 1. 创建测试商户
        binding_code = await BindingCodesManager.generate_binding_code()
        bind_result = await BindingCodesManager.validate_and_use_binding_code(
            binding_code, env['test_user_id']
        )
        merchant_id = bind_result['merchant_id']
        
        # 2. 测试状态转换序列
        status_sequence = [
            'pending_submission',
            'pending_approval', 
            'approved',
            'published',
            'expired'
        ]
        
        for status in status_sequence:
            update_success = await MerchantManager.update_merchant_status(merchant_id, status)
            assert update_success == True
            
            merchant = await MerchantManager.get_merchant(merchant_id)
            assert merchant['status'] == status
            
            # 测试状态标准化
            normalized = MERCHANT_STATUS.normalize(status)
            assert normalized == status  # V2状态应该保持不变
    
    @pytest.mark.asyncio
    async def test_media_file_handling(self, setup_test_environment):
        """测试媒体文件处理机制"""
        env = await setup_test_environment
        
        # 1. 创建测试商户
        binding_code = await BindingCodesManager.generate_binding_code()
        bind_result = await BindingCodesManager.validate_and_use_binding_code(
            binding_code, env['test_user_id']
        )
        merchant_id = bind_result['merchant_id']
        
        # 2. 模拟媒体文件数据
        test_media_files = [
            {
                'telegram_file_id': 'BAADBAADrwADBGZOUgKGUGZ_image_001',
                'file_type': 'image',
                'merchant_id': merchant_id
            },
            {
                'telegram_file_id': 'BAADBAADsAADBGZOUgKGUGZ_video_001',
                'file_type': 'video', 
                'merchant_id': merchant_id
            }
        ]
        
        # 3. 更新商户profile_data包含媒体文件信息
        profile_data = {
            'media_files': [file['telegram_file_id'] for file in test_media_files],
            'file_types': [file['file_type'] for file in test_media_files]
        }
        
        update_success = await MerchantManager.update_merchant(merchant_id, {
            'profile_data': profile_data
        })
        assert update_success == True
        
        # 4. 验证媒体文件信息存储
        merchant = await MerchantManager.get_merchant(merchant_id)
        stored_profile = merchant['profile_data']
        assert 'media_files' in stored_profile
        assert len(stored_profile['media_files']) == 2
        assert stored_profile['media_files'][0] == test_media_files[0]['telegram_file_id']
    
    @pytest.mark.asyncio
    async def test_web_backend_display_preparation(self, setup_test_environment):
        """测试Web后台显示数据准备"""
        env = await setup_test_environment
        
        # 1. 创建完整的测试商户
        binding_code = await BindingCodesManager.generate_binding_code()
        bind_result = await BindingCodesManager.validate_and_use_binding_code(
            binding_code, env['test_user_id']
        )
        merchant_id = bind_result['merchant_id']
        
        # 2. 填充完整商户信息
        complete_data = {
            'name': '完整测试商户',
            'custom_description': '这是一个完整的商户描述',
            'contact_info': '联系方式测试',
            'p_price': '600',
            'pp_price': '900',
            'status': 'pending_approval',
            'profile_data': {
                'city': '北京市',
                'district': '朝阳区',
                'advantages': '专业技能强',
                'disadvantages': '时间较少',
                'media_files': ['file_id_1', 'file_id_2']
            }
        }
        
        await MerchantManager.update_merchant(merchant_id, complete_data)
        
        # 3. 测试Web后台数据获取
        merchant_details = await MerchantManager.get_merchant_details(merchant_id)
        assert merchant_details is not None
        assert merchant_details['name'] == complete_data['name']
        assert merchant_details['status'] == 'pending_approval'
        
        # 4. 测试状态显示转换
        normalized_status = MERCHANT_STATUS.normalize(merchant_details['status'])
        display_name = MERCHANT_STATUS.get_display_name(normalized_status)
        assert display_name == '等待审核'
        
        # 5. 测试批准操作
        approve_success = await MerchantManager.approve_merchant_post(merchant_id)
        assert approve_success == True
        
        approved_merchant = await MerchantManager.get_merchant(merchant_id)
        assert approved_merchant['status'] == 'approved'
    
    @pytest.mark.asyncio
    async def test_concurrent_binding_codes(self, setup_test_environment):
        """测试并发绑定码使用场景"""
        env = await setup_test_environment
        
        # 1. 生成一个绑定码
        binding_code = await BindingCodesManager.generate_binding_code()
        
        # 2. 模拟两个用户同时使用同一个绑定码
        user1_id = 11111
        user2_id = 22222
        
        # 3. 并发执行绑定操作
        tasks = [
            BindingCodesManager.validate_and_use_binding_code(binding_code, user1_id),
            BindingCodesManager.validate_and_use_binding_code(binding_code, user2_id)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 4. 验证只有一个用户成功绑定
        success_count = sum(1 for result in results if result['success'])
        assert success_count == 1
        
        # 5. 验证失败的用户收到正确错误信息
        failed_results = [result for result in results if not result['success']]
        assert len(failed_results) == 1
        assert '无效' in failed_results[0]['message'] or '已被使用' in failed_results[0]['message']


class TestMerchantOnboardingArchitectureIssues:
    """商户入驻架构问题测试类"""
    
    def test_fsm_implementation_gap(self):
        """测试FSM实现缺陷"""
        
        # 1. 验证状态定义存在
        assert hasattr(MerchantOnboardingStates, 'AwaitingName')
        assert hasattr(MerchantOnboardingStates, 'AwaitingConfirmation')
        
        # 2. 检查状态转换规则是否定义
        # 当前StateValidator.ALLOWED_TRANSITIONS中没有MerchantOnboardingStates的规则
        from dialogs.states import StateValidator
        
        # 3. 发现问题：MerchantOnboardingStates状态没有转换规则
        onboarding_states = [
            MerchantOnboardingStates.AwaitingName,
            MerchantOnboardingStates.AwaitingCity,
            MerchantOnboardingStates.AwaitingConfirmation
        ]
        
        for state in onboarding_states:
            # 这些状态在ALLOWED_TRANSITIONS中都不存在
            assert state not in StateValidator.ALLOWED_TRANSITIONS
        
        # 4. 发现问题：状态类型识别不支持MerchantOnboardingStates
        from dialogs.states import get_user_type_from_state
        user_type = get_user_type_from_state(MerchantOnboardingStates.AwaitingName)
        assert user_type is None  # 确认缺陷存在
    
    def test_handler_implementation_mismatch(self):
        """测试处理器实现不匹配问题"""
        
        # 1. 检查MerchantHandler是否正确实现FSM流程
        from handlers.merchant import MerchantHandler, BINDING_FLOW_STEPS
        
        # 2. 发现问题：使用7步静态配置而不是FSM
        assert 'title' in BINDING_FLOW_STEPS[1]
        assert 'options' in BINDING_FLOW_STEPS[1]
        
        # 3. 确认7步流程被注释禁用
        # 注释部分包含了实际的FSM处理逻辑
        
    @pytest.mark.asyncio
    async def test_missing_fsm_integration(self):
        """测试缺失的FSM集成"""
        
        # 1. 验证当前系统只支持快速注册模式
        test_user_id = 99999
        
        # 生成绑定码
        binding_code = await BindingCodesManager.generate_binding_code()
        
        # 使用绑定码
        result = await BindingCodesManager.validate_and_use_binding_code(
            binding_code, test_user_id
        )
        
        # 2. 确认只创建了空白商户档案
        assert result['success'] == True
        merchant_id = result['merchant_id']
        
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['name'] == '待完善'
        assert merchant['status'] == 'pending_submission'
        
        # 3. 发现问题：没有FSM状态机引导用户填写信息
        # 用户需要手动更新信息，而不是通过对话式流程


if __name__ == '__main__':
    # 运行测试的示例代码
    import asyncio
    
    async def run_basic_tests():
        """运行基础测试"""
        print("开始商户入驻流程测试...")
        
        # 测试绑定码生成
        binding_code = await BindingCodesManager.generate_binding_code()
        print(f"生成绑定码: {binding_code}")
        
        # 测试绑定流程
        test_user_id = 12345
        result = await BindingCodesManager.validate_and_use_binding_code(
            binding_code, test_user_id
        )
        print(f"绑定结果: {result}")
        
        if result['success']:
            merchant_id = result['merchant_id']
            merchant = await MerchantManager.get_merchant(merchant_id)
            print(f"创建的商户: {merchant}")
        
        print("测试完成")
    
    # 取消注释以运行基础测试
    # asyncio.run(run_basic_tests())