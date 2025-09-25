"""
处理器单元测试
测试管理员、用户和商家处理器的功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from handlers.admin import admin_router
from handlers.user import router as user_router
from handlers.merchant import merchant_router
from dialogs.states import UserStates, MerchantStates, AdminStates


class TestAdminHandlers:
    """管理员处理器测试"""
    
    @pytest.fixture
    def mock_fsm_context(self):
        """模拟FSM上下文"""
        context = AsyncMock(spec=FSMContext)
        context.get_data.return_value = {}
        context.update_data = AsyncMock()
        context.set_state = AsyncMock()
        context.clear = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_set_button_command(self, mock_message, mock_admin_user, mock_fsm_context, config_override):
        """测试 /set_button 命令"""
        from handlers.admin import cmd_set_button
        
        mock_message.from_user = mock_admin_user
        mock_message.text = "/set_button"
        
        await cmd_set_button(mock_message, mock_fsm_context)
        
        # 验证回复消息
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "设置消息内容" in call_args
        
        # 验证状态设置
        mock_fsm_context.set_state.assert_called_once_with(AdminStates.setting_message)
    
    @pytest.mark.asyncio
    async def test_generate_code_command(self, mock_message, mock_admin_user, mock_fsm_context, config_override):
        """测试 /generate_code 命令"""
        from handlers.admin import cmd_generate_code
        
        mock_message.from_user = mock_admin_user
        mock_message.text = "/generate_code"
        
        with patch('handlers.admin.BindingsDatabase') as mock_bindings_db:
            mock_db_instance = AsyncMock()
            mock_bindings_db.return_value = mock_db_instance
            mock_db_instance.generate_binding_code.return_value = "ABC12345"
            
            await cmd_generate_code(mock_message, mock_fsm_context)
            
            # 验证生成绑定码
            mock_db_instance.generate_binding_code.assert_called_once()
            
            # 验证回复消息包含生成的码
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "ABC12345" in call_args
    
    @pytest.mark.asyncio
    async def test_view_stats_command(self, mock_message, mock_admin_user, mock_fsm_context, config_override):
        """测试 /view_stats 命令"""
        from handlers.admin import cmd_view_stats
        
        mock_message.from_user = mock_admin_user
        mock_message.text = "/view_stats"
        
        with patch('handlers.admin.ActivityLogsDatabase') as mock_logs_db:
            mock_db_instance = AsyncMock()
            mock_logs_db.return_value = mock_db_instance
            mock_db_instance.get_statistics.return_value = {
                "total_clicks": 100,
                "unique_users": 50,
                "button_clicks": {"test_button": 25}
            }
            
            await cmd_view_stats(mock_message, mock_fsm_context)
            
            # 验证获取统计数据
            mock_db_instance.get_statistics.assert_called_once()
            
            # 验证回复消息包含统计信息
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "100" in call_args  # 总点击数
            assert "50" in call_args   # 独立用户数
    
    @pytest.mark.asyncio
    async def test_non_admin_access_denied(self, mock_message, mock_user, mock_fsm_context, config_override):
        """测试非管理员用户访问被拒绝"""
        from handlers.admin import cmd_set_button
        
        mock_message.from_user = mock_user  # 非管理员用户
        mock_message.text = "/set_button"
        
        await cmd_set_button(mock_message, mock_fsm_context)
        
        # 验证拒绝访问的回复
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "权限不足" in call_args or "无权限" in call_args


class TestUserHandlers:
    """用户处理器测试"""
    
    @pytest.fixture
    def mock_fsm_context(self):
        """模拟FSM上下文"""
        context = AsyncMock(spec=FSMContext)
        context.get_data.return_value = {}
        context.update_data = AsyncMock()
        context.set_state = AsyncMock()
        context.clear = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_start_command(self, mock_message, mock_user, mock_fsm_context, mock_bot):
        """测试 /start 命令"""
        from handlers.user import cmd_start
        
        mock_message.from_user = mock_user
        mock_message.text = "/start"
        
        with patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            mock_db_instance = AsyncMock()
            mock_merchants_db.return_value = mock_db_instance
            mock_db_instance.get_all_merchants.return_value = [
                {"id": 1, "name": "测试商家1", "region": "北京"},
                {"id": 2, "name": "测试商家2", "region": "上海"}
            ]
            
            await cmd_start(mock_message, mock_fsm_context)
            
            # 验证回复消息
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args
            
            # 检查是否有消息文本和键盘
            assert len(call_args) > 0
            if len(call_args) > 1 and 'reply_markup' in call_args[1]:
                reply_markup = call_args[1]['reply_markup']
                assert isinstance(reply_markup, InlineKeyboardMarkup)
    
    @pytest.mark.asyncio
    async def test_merchant_callback(self, mock_callback_query, mock_user, mock_fsm_context, mock_bot):
        """测试商家选择回调"""
        from handlers.user import handle_merchant_selection
        
        mock_callback_query.from_user = mock_user
        mock_callback_query.data = "merchant_1"
        
        with patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            mock_db_instance = AsyncMock()
            mock_merchants_db.return_value = mock_db_instance
            mock_db_instance.get_merchant.return_value = {
                "id": 1,
                "name": "测试商家",
                "region": "北京",
                "category": "教育培训",
                "contact_info": "微信：test123"
            }
            
            with patch('handlers.user.ActivityLogsDatabase') as mock_logs_db:
                mock_logs_instance = AsyncMock()
                mock_logs_db.return_value = mock_logs_instance
                
                await handle_merchant_selection(mock_callback_query, mock_fsm_context)
                
                # 验证日志记录
                mock_logs_instance.log_button_click.assert_called_once()
                
                # 验证回调回复
                mock_callback_query.answer.assert_called_once()
                
                # 验证消息编辑
                mock_callback_query.message.edit_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_service_selection_callback(self, mock_callback_query, mock_user, mock_fsm_context, mock_bot):
        """测试服务选择回调"""
        from handlers.user import handle_service_selection
        
        mock_callback_query.from_user = mock_user
        mock_callback_query.data = "service_appointment_1"
        
        # 设置FSM数据
        mock_fsm_context.get_data.return_value = {"current_merchant_id": 1}
        
        with patch('handlers.user.OrderManager') as mock_order_manager, \
             patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            
            mock_orders_instance = AsyncMock()
            mock_order_manager.return_value = mock_orders_instance
            mock_orders_instance.create_order.return_value = 1
            
            mock_merchants_instance = AsyncMock()
            mock_merchants_db.return_value = mock_merchants_instance
            mock_merchants_instance.get_merchant.return_value = {
                "id": 1,
                "chat_id": 111222333,
                "name": "测试商家"
            }
            
            await handle_service_selection(mock_callback_query, mock_fsm_context)
            
            # 验证创建订单
            mock_orders_instance.create_order.assert_called_once()
            
            # 验证回调回复
            mock_callback_query.answer.assert_called_once()


class TestMerchantHandlers:
    """商家处理器测试"""
    
    @pytest.fixture
    def mock_fsm_context(self):
        """模拟FSM上下文"""
        context = AsyncMock(spec=FSMContext)
        context.get_data.return_value = {}
        context.update_data = AsyncMock()
        context.set_state = AsyncMock()
        context.clear = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_binding_process_trigger(self, mock_message, mock_user, mock_fsm_context):
        """测试上榜流程关键词触发"""
        from handlers.merchant import handle_binding_request
        
        mock_message.from_user = mock_user
        mock_message.text = "上榜流程"
        
        await handle_binding_request(mock_message, mock_fsm_context)
        
        # 验证回复消息包含联系管理员的信息
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "联系管理员" in call_args or "获取绑定码" in call_args
        
        # 验证设置状态
        mock_fsm_context.set_state.assert_called_once_with(MerchantStates.entering_binding_code)
    
    @pytest.mark.asyncio
    async def test_valid_binding_code_entry(self, mock_message, mock_user, mock_fsm_context):
        """测试输入有效绑定码"""
        from handlers.merchant import handle_binding_code_entry
        
        mock_message.from_user = mock_user
        mock_message.text = "ABC12345"
        
        with patch('handlers.merchant.BindingsDatabase') as mock_bindings_db:
            mock_db_instance = AsyncMock()
            mock_bindings_db.return_value = mock_db_instance
            mock_db_instance.validate_binding_code.return_value = True
            
            await handle_binding_code_entry(mock_message, mock_fsm_context)
            
            # 验证绑定码验证
            mock_db_instance.validate_binding_code.assert_called_once_with("ABC12345")
            
            # 验证成功消息
            mock_message.answer.assert_called()
            
            # 验证状态更新
            mock_fsm_context.update_data.assert_called()
            mock_fsm_context.set_state.assert_called()
    
    @pytest.mark.asyncio
    async def test_invalid_binding_code_entry(self, mock_message, mock_user, mock_fsm_context):
        """测试输入无效绑定码"""
        from handlers.merchant import handle_binding_code_entry
        
        mock_message.from_user = mock_user
        mock_message.text = "INVALID123"
        
        with patch('handlers.merchant.BindingsDatabase') as mock_bindings_db:
            mock_db_instance = AsyncMock()
            mock_bindings_db.return_value = mock_db_instance
            mock_db_instance.validate_binding_code.return_value = False
            
            await handle_binding_code_entry(mock_message, mock_fsm_context)
            
            # 验证绑定码验证
            mock_db_instance.validate_binding_code.assert_called_once_with("INVALID123")
            
            # 验证错误消息
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "无效" in call_args or "错误" in call_args


class TestBindingFlow:
    """绑定流程测试"""
    
    @pytest.fixture
    def mock_fsm_context(self):
        """模拟FSM上下文"""
        context = AsyncMock(spec=FSMContext)
        context.get_data.return_value = {"binding_code": "ABC12345"}
        context.update_data = AsyncMock()
        context.set_state = AsyncMock()
        context.clear = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_region_selection(self, mock_callback_query, mock_user, mock_fsm_context):
        """测试地区选择"""
        from dialogs.binding_flow import handle_region_selection
        
        mock_callback_query.from_user = mock_user
        mock_callback_query.data = "region_beijing"
        
        await handle_region_selection(mock_callback_query, mock_fsm_context)
        
        # 验证数据更新
        mock_fsm_context.update_data.assert_called()
        update_call = mock_fsm_context.update_data.call_args[1]
        assert "region" in update_call
        
        # 验证状态转换
        mock_fsm_context.set_state.assert_called_once_with(MerchantStates.selecting_category)
        
        # 验证回调回复
        mock_callback_query.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_category_selection(self, mock_callback_query, mock_user, mock_fsm_context):
        """测试类别选择"""
        from dialogs.binding_flow import handle_category_selection
        
        mock_callback_query.from_user = mock_user
        mock_callback_query.data = "category_education"
        
        # 设置已有的FSM数据
        mock_fsm_context.get_data.return_value = {
            "binding_code": "ABC12345",
            "region": "北京"
        }
        
        await handle_category_selection(mock_callback_query, mock_fsm_context)
        
        # 验证数据更新
        mock_fsm_context.update_data.assert_called()
        
        # 验证状态转换
        mock_fsm_context.set_state.assert_called_once_with(MerchantStates.confirming_profile)
    
    @pytest.mark.asyncio
    async def test_profile_confirmation(self, mock_callback_query, mock_user, mock_fsm_context):
        """测试档案确认"""
        from dialogs.binding_flow import handle_profile_confirmation
        
        mock_callback_query.from_user = mock_user
        mock_callback_query.data = "confirm_profile"
        
        # 设置完整的FSM数据
        mock_fsm_context.get_data.return_value = {
            "binding_code": "ABC12345",
            "region": "北京",
            "category": "教育培训",
            "name": "测试商家"
        }
        
        with patch('dialogs.binding_flow.MerchantsDatabase') as mock_merchants_db, \
             patch('dialogs.binding_flow.BindingsDatabase') as mock_bindings_db:
            
            mock_merchants_instance = AsyncMock()
            mock_merchants_db.return_value = mock_merchants_instance
            mock_merchants_instance.create_merchant.return_value = 1
            
            mock_bindings_instance = AsyncMock()
            mock_bindings_db.return_value = mock_bindings_instance
            mock_bindings_instance.use_binding_code.return_value = True
            
            await handle_profile_confirmation(mock_callback_query, mock_fsm_context)
            
            # 验证创建商家
            mock_merchants_instance.create_merchant.assert_called_once()
            
            # 验证使用绑定码
            mock_bindings_instance.use_binding_code.assert_called_once()
            
            # 验证清除FSM状态
            mock_fsm_context.clear.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_back_navigation(self, mock_callback_query, mock_user, mock_fsm_context):
        """测试返回导航"""
        from dialogs.binding_flow import handle_back_navigation
        
        mock_callback_query.from_user = mock_user
        mock_callback_query.data = "back_to_region"
        
        # 设置当前在类别选择状态
        mock_fsm_context.get_data.return_value = {
            "binding_code": "ABC12345",
            "region": "北京",
            "category": "教育培训"
        }
        
        await handle_back_navigation(mock_callback_query, mock_fsm_context)
        
        # 验证状态返回到地区选择
        mock_fsm_context.set_state.assert_called_once_with(MerchantStates.selecting_region)
        
        # 验证数据清除（移除category）
        mock_fsm_context.update_data.assert_called()


class TestMiddleware:
    """中间件测试"""
    
    @pytest.mark.asyncio
    async def test_throttling_middleware(self):
        """测试限流中间件"""
        from middleware.throttling import ThrottlingMiddleware
        
        middleware = ThrottlingMiddleware(
            default_rate=5,
            default_burst=2,
            admin_rate=100,
            cleanup_interval=60
        )
        
        # 模拟用户请求
        mock_handler = AsyncMock()
        mock_event = MagicMock()
        mock_event.from_user.id = 123456789
        mock_data = {}
        
        # 第一次请求应该通过
        result = await middleware(mock_handler, mock_event, mock_data)
        mock_handler.assert_called_once()
        
        # 快速连续请求应该被限流
        mock_handler.reset_mock()
        for _ in range(3):  # 超过burst限制
            await middleware(mock_handler, mock_event, mock_data)
        
        # 验证后续请求被限制
        assert mock_handler.call_count < 3
    
    @pytest.mark.asyncio
    async def test_logging_middleware(self, db_manager):
        """测试日志中间件"""
        from middleware.logging import LoggingMiddleware
        from database.db_logs import ActivityLogsDatabase
        
        logs_db = ActivityLogsDatabase()
        middleware = LoggingMiddleware(logs_db)
        
        # 模拟处理器和事件
        mock_handler = AsyncMock()
        mock_event = MagicMock()
        mock_event.from_user.id = 123456789
        mock_event.from_user.username = "testuser"
        mock_data = {}
        
        await middleware(mock_handler, mock_event, mock_data)
        
        # 验证处理器被调用
        mock_handler.assert_called_once()


class TestErrorHandling:
    """错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_database_error_recovery(self, mock_message, mock_user):
        """测试数据库错误恢复"""
        from handlers.user import cmd_start
        
        mock_message.from_user = mock_user
        
        # 模拟数据库连接错误
        with patch('handlers.user.MerchantsDatabase') as mock_merchants_db:
            mock_db_instance = AsyncMock()
            mock_merchants_db.return_value = mock_db_instance
            mock_db_instance.get_all_merchants.side_effect = Exception("Database connection failed")
            
            # 应该优雅处理错误
            mock_fsm_context = AsyncMock()
            await cmd_start(mock_message, mock_fsm_context)
            
            # 验证发送了错误消息而不是崩溃
            mock_message.answer.assert_called()
    
    @pytest.mark.asyncio
    async def test_invalid_callback_data_handling(self, mock_callback_query, mock_user):
        """测试无效回调数据处理"""
        from handlers.user import handle_merchant_selection
        
        mock_callback_query.from_user = mock_user
        mock_callback_query.data = "invalid_merchant_data"
        
        mock_fsm_context = AsyncMock()
        
        # 应该优雅处理无效数据
        await handle_merchant_selection(mock_callback_query, mock_fsm_context)
        
        # 验证发送了错误提示
        mock_callback_query.answer.assert_called()


class TestUtilities:
    """工具函数测试"""
    
    @pytest.mark.asyncio
    async def test_dialog_manager_message_cleanup(self, mock_bot, mock_user):
        """测试对话管理器消息清理"""
        from dialogs.dialog_manager import DialogManager
        
        dialog_manager = DialogManager(mock_bot)
        
        # 模拟消息历史
        user_id = mock_user.id
        message_ids = [1, 2, 3, 4, 5]
        
        for msg_id in message_ids:
            dialog_manager.add_message_to_history(user_id, msg_id)
        
        # 执行清理
        await dialog_manager.cleanup_user_messages(user_id, keep_last=2)
        
        # 验证删除消息的调用
        assert mock_bot.delete_message.call_count == 3  # 删除前3条消息
    
    def test_path_manager_path_resolution(self):
        """测试路径管理器路径解析"""
        from path_manager import PathManager
        
        # 测试数据库路径
        db_path = PathManager.get_db_path()
        assert db_path.endswith('.db')
        assert isinstance(db_path, str)
        
        # 测试模板路径
        template_path = PathManager.get_template_path('test.html')
        assert 'test.html' in template_path
        assert isinstance(template_path, str)
    
    def test_config_validation(self):
        """测试配置验证"""
        from config import bot_config, ADMIN_IDS, MESSAGE_TEMPLATES
        
        # 验证基本配置存在
        assert hasattr(bot_config, 'token')
        assert isinstance(ADMIN_IDS, list)
        assert isinstance(MESSAGE_TEMPLATES, dict)
        
        # 验证消息模板完整性
        required_templates = ['welcome', 'merchant_info', 'service_selection']
        for template in required_templates:
            assert template in MESSAGE_TEMPLATES or any(template in key for key in MESSAGE_TEMPLATES.keys())