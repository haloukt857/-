"""
用户流程集成测试
端到端测试用户、商家和管理员的完整工作流程
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import User, Chat, Message, CallbackQuery, InlineKeyboardMarkup

from database.db_merchants import MerchantManager as MerchantsDatabase
from database.db_orders import OrderManager as OrderManagerV2
from database.db_binding_codes import BindingCodesManager as BindingsDatabase
from database.db_logs import ActivityLogsDatabase
from states.user_states import UserStates
from states.merchant_states import MerchantStates
from states.admin_states import AdminStates


class TestUserJourney:
    """用户完整流程测试"""
    
    @pytest.fixture
    async def setup_test_data(self, db_manager):
        """设置测试数据"""
        # 创建测试商家
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": 111222333,
            "name": "测试教育机构",
            "region": "北京",
            "category": "教育培训",
            "contact_info": "微信：edu123",
            "profile_data": {
                "description": "专业英语培训",
                "services": ["雅思", "托福", "商务英语"],
                "price_range": "200-500元/小时"
            }
        }
        merchant_id = await merchants_db.create_merchant(merchant_data)
        return {"merchant_id": merchant_id, "merchant_data": merchant_data}
    
    @pytest.fixture
    def storage(self):
        """创建FSM存储"""
        return MemoryStorage()
    
    @pytest.fixture
    async def fsm_context(self, storage, mock_user, mock_chat):
        """创建FSM上下文"""
        context = FSMContext(
            storage=storage,
            key=storage.get_key(
                bot_id=12345,
                chat_id=mock_chat.id,
                user_id=mock_user.id
            )
        )
        return context
    
    @pytest.mark.asyncio
    async def test_complete_user_appointment_flow(self, setup_test_data, mock_bot, mock_user, mock_chat, fsm_context):
        """测试用户完整预约流程"""
        merchant_id = setup_test_data["merchant_id"]
        
        # 1. 用户发送 /start 命令
        from handlers.user import cmd_start
        
        start_message = AsyncMock(spec=Message)
        start_message.from_user = mock_user
        start_message.chat = mock_chat
        start_message.text = "/start"
        
        # 初始化用户处理器
        from handlers.user import init_user_handler
        init_user_handler(mock_bot)
        
        with patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            mock_db_instance = AsyncMock()
            mock_merchants_db.return_value = mock_db_instance
            mock_db_instance.get_all_merchants.return_value = [setup_test_data["merchant_data"]]
            
            await cmd_start(start_message, fsm_context)
            
            # 验证发送了商家列表
            start_message.answer.assert_called_once()
            
            # 验证FSM状态
            state = await fsm_context.get_state()
            assert state == UserStates.waiting_for_merchant_selection
    
        # 2. 用户选择商家
        from handlers.user import handle_merchant_selection
        
        merchant_callback = AsyncMock(spec=CallbackQuery)
        merchant_callback.from_user = mock_user
        merchant_callback.data = f"merchant_{merchant_id}"
        merchant_callback.message = AsyncMock()
        
        with patch('handlers.user.MerchantsDatabase') as mock_merchants_db, \
             patch('handlers.user.ActivityLogsDatabase') as mock_logs_db:
            
            mock_merchants_instance = AsyncMock()
            mock_merchants_db.return_value = mock_merchants_instance
            mock_merchants_instance.get_merchant.return_value = setup_test_data["merchant_data"]
            
            mock_logs_instance = AsyncMock()
            mock_logs_db.return_value = mock_logs_instance
            
            await handle_merchant_selection(merchant_callback, fsm_context)
            
            # 验证日志记录
            mock_logs_instance.log_button_click.assert_called_once()
            
            # 验证商家信息显示
            merchant_callback.message.edit_text.assert_called_once()
            
            # 验证FSM状态
            state = await fsm_context.get_state()
            assert state == UserStates.selecting_service
            
            # 验证FSM数据
            data = await fsm_context.get_data()
            assert data["current_merchant_id"] == merchant_id
    
        # 3. 用户选择预约服务
        from handlers.user import handle_service_selection
        
        service_callback = AsyncMock(spec=CallbackQuery)
        service_callback.from_user = mock_user
        service_callback.data = f"service_appointment_{merchant_id}"
        service_callback.message = AsyncMock()
        
        with patch('handlers.user.OrderManagerV2') as mock_order_manager_v2, \
             patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            
            mock_orders_instance = AsyncMock()
            mock_order_manager_v2.return_value = mock_orders_instance
            mock_orders_instance.create_order.return_value = 1
            
            mock_merchants_instance = AsyncMock()
            mock_merchants_db.return_value = mock_merchants_instance
            mock_merchants_instance.get_merchant.return_value = setup_test_data["merchant_data"]
            
            await handle_service_selection(service_callback, fsm_context)
            
            # 验证创建订单
            mock_orders_instance.create_order.assert_called_once()
            order_data = mock_orders_instance.create_order.call_args[0][0]
            assert order_data["user_id"] == mock_user.id
            assert order_data["merchant_id"] == merchant_id
            assert order_data["order_type"] == "appointment"
            
            # 验证用户收到确认信息
            service_callback.message.edit_text.assert_called_once()
            
            # 验证通知商家
            mock_bot.send_message.assert_called_once()
            
            # 验证FSM状态清除
            state = await fsm_context.get_state()
            assert state is None
    
    @pytest.mark.asyncio
    async def test_user_follow_merchant_flow(self, setup_test_data, mock_bot, mock_user, fsm_context):
        """测试用户关注商家流程"""
        merchant_id = setup_test_data["merchant_id"]
        
        # 设置用户已选择商家的状态
        await fsm_context.set_state(UserStates.selecting_service)
        await fsm_context.update_data(current_merchant_id=merchant_id)
        
        # 用户选择关注服务
        from handlers.user import handle_service_selection
        
        follow_callback = AsyncMock(spec=CallbackQuery)
        follow_callback.from_user = mock_user
        follow_callback.data = f"service_follow_{merchant_id}"
        follow_callback.message = AsyncMock()
        
        with patch('handlers.user.OrderManagerV2') as mock_order_manager_v2, \
             patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            
            mock_orders_instance = AsyncMock()
            mock_order_manager_v2.return_value = mock_orders_instance
            mock_orders_instance.create_order.return_value = 2
            
            mock_merchants_instance = AsyncMock()
            mock_merchants_db.return_value = mock_merchants_instance
            mock_merchants_instance.get_merchant.return_value = setup_test_data["merchant_data"]
            
            await handle_service_selection(follow_callback, fsm_context)
            
            # 验证创建关注订单
            mock_orders_instance.create_order.assert_called_once()
            order_data = mock_orders_instance.create_order.call_args[0][0]
            assert order_data["order_type"] == "follow"
    
    @pytest.mark.asyncio
    async def test_user_return_to_merchant_list_flow(self, setup_test_data, mock_user, fsm_context):
        """测试用户返回商家列表流程"""
        merchant_id = setup_test_data["merchant_id"]
        
        # 设置用户已选择商家的状态
        await fsm_context.set_state(UserStates.selecting_service)
        await fsm_context.update_data(current_merchant_id=merchant_id)
        
        # 用户选择返回列表
        from handlers.user import handle_service_selection
        
        return_callback = AsyncMock(spec=CallbackQuery)
        return_callback.from_user = mock_user
        return_callback.data = "back_to_list"
        return_callback.message = AsyncMock()
        
        with patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            mock_merchants_instance = AsyncMock()
            mock_merchants_db.return_value = mock_merchants_instance
            mock_merchants_instance.get_all_merchants.return_value = [setup_test_data["merchant_data"]]
            
            await handle_service_selection(return_callback, fsm_context)
            
            # 验证返回到商家列表状态
            state = await fsm_context.get_state()
            assert state == UserStates.waiting_for_merchant_selection
    
    @pytest.mark.asyncio
    async def test_user_error_handling(self, mock_bot, mock_user, mock_chat, fsm_context):
        """测试用户流程中的错误处理"""
        from handlers.user import handle_merchant_selection
        
        # 用户选择不存在的商家
        invalid_callback = AsyncMock(spec=CallbackQuery)
        invalid_callback.from_user = mock_user
        invalid_callback.data = "merchant_99999"  # 不存在的商家ID
        invalid_callback.message = AsyncMock()
        
        with patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            mock_merchants_instance = AsyncMock()
            mock_merchants_db.return_value = mock_merchants_instance
            mock_merchants_instance.get_merchant.return_value = None  # 商家不存在
            
            await handle_merchant_selection(invalid_callback, fsm_context)
            
            # 验证错误提示
            invalid_callback.answer.assert_called_once()
            error_msg = invalid_callback.answer.call_args[0][0]
            assert "不存在" in error_msg or "无效" in error_msg


class TestMerchantRegistrationFlow:
    """商家注册流程测试"""
    
    @pytest.fixture
    def storage(self):
        """创建FSM存储"""
        return MemoryStorage()
    
    @pytest.fixture
    async def fsm_context(self, storage, mock_user, mock_chat):
        """创建FSM上下文"""
        context = FSMContext(
            storage=storage,
            key=storage.get_key(
                bot_id=12345,
                chat_id=mock_chat.id,
                user_id=mock_user.id
            )
        )
        return context
    
    @pytest.mark.asyncio
    async def test_complete_merchant_registration_flow(self, mock_bot, mock_user, mock_chat, fsm_context, db_manager):
        """测试商家完整注册流程"""
        
        # 1. 商家发送"上榜流程"
        from handlers.merchant import handle_binding_request
        
        binding_request_msg = AsyncMock(spec=Message)
        binding_request_msg.from_user = mock_user
        binding_request_msg.chat = mock_chat
        binding_request_msg.text = "上榜流程"
        
        await handle_binding_request(binding_request_msg, fsm_context)
        
        # 验证引导信息
        binding_request_msg.answer.assert_called_once()
        
        # 验证FSM状态
        state = await fsm_context.get_state()
        assert state == MerchantStates.entering_binding_code
        
        # 2. 商家输入绑定码
        from handlers.merchant import handle_binding_code_entry
        
        # 先生成有效的绑定码
        bindings_db = BindingsDatabase()
        valid_code = await bindings_db.generate_binding_code()
        
        code_entry_msg = AsyncMock(spec=Message)
        code_entry_msg.from_user = mock_user
        code_entry_msg.chat = mock_chat
        code_entry_msg.text = valid_code
        
        await handle_binding_code_entry(code_entry_msg, fsm_context)
        
        # 验证成功提示
        code_entry_msg.answer.assert_called()
        
        # 验证FSM状态转换
        state = await fsm_context.get_state()
        assert state == MerchantStates.selecting_region
        
        # 3. 选择地区
        from dialogs.binding_flow import handle_region_selection
        
        region_callback = AsyncMock(spec=CallbackQuery)
        region_callback.from_user = mock_user
        region_callback.data = "region_beijing"
        region_callback.message = AsyncMock()
        
        await handle_region_selection(region_callback, fsm_context)
        
        # 验证数据更新
        data = await fsm_context.get_data()
        assert "region" in data
        
        # 验证状态转换
        state = await fsm_context.get_state()
        assert state == MerchantStates.selecting_category
        
        # 4. 选择类别
        from dialogs.binding_flow import handle_category_selection
        
        category_callback = AsyncMock(spec=CallbackQuery)
        category_callback.from_user = mock_user
        category_callback.data = "category_education"
        category_callback.message = AsyncMock()
        
        await handle_category_selection(category_callback, fsm_context)
        
        # 验证状态转换
        state = await fsm_context.get_state()
        assert state == MerchantStates.confirming_profile
        
        # 5. 确认档案
        from dialogs.binding_flow import handle_profile_confirmation
        
        confirm_callback = AsyncMock(spec=CallbackQuery)
        confirm_callback.from_user = mock_user
        confirm_callback.data = "confirm_profile"
        confirm_callback.message = AsyncMock()
        
        await handle_profile_confirmation(confirm_callback, fsm_context)
        
        # 验证商家创建
        merchants_db = MerchantsDatabase()
        merchant = await merchants_db.get_merchant_by_chat_id(mock_user.id)
        assert merchant is not None
        assert merchant["status"] == "active"
        
        # 验证绑定码已使用
        is_valid = await bindings_db.validate_binding_code(valid_code)
        assert not is_valid
        
        # 验证FSM状态清除
        state = await fsm_context.get_state()
        assert state is None
    
    @pytest.mark.asyncio
    async def test_merchant_registration_with_back_navigation(self, mock_user, fsm_context, db_manager):
        """测试商家注册中的返回导航"""
        
        # 设置用户在类别选择状态
        await fsm_context.set_state(MerchantStates.selecting_category)
        await fsm_context.update_data({
            "binding_code": "TEST123",
            "region": "北京",
            "category": "教育培训"
        })
        
        # 用户点击返回按钮
        from dialogs.binding_flow import handle_back_navigation
        
        back_callback = AsyncMock(spec=CallbackQuery)
        back_callback.from_user = mock_user
        back_callback.data = "back_to_region"
        back_callback.message = AsyncMock()
        
        await handle_back_navigation(back_callback, fsm_context)
        
        # 验证状态回退
        state = await fsm_context.get_state()
        assert state == MerchantStates.selecting_region
        
        # 验证数据回退（category应该被移除）
        data = await fsm_context.get_data()
        assert "region" in data
        assert "category" not in data
    
    @pytest.mark.asyncio
    async def test_invalid_binding_code_handling(self, mock_user, fsm_context):
        """测试无效绑定码处理"""
        
        # 设置用户在输入绑定码状态
        await fsm_context.set_state(MerchantStates.entering_binding_code)
        
        from handlers.merchant import handle_binding_code_entry
        
        invalid_code_msg = AsyncMock(spec=Message)
        invalid_code_msg.from_user = mock_user
        invalid_code_msg.text = "INVALID_CODE"
        
        await handle_binding_code_entry(invalid_code_msg, fsm_context)
        
        # 验证错误信息
        invalid_code_msg.answer.assert_called_once()
        error_msg = invalid_code_msg.answer.call_args[0][0]
        assert "无效" in error_msg or "错误" in error_msg
        
        # 验证状态保持不变
        state = await fsm_context.get_state()
        assert state == MerchantStates.entering_binding_code


class TestAdminManagementFlow:
    """管理员管理流程测试"""
    
    @pytest.fixture
    def storage(self):
        """创建FSM存储"""
        return MemoryStorage()
    
    @pytest.fixture
    async def fsm_context(self, storage, mock_admin_user, mock_chat):
        """创建管理员FSM上下文"""
        context = FSMContext(
            storage=storage,
            key=storage.get_key(
                bot_id=12345,
                chat_id=mock_chat.id,
                user_id=mock_admin_user.id
            )
        )
        return context
    
    @pytest.mark.asyncio
    async def test_admin_button_configuration_flow(self, mock_admin_user, mock_chat, fsm_context, config_override):
        """测试管理员按钮配置流程"""
        
        # 1. 管理员发送 /set_button 命令
        from handlers.admin import cmd_set_button
        
        set_button_msg = AsyncMock(spec=Message)
        set_button_msg.from_user = mock_admin_user
        set_button_msg.chat = mock_chat
        set_button_msg.text = "/set_button"
        
        await cmd_set_button(set_button_msg, fsm_context)
        
        # 验证引导信息
        set_button_msg.answer.assert_called_once()
        
        # 验证FSM状态
        state = await fsm_context.get_state()
        assert state == AdminStates.setting_message
        
        # 2. 管理员输入消息内容
        from handlers.admin import handle_message_input
        
        message_input = AsyncMock(spec=Message)
        message_input.from_user = mock_admin_user
        message_input.text = "欢迎使用商家服务平台"
        
        await handle_message_input(message_input, fsm_context)
        
        # 验证状态转换
        state = await fsm_context.get_state()
        assert state == AdminStates.configuring_buttons
        
        # 3. 管理员配置按钮
        from handlers.admin import handle_button_configuration
        
        button_callback = AsyncMock(spec=CallbackQuery)
        button_callback.from_user = mock_admin_user
        button_callback.data = "add_button"
        button_callback.message = AsyncMock()
        
        await handle_button_configuration(button_callback, fsm_context)
        
        # 验证进入添加按钮状态
        state = await fsm_context.get_state()
        assert state == AdminStates.adding_button
    
    @pytest.mark.asyncio
    async def test_admin_generate_binding_code_flow(self, mock_admin_user, fsm_context, config_override, db_manager):
        """测试管理员生成绑定码流程"""
        
        from handlers.admin import cmd_generate_code
        
        generate_msg = AsyncMock(spec=Message)
        generate_msg.from_user = mock_admin_user
        generate_msg.text = "/generate_code"
        
        await cmd_generate_code(generate_msg, fsm_context)
        
        # 验证生成绑定码
        generate_msg.answer.assert_called_once()
        response_text = generate_msg.answer.call_args[0][0]
        
        # 验证响应中包含绑定码
        assert len([word for word in response_text.split() if word.isalnum() and len(word) >= 6]) > 0
    
    @pytest.mark.asyncio
    async def test_admin_view_statistics_flow(self, mock_admin_user, fsm_context, config_override, db_manager):
        """测试管理员查看统计流程"""
        
        # 先添加一些测试日志数据
        logs_db = ActivityLogsDatabase()
        await logs_db.log_button_click(123456, "test_button")
        await logs_db.log_user_interaction(123456, "merchant_contact", {"merchant_id": 1})
        
        from handlers.admin import cmd_view_stats
        
        stats_msg = AsyncMock(spec=Message)
        stats_msg.from_user = mock_admin_user
        stats_msg.text = "/view_stats"
        
        await cmd_view_stats(stats_msg, fsm_context)
        
        # 验证统计信息
        stats_msg.answer.assert_called_once()
        response_text = stats_msg.answer.call_args[0][0]
        
        # 验证响应包含统计数据
        assert "点击" in response_text or "统计" in response_text


class TestConcurrentUserFlow:
    """并发用户流程测试"""
    
    @pytest.mark.asyncio
    async def test_multiple_users_simultaneous_access(self, db_manager, mock_bot):
        """测试多用户同时访问"""
        
        # 创建测试商家
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": 111222333,
            "name": "并发测试商家",
            "region": "上海",
            "category": "教育培训",
            "contact_info": "微信：concurrent123"
        }
        merchant_id = await merchants_db.create_merchant(merchant_data)
        
        # 模拟多个用户同时操作的任务
        async def user_appointment_task(user_id):
            order_manager_v2 = OrderManagerV2()
            order_data = {
                "user_id": user_id,
                "username": f"@user{user_id}",
                "merchant_id": merchant_id,
                "order_type": "appointment",
                "price": 200.00
            }
            return await order_manager_v2.create_order(order_data)
        
        # 创建10个并发用户任务
        tasks = []
        user_ids = range(1000000, 1000010)
        
        for user_id in user_ids:
            task = user_appointment_task(user_id)
            tasks.append(task)
        
        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证所有任务都成功完成
        successful_orders = [r for r in results if isinstance(r, int)]
        assert len(successful_orders) == 10
        
        # 验证数据库中确实有10个订单
        all_orders = await OrderManagerV2().get_orders_by_merchant(merchant_id)
        assert len(all_orders) >= 10
    
    @pytest.mark.asyncio
    async def test_concurrent_merchant_registration(self, db_manager):
        """测试并发商家注册"""
        
        # 生成多个绑定码
        bindings_db = BindingsDatabase()
        codes = []
        for i in range(5):
            code = await bindings_db.generate_binding_code()
            codes.append(code)
        
        # 模拟并发商家注册任务
        async def merchant_registration_task(chat_id, code, name):
            merchants_db = MerchantsDatabase()
            merchant_data = {
                "chat_id": chat_id,
                "name": name,
                "region": "测试地区",
                "category": "测试类别",
                "contact_info": f"微信：test{chat_id}"
            }
            
            merchant_id = await merchants_db.create_merchant(merchant_data)
            await bindings_db.use_binding_code(code, merchant_id)
            return merchant_id
        
        # 创建并发任务
        tasks = []
        for i, code in enumerate(codes):
            chat_id = 2000000 + i
            name = f"并发商家{i}"
            task = merchant_registration_task(chat_id, code, name)
            tasks.append(task)
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证所有注册都成功
        successful_registrations = [r for r in results if isinstance(r, int)]
        assert len(successful_registrations) == 5
        
        # 验证所有绑定码都被使用
        for code in codes:
            is_valid = await bindings_db.validate_binding_code(code)
            assert not is_valid  # 已被使用，不再有效


class TestErrorRecoveryIntegration:
    """错误恢复集成测试"""
    
    @pytest.mark.asyncio
    async def test_database_failure_recovery(self, mock_bot, mock_user, mock_chat):
        """测试数据库故障恢复"""
        from handlers.user import cmd_start
        from utils.error_recovery import ErrorRecoveryService
        
        # 创建错误恢复服务
        error_service = ErrorRecoveryService(mock_bot)
        
        # 模拟数据库连接失败
        with patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            mock_db_instance = AsyncMock()
            mock_merchants_db.return_value = mock_db_instance
            mock_db_instance.get_all_merchants.side_effect = Exception("Database connection failed")
            
            start_message = AsyncMock(spec=Message)
            start_message.from_user = mock_user
            start_message.chat = mock_chat
            start_message.text = "/start"
            
            # 使用错误恢复服务处理
            try:
                await cmd_start(start_message, AsyncMock())
            except Exception as e:
                await error_service.handle_error(e, {"operation": "user_start"})
            
            # 验证发送了错误消息而不是崩溃
            start_message.answer.assert_called()
    
    @pytest.mark.asyncio
    async def test_api_rate_limit_handling(self, mock_bot, mock_user):
        """测试API限流处理"""
        from middleware.throttling import ThrottlingMiddleware
        
        # 创建限流中间件
        throttling = ThrottlingMiddleware(
            default_rate=1,  # 很低的限制用于测试
            default_burst=1,
            admin_rate=10
        )
        
        # 模拟处理器
        async def mock_handler(event, data):
            return "processed"
        
        # 模拟事件
        mock_event = MagicMock()
        mock_event.from_user.id = mock_user.id
        
        # 第一次请求应该通过
        result = await throttling(mock_handler, mock_event, {})
        assert result == "processed"
        
        # 立即的第二次请求应该被限制
        with pytest.raises(Exception):  # 应该抛出限流异常
            await throttling(mock_handler, mock_event, {})
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, mock_bot):
        """测试优雅降级"""
        from utils.fallback_manager import FallbackManager
        
        fallback_manager = FallbackManager(mock_bot)
        fallback_manager.enable_fallback_mode(simplified=True)
        
        # 模拟正常功能不可用时的故障转移
        mock_message = AsyncMock()
        mock_message.from_user.id = 123456
        
        result = await fallback_manager.handle_fallback_request(
            "start",
            mock_message,
            {}
        )
        
        # 验证故障转移成功
        assert result is True
        mock_message.answer.assert_called_once()
        
        # 验证消息内容表明是简化模式
        call_args = mock_message.answer.call_args[0][0]
        assert "维护" in call_args or "功能有限" in call_args