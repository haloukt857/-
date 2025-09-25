# -*- coding: utf-8 -*-
"""
激励系统集成测试
验证双向评价系统与激励系统的完整集成流程

测试流程：
1. 创建用户、商家、订单
2. 用户提交评价
3. 商家确认评价有效性
4. 验证激励奖励发放
5. 验证等级升级
6. 验证勋章获得
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch

# 导入被测试的模块
from services.incentive_processor import IncentiveProcessor, incentive_processor
from database.db_reviews import ReviewManager
from database.db_users import UserManager
from database.db_orders import OrderManager
from database.db_incentives import IncentiveManager


class TestIncentiveSystemIntegration:
    """激励系统集成测试"""
    
    @pytest.fixture
    async def setup_test_data(self):
        """设置测试数据"""
        test_data = {
            'user_id': 123456789,
            'merchant_id': 1,
            'order_id': 100,
            'review_id': 50,
            'ratings': {
                'appearance': 9,
                'figure': 8,
                'service': 10,
                'attitude': 9,
                'environment': 8
            }
        }
        
        # 模拟用户初始状态
        mock_user = {
            'user_id': test_data['user_id'],
            'username': 'test_user',
            'xp': 80,  # 接近升级的经验值
            'points': 200,
            'level_name': '新手',
            'badges': '[]',
            'order_count': 2
        }
        
        # 模拟等级配置
        mock_levels = [
            {'id': 1, 'level_name': '新手', 'xp_required': 0},
            {'id': 2, 'level_name': '老司机', 'xp_required': 100},
            {'id': 3, 'level_name': '大师', 'xp_required': 500}
        ]
        
        # 模拟勋章配置
        mock_badges = [
            {
                'id': 1,
                'badge_name': '三连胜',
                'badge_icon': '🏆',
                'description': '完成3个订单',
                'triggers': [
                    {'trigger_type': 'order_count', 'trigger_value': 3}
                ]
            },
            {
                'id': 2,
                'badge_name': '评价达人',
                'badge_icon': '⭐',
                'description': '总积分达到300',
                'triggers': [
                    {'trigger_type': 'total_points', 'trigger_value': 300}
                ]
            }
        ]
        
        return {
            'test_data': test_data,
            'mock_user': mock_user,
            'mock_levels': mock_levels,
            'mock_badges': mock_badges
        }
    
    @pytest.mark.asyncio
    async def test_complete_review_incentive_flow(self, setup_test_data):
        """测试完整的评价激励流程"""
        
        data = await setup_test_data
        test_data = data['test_data']
        mock_user = data['mock_user']
        mock_levels = data['mock_levels']
        mock_badges = data['mock_badges']
        
        # Mock数据库操作
        with patch.object(UserManager, 'get_user_profile', return_value=mock_user), \
             patch.object(UserManager, 'grant_rewards', return_value=True), \
             patch.object(UserManager, 'update_user_level_and_badges', return_value=True), \
             patch.object(IncentiveManager, 'get_all_levels', return_value=mock_levels), \
             patch.object(IncentiveManager, 'get_all_badges_with_triggers', return_value=mock_badges), \
             patch.object(OrderManager, 'get_orders_by_user', return_value=[{'status': '已完成'}, {'status': '已完成'}, {'status': '已完成'}]), \
             patch.object(ReviewManager, 'get_review_detail', return_value={
                'id': test_data['review_id'],
                'order_id': test_data['order_id'],
                'customer_user_id': test_data['user_id'],
                'rating_appearance': 9,
                'rating_figure': 8,
                'rating_service': 10,
                'rating_attitude': 9,
                'rating_environment': 8,
                'text_review_by_user': '服务很好，环境不错',
                'is_confirmed_by_merchant': False
             }):
            
            # 执行激励处理
            result = await incentive_processor.process_confirmed_review_rewards(
                user_id=test_data['user_id'],
                review_id=test_data['review_id'],
                order_id=test_data['order_id']
            )
            
            # 验证激励处理结果
            assert result['success'] is True, f"激励处理失败: {result.get('error')}"
            assert result['rewards_granted'] is True, "奖励发放失败"
            assert result['points_earned'] > 0, "积分奖励为0"
            assert result['xp_earned'] > 0, "经验奖励为0"
            
            # 验证等级升级
            # 用户初始80经验 + 至少20经验奖励 = 100+，应该升级到"老司机"
            assert result['level_upgraded'] is True, "用户应该升级"
            assert result['new_level'] == '老司机', f"用户应该升级到老司机，实际: {result['new_level']}"
            
            # 验证勋章获得
            assert len(result['new_badges']) > 0, "用户应该获得勋章"
            badge_names = [badge['badge_name'] for badge in result['new_badges']]
            assert '三连胜' in badge_names, "用户应该获得'三连胜'勋章"
            
            print(f"✅ 测试通过: 用户获得 {result['points_earned']} 积分, {result['xp_earned']} 经验")
            print(f"✅ 等级升级: {result['old_level']} -> {result['new_level']}")
            print(f"✅ 获得勋章: {[b['badge_name'] for b in result['new_badges']]}")
    
    @pytest.mark.asyncio 
    async def test_review_reward_calculation(self, setup_test_data):
        """测试评价奖励计算逻辑"""
        
        data = await setup_test_data
        test_data = data['test_data']
        
        # Mock高分评价
        high_rating_review = {
            'id': 1,
            'rating_appearance': 9,
            'rating_figure': 9, 
            'rating_service': 10,
            'rating_attitude': 10,
            'rating_environment': 9,
            'text_review_by_user': '服务非常棒，强烈推荐给大家!'
        }
        
        with patch.object(ReviewManager, 'get_review_detail', return_value=high_rating_review):
            # 测试奖励计算
            rewards = await IncentiveProcessor._calculate_review_base_rewards(1)
            
            assert rewards is not None, "奖励计算失败"
            
            # 基础奖励: 50积分 + 20经验
            # 高分奖励: +25积分 + 10经验 (平均分9.4 >= 8.0)
            # 文字奖励: +15积分 + 5经验 (文字长度 >= 10)
            # 总计: 90积分 + 35经验
            expected_points = 50 + 25 + 15  # 90
            expected_xp = 20 + 10 + 5       # 35
            
            assert rewards['points'] == expected_points, f"积分计算错误: 期望{expected_points}, 实际{rewards['points']}"
            assert rewards['xp'] == expected_xp, f"经验计算错误: 期望{expected_xp}, 实际{rewards['xp']}"
            
            print(f"✅ 高质量评价奖励: {rewards['points']} 积分, {rewards['xp']} 经验")
    
    @pytest.mark.asyncio
    async def test_level_upgrade_logic(self, setup_test_data):
        """测试等级升级逻辑"""
        
        data = await setup_test_data
        mock_levels = data['mock_levels']
        
        # 测试不同经验值的升级情况
        test_cases = [
            {'xp': 50, 'current_level': '新手', 'expected_level': '新手', 'should_upgrade': False},
            {'xp': 150, 'current_level': '新手', 'expected_level': '老司机', 'should_upgrade': True},
            {'xp': 600, 'current_level': '老司机', 'expected_level': '大师', 'should_upgrade': True}
        ]
        
        for case in test_cases:
            mock_user = {
                'xp': case['xp'],
                'level_name': case['current_level']
            }
            
            with patch.object(UserManager, 'get_user_profile', return_value=mock_user), \
                 patch.object(IncentiveManager, 'get_all_levels', return_value=mock_levels), \
                 patch.object(UserManager, 'update_user_level_and_badges', return_value=True):
                
                result = await IncentiveProcessor._check_and_process_level_upgrade(123456789)
                
                assert result['upgraded'] == case['should_upgrade'], \
                    f"XP{case['xp']}: 升级判断错误，期望{case['should_upgrade']}, 实际{result['upgraded']}"
                
                if case['should_upgrade']:
                    assert result['new_level'] == case['expected_level'], \
                        f"XP{case['xp']}: 等级错误，期望{case['expected_level']}, 实际{result['new_level']}"
                
                print(f"✅ XP{case['xp']}: {case['current_level']} -> {'升级' if case['should_upgrade'] else '不升级'}")
    
    @pytest.mark.asyncio
    async def test_badge_trigger_logic(self, setup_test_data):
        """测试勋章触发逻辑"""
        
        data = await setup_test_data
        mock_badges = data['mock_badges']
        
        # 测试满足勋章条件的用户
        mock_user_qualified = {
            'user_id': 123456789,
            'badges': '[]',  # 没有勋章
            'points': 350,   # 满足"评价达人"的300积分要求
            'order_count': 5 # 满足"三连胜"的3订单要求
        }
        
        # Mock统计数据
        mock_stats = {
            'total_points': 350,
            'order_count': 5,
            'perfect_reviews': 0,
            'consecutive_reviews': 0
        }
        
        with patch.object(UserManager, 'get_user_profile', return_value=mock_user_qualified), \
             patch.object(IncentiveManager, 'get_all_badges_with_triggers', return_value=mock_badges), \
             patch.object(IncentiveProcessor, '_collect_user_statistics', return_value=mock_stats), \
             patch.object(UserManager, 'update_user_level_and_badges', return_value=True):
            
            result = await IncentiveProcessor._check_and_grant_badges(123456789)
            
            assert len(result['new_badges']) == 2, f"应该获得2个勋章，实际获得{len(result['new_badges'])}个"
            
            badge_names = [badge['badge_name'] for badge in result['new_badges']]
            assert '三连胜' in badge_names, "应该获得'三连胜'勋章"
            assert '评价达人' in badge_names, "应该获得'评价达人'勋章"
            
            print(f"✅ 勋章触发测试通过: 获得勋章 {badge_names}")


if __name__ == '__main__':
    # 运行测试
    async def run_tests():
        test_instance = TestIncentiveSystemIntegration()
        
        # 手动设置测试数据
        setup_data = await test_instance.setup_test_data()
        
        try:
            print("🧪 开始测试激励系统集成...")
            
            # 运行各项测试
            await test_instance.test_complete_review_incentive_flow(setup_data)
            print("✅ 完整流程测试通过")
            
            await test_instance.test_review_reward_calculation(setup_data)
            print("✅ 奖励计算测试通过")
            
            await test_instance.test_level_upgrade_logic(setup_data)
            print("✅ 等级升级测试通过")
            
            await test_instance.test_badge_trigger_logic(setup_data)
            print("✅ 勋章触发测试通过")
            
            print("\n🎉 所有激励系统测试通过!")
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            raise
    
    # 使用asyncio运行异步测试
    asyncio.run(run_tests())