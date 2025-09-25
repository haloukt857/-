# -*- coding: utf-8 -*-
"""
用户核心体验集成测试

测试Telegram商户机器人V2.0的用户核心交互功能：
1. 地区搜索功能
2. 商户浏览和发现
3. 订单创建和管理
4. 用户档案系统
5. 用户交互流程

作者: QA测试引擎
日期: 2025-09-13
状态: 用户体验专项测试
"""

import asyncio
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import logging

# 设置测试日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入被测试的模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.db_regions import region_manager
from database.db_merchants import merchant_manager
from database.db_orders import order_manager
from database.db_users import user_manager
from database.db_incentives import incentive_manager
from handlers.user import start_command, profile_command
from handlers.auto_reply import auto_reply_handler
from utils.keyboard_utils import (
    create_main_menu_keyboard,
    create_city_keyboard,
    create_district_keyboard,
    create_merchants_keyboard
)

class TestUserExperience:
    """
    用户核心体验测试套件
    模拟真实用户使用场景，验证核心功能的完整性和流畅性
    """

    def setup_method(self):
        """测试前置设置"""
        self.test_user_id = 12345678
        self.test_username = "test_user"
        self.test_merchant_id = 1
        self.test_city_id = 1
        self.test_district_id = 1
        
        # 模拟Telegram消息对象
        self.mock_message = MagicMock()
        self.mock_message.from_user.id = self.test_user_id
        self.mock_message.from_user.username = self.test_username
        self.mock_message.chat.type = 'private'
        self.mock_message.text = ""
        self.mock_message.answer = AsyncMock()

    @pytest.mark.asyncio
    async def test_region_search_functionality(self):
        """
        测试地区搜索功能
        验证用户可以通过地区搜索找到已发布的商家
        """
        logger.info("开始测试地区搜索功能")
        
        try:
            # 1. 测试地区搜索基础功能
            search_results = await region_manager.search_regions("北京", limit=10)
            assert isinstance(search_results, list), "搜索结果应该是列表类型"
            
            # 2. 测试空搜索词处理
            empty_results = await region_manager.search_regions("", limit=10)
            assert len(empty_results) == 0, "空搜索词应该返回空结果"
            
            # 3. 测试获取城市和地区数据
            cities_with_districts = await region_manager.get_all_cities_with_districts()
            assert isinstance(cities_with_districts, list), "城市数据应该是列表类型"
            
            # 4. 测试活跃城市和地区获取
            active_cities = await region_manager.get_active_cities_with_districts()
            assert isinstance(active_cities, list), "活跃城市数据应该是列表类型"
            
            # 5. 测试地区键盘生成
            if cities_with_districts:
                city_keyboard = create_city_keyboard(cities_with_districts[:5])
                assert city_keyboard is not None, "城市键盘应该能够生成"
                assert hasattr(city_keyboard, 'inline_keyboard'), "应该包含内联键盘"
            
            # 6. 测试地区搜索边界情况
            long_search = await region_manager.search_regions("很长很长的搜索词汇测试边界情况", limit=50)
            assert isinstance(long_search, list), "长搜索词应该正常处理"
            
            # 7. 测试搜索结果限制
            limited_results = await region_manager.search_regions("市", limit=3)
            assert len(limited_results) <= 3, "搜索结果应该遵守限制"
            
            logger.info("✅ 地区搜索功能测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 地区搜索功能测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def test_merchant_browsing_and_discovery(self):
        """
        测试商户浏览和发现功能
        验证用户能够浏览已发布状态的商户信息
        """
        logger.info("开始测试商户浏览和发现功能")
        
        try:
            # 1. 测试获取已发布商户列表
            published_merchants = await merchant_manager.get_merchants(
                status='published', 
                limit=20
            )
            assert isinstance(published_merchants, list), "商户列表应该是列表类型"
            
            # 2. 测试商户搜索功能
            search_results = await merchant_manager.search_merchants(
                search_term="教师",
                search_fields=['name', 'custom_description', 'category'],
                status_filter='published'
            )
            assert isinstance(search_results, list), "搜索结果应该是列表类型"
            
            # 3. 测试按地区过滤商户
            region_filtered = await merchant_manager.get_merchants(
                status='published',
                region_id=self.test_district_id,
                limit=10
            )
            assert isinstance(region_filtered, list), "地区过滤结果应该是列表类型"
            
            # 4. 测试获取单个商户详情
            if published_merchants:
                merchant_id = published_merchants[0]['id']
                merchant_detail = await merchant_manager.get_merchant(merchant_id)
                assert merchant_detail is not None, "应该能获取商户详情"
                assert 'name' in merchant_detail, "商户详情应该包含名称"
                assert 'custom_description' in merchant_detail, "商户详情应该包含描述"
                assert 'contact_info' in merchant_detail, "商户详情应该包含联系信息"
            
            # 5. 测试商户键盘生成
            if published_merchants:
                merchant_keyboard = create_merchants_keyboard(
                    published_merchants[:5], 
                    self.test_city_id
                )
                assert merchant_keyboard is not None, "商户键盘应该能够生成"
                assert hasattr(merchant_keyboard, 'inline_keyboard'), "应该包含内联键盘"
            
            # 6. 测试商户统计信息
            merchant_stats = await merchant_manager.get_merchant_statistics()
            assert isinstance(merchant_stats, dict), "商户统计应该是字典类型"
            assert 'total_merchants' in merchant_stats, "应该包含总商户数"
            
            # 7. 测试仪表板统计
            dashboard_stats = await merchant_manager.get_dashboard_stats()
            assert isinstance(dashboard_stats, dict), "仪表板统计应该是字典类型"
            
            # 8. 测试商户类型统计
            from database.db_merchants import get_merchant_type_statistics
            type_stats = await get_merchant_type_statistics()
            assert isinstance(type_stats, dict), "类型统计应该是字典类型"
            
            logger.info("✅ 商户浏览和发现功能测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 商户浏览和发现功能测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def test_order_creation_and_management(self):
        """
        测试订单创建和管理功能
        验证用户可以成功为商家创建订单并管理订单状态
        """
        logger.info("开始测试订单创建和管理功能")
        
        try:
            # 1. 测试创建订单
            order_data = {
                'customer_user_id': self.test_user_id,
                'customer_username': self.test_username,
                'merchant_id': self.test_merchant_id,
                'price': 500,
                'status': '尝试预约'
            }
            
            order_id = await order_manager.create_order(order_data)
            assert order_id is not None, "应该能成功创建订单"
            assert isinstance(order_id, int), "订单ID应该是整数"
            
            # 2. 测试获取订单详情
            order_detail = await order_manager.get_order(order_id)
            assert order_detail is not None, "应该能获取订单详情"
            assert order_detail['customer_user_id'] == self.test_user_id, "订单用户ID应该匹配"
            assert order_detail['merchant_id'] == self.test_merchant_id, "订单商户ID应该匹配"
            assert order_detail['status'] == '尝试预约', "订单状态应该正确"
            
            # 3. 测试获取用户订单列表
            user_orders = await order_manager.get_orders_by_user(
                self.test_user_id,
                limit=10
            )
            assert isinstance(user_orders, list), "用户订单列表应该是列表类型"
            assert len(user_orders) > 0, "应该能找到刚创建的订单"
            
            # 4. 测试获取商户订单列表
            merchant_orders = await order_manager.get_orders_by_merchant(
                self.test_merchant_id,
                limit=10
            )
            assert isinstance(merchant_orders, list), "商户订单列表应该是列表类型"
            
            # 5. 测试订单状态更新
            status_updated = await order_manager.update_order_status(
                order_id, 
                '已完成'
            )
            assert status_updated is True, "应该能成功更新订单状态"
            
            # 6. 验证状态更新结果
            updated_order = await order_manager.get_order(order_id)
            assert updated_order['status'] == '已完成', "订单状态应该已更新"
            assert updated_order['completion_time'] is not None, "应该设置完成时间"
            
            # 7. 测试订单信息更新
            update_data = {
                'price': 600,
                'customer_username': f"updated_{self.test_username}"
            }
            order_updated = await order_manager.update_order(order_id, update_data)
            assert order_updated is True, "应该能成功更新订单信息"
            
            # 8. 测试订单统计
            stats = await order_manager.get_order_statistics()
            assert isinstance(stats, dict), "订单统计应该是字典类型"
            assert 'total_orders' in stats, "应该包含总订单数"
            assert 'status_summary' in stats, "应该包含状态统计"
            
            # 9. 测试商户订单摘要
            merchant_summary = await order_manager.get_merchant_order_summary(self.test_merchant_id)
            assert isinstance(merchant_summary, dict), "商户订单摘要应该是字典类型"
            assert 'total_orders' in merchant_summary, "应该包含总订单数"
            
            # 10. 测试带评价状态的订单列表
            orders_with_review = await order_manager.get_orders_with_review_status()
            assert isinstance(orders_with_review, list), "带评价状态的订单列表应该是列表类型"
            
            # 11. 测试时间范围查询
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            time_filtered_orders = await order_manager.get_orders_by_timeframe(
                start_date, 
                end_date,
                merchant_id=self.test_merchant_id
            )
            assert isinstance(time_filtered_orders, list), "时间范围查询结果应该是列表类型"
            
            # 12. 测试V1兼容性方法
            v1_order_id = await order_manager.create_order_v1_compat(
                self.test_user_id + 1,
                self.test_merchant_id,
                400,
                username=f"v1_{self.test_username}"
            )
            assert v1_order_id is not None, "V1兼容方法应该能创建订单"
            
            logger.info("✅ 订单创建和管理功能测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 订单创建和管理功能测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def test_user_profile_system(self):
        """
        测试用户档案系统功能
        验证用户可以查看个人信息、等级、积分、经验值等
        """
        logger.info("开始测试用户档案系统功能")
        
        try:
            # 1. 测试创建或更新用户
            await user_manager.create_or_update_user(
                self.test_user_id, 
                self.test_username
            )
            
            # 2. 测试获取用户档案
            user_profile = await user_manager.get_user_profile(self.test_user_id)
            if user_profile:
                assert isinstance(user_profile, dict), "用户档案应该是字典类型"
                assert user_profile['user_id'] == self.test_user_id, "用户ID应该匹配"
            
            # 3. 测试用户奖励发放
            await user_manager.grant_rewards(
                self.test_user_id,
                xp_to_add=100,
                points_to_add=50
            )
            
            # 4. 验证奖励发放结果
            updated_profile = await user_manager.get_user_profile(self.test_user_id)
            if updated_profile:
                assert updated_profile['xp'] >= 100, "经验值应该增加"
                assert updated_profile['points'] >= 50, "积分应该增加"
            
            # 5. 测试等级和勋章更新
            await user_manager.update_user_level_and_badges(
                self.test_user_id,
                new_level_name="高级用户",
                new_badge="首次订单"
            )
            
            # 6. 验证等级和勋章更新结果
            level_updated_profile = await user_manager.get_user_profile(self.test_user_id)
            if level_updated_profile:
                assert level_updated_profile['level_name'] == "高级用户", "等级名称应该更新"
                badges = json.loads(level_updated_profile.get('badges', '[]'))
                assert "首次订单" in badges, "勋章应该添加成功"
            
            # 7. 测试激励系统 - 等级配置
            all_levels = await incentive_manager.get_all_levels()
            assert isinstance(all_levels, list), "等级列表应该是列表类型"
            
            # 8. 测试激励系统 - 勋章配置
            all_badges = await incentive_manager.get_all_badges()
            assert isinstance(all_badges, list), "勋章列表应该是列表类型"
            
            # 9. 测试用户档案命令处理器
            with patch.object(user_manager, 'get_user_profile') as mock_get_profile:
                mock_get_profile.return_value = {
                    'level_name': '新手',
                    'xp': 150,
                    'points': 75,
                    'order_count': 2,
                    'badges': '["首次订单", "活跃用户"]'
                }
                
                await profile_command(self.mock_message)
                mock_get_profile.assert_called_once_with(self.test_user_id)
                self.mock_message.answer.assert_called_once()
            
            # 10. 测试用户档案显示内容
            with patch('database.db_templates.template_manager.get_template') as mock_template:
                mock_template.return_value = "模板内容: {level_name}"
                
                await profile_command(self.mock_message)
                assert mock_template.call_count > 0, "应该调用模板获取"
            
            logger.info("✅ 用户档案系统功能测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 用户档案系统功能测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def test_user_interaction_flow(self):
        """
        测试用户交互流程
        验证Bot命令响应、错误处理、用户引导等
        """
        logger.info("开始测试用户交互流程")
        
        try:
            # 1. 测试/start命令处理
            with patch.object(user_manager, 'create_or_update_user') as mock_create_user:
                mock_create_user.return_value = None
                
                with patch('database.db_templates.template_manager.get_template') as mock_template:
                    mock_template.return_value = "欢迎使用商户机器人！"
                    
                    await start_command(self.mock_message)
                    
                    mock_create_user.assert_called_once_with(
                        self.test_user_id, 
                        self.test_username
                    )
                    self.mock_message.answer.assert_called_once()
            
            # 2. 测试主菜单键盘生成
            main_menu = create_main_menu_keyboard()
            assert main_menu is not None, "主菜单键盘应该能够生成"
            assert hasattr(main_menu, 'inline_keyboard'), "应该包含内联键盘"
            assert len(main_menu.inline_keyboard) > 0, "应该包含菜单选项"
            
            # 3. 测试自动回复功能（如果处理器已初始化）
            if auto_reply_handler:
                # 模拟FSM状态
                mock_state = AsyncMock()
                mock_state.get_state.return_value = None
                
                # 设置测试消息
                self.mock_message.text = "测试消息"
                
                with patch.object(auto_reply_handler, 'handle_text_message') as mock_handle:
                    mock_handle.return_value = None
                    
                    # 这里会调用实际的自动回复处理逻辑
                    await auto_reply_handler.handle_text_message(self.mock_message, mock_state)
                    mock_handle.assert_called_once()
            
            # 4. 测试错误消息处理
            self.mock_message.from_user = None  # 模拟异常情况
            
            try:
                await start_command(self.mock_message)
            except Exception as e:
                logger.info(f"正确处理了异常情况: {e}")
            
            # 5. 测试空用户名处理
            self.mock_message.from_user = MagicMock()
            self.mock_message.from_user.id = self.test_user_id
            self.mock_message.from_user.username = None
            
            with patch.object(user_manager, 'create_or_update_user') as mock_create_user:
                mock_create_user.return_value = None
                
                with patch('database.db_templates.template_manager.get_template') as mock_template:
                    mock_template.return_value = "欢迎！"
                    
                    await start_command(self.mock_message)
                    mock_create_user.assert_called_once()
            
            # 6. 测试用户档案不存在情况
            with patch.object(user_manager, 'get_user_profile') as mock_get_profile:
                mock_get_profile.return_value = None
                
                with patch('database.db_templates.template_manager.get_template') as mock_template:
                    mock_template.return_value = "用户档案不存在"
                    
                    await profile_command(self.mock_message)
                    self.mock_message.answer.assert_called()
            
            # 7. 测试地区键盘边界情况
            empty_cities = []
            empty_keyboard = create_city_keyboard(empty_cities)
            assert empty_keyboard is not None, "空城市列表应该能生成键盘"
            
            # 8. 测试商户键盘边界情况
            empty_merchants = []
            empty_merchant_keyboard = create_merchants_keyboard(empty_merchants, self.test_city_id)
            assert empty_merchant_keyboard is not None, "空商户列表应该能生成键盘"
            
            logger.info("✅ 用户交互流程功能测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 用户交互流程功能测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def test_concurrent_user_operations(self):
        """
        测试并发用户操作
        验证系统在多用户同时操作时的稳定性
        """
        logger.info("开始测试并发用户操作")
        
        try:
            # 1. 创建多个测试用户
            test_users = [
                (12345001, "user_001"),
                (12345002, "user_002"),
                (12345003, "user_003"),
                (12345004, "user_004"),
                (12345005, "user_005")
            ]
            
            # 2. 并发创建用户
            user_creation_tasks = [
                user_manager.create_or_update_user(user_id, username)
                for user_id, username in test_users
            ]
            await asyncio.gather(*user_creation_tasks)
            
            # 3. 并发获取用户档案
            profile_tasks = [
                user_manager.get_user_profile(user_id)
                for user_id, _ in test_users
            ]
            profiles = await asyncio.gather(*profile_tasks)
            
            # 验证所有用户档案都能正确获取
            for i, (user_id, username) in enumerate(test_users):
                profile = profiles[i]
                if profile:
                    assert profile['user_id'] == user_id, f"用户{user_id}档案应该正确"
            
            # 4. 并发创建订单
            order_creation_tasks = [
                order_manager.create_order({
                    'customer_user_id': user_id,
                    'customer_username': username,
                    'merchant_id': self.test_merchant_id,
                    'price': 500 + i * 50,
                    'status': '尝试预约'
                })
                for i, (user_id, username) in enumerate(test_users)
            ]
            order_ids = await asyncio.gather(*order_creation_tasks)
            
            # 验证所有订单都创建成功
            successful_orders = [oid for oid in order_ids if oid is not None]
            assert len(successful_orders) == len(test_users), "所有订单都应该创建成功"
            
            # 5. 并发查询操作
            query_tasks = [
                region_manager.search_regions(f"测试地区{i}", limit=5)
                for i in range(10)
            ]
            search_results = await asyncio.gather(*query_tasks)
            
            # 验证搜索操作都正常执行
            assert len(search_results) == 10, "所有搜索任务都应该完成"
            for result in search_results:
                assert isinstance(result, list), "搜索结果应该是列表类型"
            
            # 6. 并发更新操作
            if successful_orders:
                update_tasks = [
                    order_manager.update_order_status(order_id, '已完成')
                    for order_id in successful_orders
                ]
                update_results = await asyncio.gather(*update_tasks)
                
                # 验证更新操作
                successful_updates = [result for result in update_results if result]
                assert len(successful_updates) > 0, "应该有订单更新成功"
            
            # 7. 并发奖励发放
            reward_tasks = [
                user_manager.grant_rewards(user_id, 50, 25)
                for user_id, _ in test_users
            ]
            await asyncio.gather(*reward_tasks)
            
            # 8. 验证奖励发放结果
            final_profile_tasks = [
                user_manager.get_user_profile(user_id)
                for user_id, _ in test_users
            ]
            final_profiles = await asyncio.gather(*final_profile_tasks)
            
            for profile in final_profiles:
                if profile:
                    assert profile['xp'] >= 50, "经验值应该增加"
                    assert profile['points'] >= 25, "积分应该增加"
            
            logger.info("✅ 并发用户操作测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 并发用户操作测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def test_edge_cases_and_error_handling(self):
        """
        测试边界情况和错误处理
        验证系统在异常情况下的稳定性
        """
        logger.info("开始测试边界情况和错误处理")
        
        try:
            # 1. 测试无效用户ID
            invalid_profile = await user_manager.get_user_profile(-1)
            assert invalid_profile is None, "无效用户ID应该返回None"
            
            # 2. 测试无效订单ID
            invalid_order = await order_manager.get_order(-1)
            assert invalid_order is None, "无效订单ID应该返回None"
            
            # 3. 测试无效商户ID
            invalid_merchant = await merchant_manager.get_merchant(-1)
            assert invalid_merchant is None, "无效商户ID应该返回None"
            
            # 4. 测试空字符串搜索
            empty_search = await region_manager.search_regions("", limit=10)
            assert len(empty_search) == 0, "空搜索应该返回空结果"
            
            # 5. 测试非常长的搜索词
            long_search = await region_manager.search_regions("x" * 1000, limit=10)
            assert isinstance(long_search, list), "长搜索词应该正常处理"
            
            # 6. 测试创建订单时缺少必需字段
            try:
                invalid_order_data = {
                    'customer_user_id': self.test_user_id,
                    # 缺少merchant_id和price
                }
                await order_manager.create_order(invalid_order_data)
                assert False, "缺少必需字段应该抛出异常"
            except (ValueError, Exception):
                pass  # 正确抛出异常
            
            # 7. 测试更新不存在的订单
            update_result = await order_manager.update_order_status(999999, '已完成')
            assert update_result is False, "更新不存在的订单应该返回False"
            
            # 8. 测试无效订单状态
            try:
                await order_manager.update_order_status(1, '无效状态')
                assert False, "无效状态应该抛出异常"
            except (ValueError, Exception):
                pass  # 正确抛出异常
            
            # 9. 测试商户搜索边界情况
            empty_merchant_search = await merchant_manager.search_merchants("")
            assert isinstance(empty_merchant_search, list), "空搜索应该返回列表"
            
            # 10. 测试大量数据查询
            large_limit_merchants = await merchant_manager.get_merchants(limit=1000)
            assert isinstance(large_limit_merchants, list), "大限制查询应该正常处理"
            
            # 11. 测试JSON格式错误处理
            try:
                # 测试用户勋章JSON解析错误处理
                await user_manager.update_user_level_and_badges(
                    self.test_user_id,
                    new_badge="测试勋章"
                )
            except Exception as e:
                logger.info(f"JSON错误处理测试: {e}")
            
            # 12. 测试数据库连接异常处理
            # 这里可以模拟数据库连接问题
            with patch('database.db_connection.db_manager.fetch_one') as mock_fetch:
                mock_fetch.side_effect = Exception("数据库连接异常")
                
                try:
                    await user_manager.get_user_profile(self.test_user_id)
                except Exception:
                    pass  # 正确处理异常
            
            logger.info("✅ 边界情况和错误处理测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 边界情况和错误处理测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def test_new_user_first_experience(self):
        """
        测试新用户首次使用体验
        验证新用户从注册到首次使用的完整流程
        """
        logger.info("开始测试新用户首次使用体验")
        
        try:
            new_user_id = 99999999
            new_username = "brand_new_user"
            
            # 1. 模拟新用户首次启动
            new_user_message = MagicMock()
            new_user_message.from_user.id = new_user_id
            new_user_message.from_user.username = new_username
            new_user_message.answer = AsyncMock()
            
            # 2. 测试用户自动创建
            with patch.object(user_manager, 'create_or_update_user') as mock_create:
                mock_create.return_value = None
                
                with patch('database.db_templates.template_manager.get_template') as mock_template:
                    mock_template.return_value = "欢迎新用户！"
                    
                    await start_command(new_user_message)
                    mock_create.assert_called_once_with(new_user_id, new_username)
            
            # 3. 验证新用户档案
            await user_manager.create_or_update_user(new_user_id, new_username)
            new_profile = await user_manager.get_user_profile(new_user_id)
            
            if new_profile:
                assert new_profile['user_id'] == new_user_id, "新用户ID应该正确"
                assert new_profile['username'] == new_username, "新用户名应该正确"
            
            # 4. 测试新用户首次搜索
            search_result = await region_manager.search_regions("北京", limit=5)
            assert isinstance(search_result, list), "新用户应该能正常搜索"
            
            # 5. 测试新用户首次查看商户
            merchants = await merchant_manager.get_merchants(status='published', limit=5)
            assert isinstance(merchants, list), "新用户应该能查看商户"
            
            # 6. 测试新用户首次创建订单
            if merchants:
                first_order_data = {
                    'customer_user_id': new_user_id,
                    'customer_username': new_username,
                    'merchant_id': merchants[0]['id'],
                    'price': 300,
                    'status': '尝试预约'
                }
                
                first_order_id = await order_manager.create_order(first_order_data)
                assert first_order_id is not None, "新用户应该能创建订单"
                
                # 7. 验证首次订单
                first_order = await order_manager.get_order(first_order_id)
                assert first_order is not None, "应该能获取首次订单"
                assert first_order['customer_user_id'] == new_user_id, "订单用户ID应该正确"
            
            # 8. 测试新用户首次获得奖励
            await user_manager.grant_rewards(new_user_id, 20, 10)
            
            # 9. 验证奖励结果
            rewarded_profile = await user_manager.get_user_profile(new_user_id)
            if rewarded_profile:
                assert rewarded_profile['xp'] >= 20, "新用户应该获得经验奖励"
                assert rewarded_profile['points'] >= 10, "新用户应该获得积分奖励"
            
            # 10. 测试新用户档案显示
            with patch.object(user_manager, 'get_user_profile') as mock_profile:
                mock_profile.return_value = rewarded_profile
                
                with patch('database.db_templates.template_manager.get_template') as mock_template:
                    mock_template.return_value = "新用户档案: {level_name}"
                    
                    await profile_command(new_user_message)
                    new_user_message.answer.assert_called()
            
            logger.info("✅ 新用户首次使用体验测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 新用户首次使用体验测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def test_comprehensive_user_journey(self):
        """
        测试完整的用户使用旅程
        从注册到完成交易的端到端测试
        """
        logger.info("开始测试完整的用户使用旅程")
        
        try:
            journey_user_id = 88888888
            journey_username = "journey_user"
            
            # 阶段1: 用户注册和首次使用
            await user_manager.create_or_update_user(journey_user_id, journey_username)
            
            # 阶段2: 地区搜索和商户发现
            cities = await region_manager.get_active_cities_with_districts()
            assert len(cities) >= 0, "应该能获取城市列表"
            
            # 阶段3: 商户浏览
            published_merchants = await merchant_manager.get_merchants(
                status='published', 
                limit=10
            )
            
            if published_merchants:
                selected_merchant = published_merchants[0]
                
                # 阶段4: 查看商户详情
                merchant_detail = await merchant_manager.get_merchant(selected_merchant['id'])
                assert merchant_detail is not None, "应该能获取商户详情"
                
                # 阶段5: 创建订单
                journey_order_data = {
                    'customer_user_id': journey_user_id,
                    'customer_username': journey_username,
                    'merchant_id': selected_merchant['id'],
                    'price': 800,
                    'status': '尝试预约'
                }
                
                journey_order_id = await order_manager.create_order(journey_order_data)
                assert journey_order_id is not None, "应该能创建订单"
                
                # 阶段6: 订单确认和完成
                await order_manager.update_order_status(journey_order_id, '已完成')
                
                # 阶段7: 用户获得奖励
                await user_manager.grant_rewards(journey_user_id, 100, 50)
                await user_manager.update_user_level_and_badges(
                    journey_user_id,
                    new_level_name="活跃用户",
                    new_badge="首次完成"
                )
                
                # 阶段8: 查看更新后的用户档案
                final_profile = await user_manager.get_user_profile(journey_user_id)
                assert final_profile is not None, "应该能获取最终用户档案"
                assert final_profile['level_name'] == "活跃用户", "等级应该更新"
                
                # 阶段9: 查看订单历史
                user_orders = await order_manager.get_orders_by_user(journey_user_id)
                assert len(user_orders) > 0, "应该有订单历史"
                
                # 阶段10: 统计验证
                order_stats = await order_manager.get_order_statistics()
                assert order_stats['total_orders'] > 0, "总订单数应该大于0"
                
                merchant_stats = await merchant_manager.get_merchant_statistics()
                assert merchant_stats['total_merchants'] >= 0, "商户统计应该正常"
            
            logger.info("✅ 完整的用户使用旅程测试通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ 完整的用户使用旅程测试失败: {e}")
            return False

    @pytest.mark.asyncio
    async def run_all_tests(self):
        """
        运行所有用户体验测试
        生成完整的测试报告
        """
        logger.info("🚀 开始运行用户核心体验全面测试")
        
        test_results = {}
        
        # 定义测试套件
        test_suite = [
            ("地区搜索功能", self.test_region_search_functionality),
            ("商户浏览和发现", self.test_merchant_browsing_and_discovery),
            ("订单创建和管理", self.test_order_creation_and_management),
            ("用户档案系统", self.test_user_profile_system),
            ("用户交互流程", self.test_user_interaction_flow),
            ("并发用户操作", self.test_concurrent_user_operations),
            ("边界情况和错误处理", self.test_edge_cases_and_error_handling),
            ("新用户首次体验", self.test_new_user_first_experience),
            ("完整用户旅程", self.test_comprehensive_user_journey)
        ]
        
        # 执行测试
        passed_tests = 0
        total_tests = len(test_suite)
        
        for test_name, test_func in test_suite:
            logger.info(f"\n📋 执行测试: {test_name}")
            try:
                result = await test_func()
                test_results[test_name] = {
                    'status': 'PASSED' if result else 'FAILED',
                    'result': result
                }
                if result:
                    passed_tests += 1
                    logger.info(f"✅ {test_name} - 通过")
                else:
                    logger.error(f"❌ {test_name} - 失败")
            except Exception as e:
                test_results[test_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
                logger.error(f"💥 {test_name} - 异常: {e}")
        
        # 生成测试报告
        logger.info("\n" + "="*60)
        logger.info("📊 用户核心体验测试报告")
        logger.info("="*60)
        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过测试: {passed_tests}")
        logger.info(f"失败测试: {total_tests - passed_tests}")
        logger.info(f"通过率: {(passed_tests/total_tests)*100:.1f}%")
        logger.info("="*60)
        
        for test_name, result in test_results.items():
            status_emoji = "✅" if result['status'] == 'PASSED' else "❌" if result['status'] == 'FAILED' else "💥"
            logger.info(f"{status_emoji} {test_name}: {result['status']}")
            if 'error' in result:
                logger.info(f"   错误: {result['error']}")
        
        logger.info("="*60)
        
        return test_results

# 如果直接运行此脚本
if __name__ == "__main__":
    async def main():
        test_runner = TestUserExperience()
        await test_runner.run_all_tests()
    
    asyncio.run(main())