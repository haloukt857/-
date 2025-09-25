"""
管理员流程集成测试
测试管理员的完整工作流程和权限管理
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

from database.db_merchants import MerchantManager as MerchantsDatabase
from database.db_orders import OrderManager as OrderManagerV2
from database.db_binding_codes import BindingCodesManager as BindingsDatabase
from database.db_logs import ActivityLogsDatabase
from states.admin_states import AdminStates
from config import ADMIN_IDS


class TestAdminPermissions:
    """管理员权限测试"""
    
    @pytest.mark.asyncio
    async def test_admin_command_access(self, mock_admin_user, config_override):
        """测试管理员命令访问权限"""
        from handlers.admin import cmd_set_button, cmd_generate_code, cmd_view_stats
        
        # 创建模拟消息
        admin_message = AsyncMock(spec=Message)
        admin_message.from_user = mock_admin_user
        mock_fsm_context = AsyncMock()
        
        # 测试管理员可以访问所有命令
        await cmd_set_button(admin_message, mock_fsm_context)
        admin_message.answer.assert_called()
        
        admin_message.reset_mock()
        await cmd_generate_code(admin_message, mock_fsm_context)
        admin_message.answer.assert_called()
        
        admin_message.reset_mock()
        await cmd_view_stats(admin_message, mock_fsm_context)
        admin_message.answer.assert_called()
    
    @pytest.mark.asyncio
    async def test_non_admin_command_denial(self, mock_user, config_override):
        """测试非管理员用户被拒绝访问"""
        from handlers.admin import cmd_set_button
        
        # 创建非管理员用户消息
        user_message = AsyncMock(spec=Message)
        user_message.from_user = mock_user  # 非管理员用户
        mock_fsm_context = AsyncMock()
        
        await cmd_set_button(user_message, mock_fsm_context)
        
        # 验证拒绝访问
        user_message.answer.assert_called_once()
        response_text = user_message.answer.call_args[0][0]
        assert "权限" in response_text or "无权" in response_text


class TestButtonManagement:
    """按钮管理测试"""
    
    @pytest.fixture
    def storage(self):
        return MemoryStorage()
    
    @pytest.fixture
    async def admin_fsm_context(self, storage, mock_admin_user, mock_chat):
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
    async def test_complete_button_configuration_flow(self, mock_admin_user, admin_fsm_context, config_override, db_manager):
        """测试完整的按钮配置流程"""
        
        # 1. 启动按钮设置
        from handlers.admin import cmd_set_button
        
        set_button_msg = AsyncMock(spec=Message)
        set_button_msg.from_user = mock_admin_user
        set_button_msg.text = "/set_button"
        
        await cmd_set_button(set_button_msg, admin_fsm_context)
        
        # 验证进入设置消息状态
        state = await admin_fsm_context.get_state()
        assert state == AdminStates.setting_message
        
        # 2. 输入消息内容
        from handlers.admin import handle_message_input
        
        message_input = AsyncMock(spec=Message)
        message_input.from_user = mock_admin_user
        message_input.text = "🏪 选择您需要的服务商家："
        
        await handle_message_input(message_input, admin_fsm_context)
        
        # 验证状态转换
        state = await admin_fsm_context.get_state()
        assert state == AdminStates.configuring_buttons
        
        # 验证数据保存
        data = await admin_fsm_context.get_data()
        assert data["message_text"] == "🏪 选择您需要的服务商家："
        
        # 3. 添加按钮
        from handlers.admin import handle_button_configuration
        
        add_button_callback = AsyncMock(spec=CallbackQuery)
        add_button_callback.from_user = mock_admin_user
        add_button_callback.data = "add_button"
        add_button_callback.message = AsyncMock()
        
        await handle_button_configuration(add_button_callback, admin_fsm_context)
        
        # 验证进入添加按钮状态
        state = await admin_fsm_context.get_state()
        assert state == AdminStates.adding_button
        
        # 4. 输入按钮信息
        from handlers.admin import handle_button_input
        
        button_input = AsyncMock(spec=Message)
        button_input.from_user = mock_admin_user
        button_input.text = "📚 教育培训|merchant_1"  # 格式：显示文本|回调数据
        
        await handle_button_input(button_input, admin_fsm_context)
        
        # 验证按钮添加到数据中
        data = await admin_fsm_context.get_data()
        assert "buttons" in data
        assert len(data["buttons"]) == 1
        assert data["buttons"][0]["text"] == "📚 教育培训"
        assert data["buttons"][0]["callback_data"] == "merchant_1"
        
        # 5. 完成配置
        finish_callback = AsyncMock(spec=CallbackQuery)
        finish_callback.from_user = mock_admin_user
        finish_callback.data = "finish_config"
        finish_callback.message = AsyncMock()
        
        await handle_button_configuration(finish_callback, admin_fsm_context)
        
        # 验证配置保存到数据库
        # 这里可以添加数据库验证逻辑
        
        # 验证状态清除
        state = await admin_fsm_context.get_state()
        assert state is None
    
    @pytest.mark.asyncio
    async def test_button_validation(self, mock_admin_user, admin_fsm_context, config_override):
        """测试按钮输入验证"""
        
        # 设置状态
        await admin_fsm_context.set_state(AdminStates.adding_button)
        
        from handlers.admin import handle_button_input
        
        # 测试无效格式的按钮输入
        invalid_input = AsyncMock(spec=Message)
        invalid_input.from_user = mock_admin_user
        invalid_input.text = "无效按钮格式"  # 缺少分隔符
        
        await handle_button_input(invalid_input, admin_fsm_context)
        
        # 验证错误提示
        invalid_input.answer.assert_called()
        error_msg = invalid_input.answer.call_args[0][0]
        assert "格式" in error_msg or "无效" in error_msg
        
        # 验证状态保持不变
        state = await admin_fsm_context.get_state()
        assert state == AdminStates.adding_button


class TestStatisticsManagement:
    """统计管理测试"""
    
    @pytest.fixture
    async def setup_test_statistics(self, db_manager):
        """设置测试统计数据"""
        logs_db = ActivityLogsDatabase()
        
        # 添加测试日志数据
        test_data = [
            {"user_id": 123456, "button_id": "merchant_1", "action": "button_click"},
            {"user_id": 123457, "button_id": "merchant_1", "action": "button_click"},
            {"user_id": 123458, "button_id": "merchant_2", "action": "button_click"},
            {"user_id": 123456, "action_type": "merchant_contact", "details": {"merchant_id": 1}},
            {"user_id": 123457, "action_type": "appointment", "details": {"merchant_id": 1}},
        ]
        
        for data in test_data:
            if "button_id" in data:
                await logs_db.log_button_click(data["user_id"], data["button_id"])
            else:
                await logs_db.log_user_interaction(
                    data["user_id"], 
                    data["action_type"], 
                    data["details"]
                )
        
        return logs_db
    
    @pytest.mark.asyncio
    async def test_view_comprehensive_statistics(self, mock_admin_user, config_override, setup_test_statistics):
        """测试查看综合统计信息"""
        
        from handlers.admin import cmd_view_stats
        
        stats_message = AsyncMock(spec=Message)
        stats_message.from_user = mock_admin_user
        stats_message.text = "/view_stats"
        mock_fsm_context = AsyncMock()
        
        await cmd_view_stats(stats_message, mock_fsm_context)
        
        # 验证统计信息返回
        stats_message.answer.assert_called_once()
        response_text = stats_message.answer.call_args[0][0]
        
        # 验证包含关键统计信息
        assert "点击" in response_text or "统计" in response_text
        assert "用户" in response_text
        
        # 验证数字统计存在
        import re
        numbers = re.findall(r'\d+', response_text)
        assert len(numbers) > 0  # 应该包含统计数字
    
    @pytest.mark.asyncio
    async def test_filtered_statistics(self, mock_admin_user, config_override, setup_test_statistics):
        """测试筛选统计信息"""
        
        from handlers.admin import handle_stats_filter
        
        # 模拟按时间筛选
        time_filter_callback = AsyncMock(spec=CallbackQuery)
        time_filter_callback.from_user = mock_admin_user
        time_filter_callback.data = "stats_filter_today"
        time_filter_callback.message = AsyncMock()
        
        await handle_stats_filter(time_filter_callback, AsyncMock())
        
        # 验证筛选结果
        time_filter_callback.message.edit_text.assert_called_once()
        
        # 模拟按按钮筛选
        button_filter_callback = AsyncMock(spec=CallbackQuery)
        button_filter_callback.from_user = mock_admin_user
        button_filter_callback.data = "stats_button_merchant_1"
        button_filter_callback.message = AsyncMock()
        
        await handle_stats_filter(button_filter_callback, AsyncMock())
        
        # 验证按钮筛选结果
        button_filter_callback.message.edit_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_export_statistics(self, mock_admin_user, config_override, setup_test_statistics):
        """测试导出统计数据"""
        
        from handlers.admin import handle_export_stats
        
        export_callback = AsyncMock(spec=CallbackQuery)
        export_callback.from_user = mock_admin_user
        export_callback.data = "export_stats_csv"
        export_callback.message = AsyncMock()
        
        await handle_export_stats(export_callback, AsyncMock())
        
        # 验证导出功能（这里应该发送文件）
        export_callback.message.answer_document.assert_called_once()


class TestBindingCodeManagement:
    """绑定码管理测试"""
    
    @pytest.mark.asyncio
    async def test_generate_single_binding_code(self, mock_admin_user, config_override, db_manager):
        """测试生成单个绑定码"""
        
        from handlers.admin import cmd_generate_code
        
        generate_msg = AsyncMock(spec=Message)
        generate_msg.from_user = mock_admin_user
        generate_msg.text = "/generate_code"
        mock_fsm_context = AsyncMock()
        
        await cmd_generate_code(generate_msg, mock_fsm_context)
        
        # 验证响应包含绑定码
        generate_msg.answer.assert_called_once()
        response_text = generate_msg.answer.call_args[0][0]
        
        # 提取绑定码并验证其有效性
        import re
        code_pattern = r'[A-Z0-9]{8}'
        codes = re.findall(code_pattern, response_text)
        assert len(codes) >= 1
        
        # 验证生成的码在数据库中有效
        bindings_db = BindingsDatabase()
        is_valid = await bindings_db.validate_binding_code(codes[0])
        assert is_valid
    
    @pytest.mark.asyncio
    async def test_generate_batch_binding_codes(self, mock_admin_user, config_override, db_manager):
        """测试批量生成绑定码"""
        
        from handlers.admin import handle_batch_generate_codes
        
        batch_callback = AsyncMock(spec=CallbackQuery)
        batch_callback.from_user = mock_admin_user
        batch_callback.data = "generate_batch_5"  # 生成5个码
        batch_callback.message = AsyncMock()
        
        await handle_batch_generate_codes(batch_callback, AsyncMock())
        
        # 验证批量生成
        batch_callback.message.edit_text.assert_called_once()
        response_text = batch_callback.message.edit_text.call_args[0][0]
        
        # 验证包含多个绑定码
        import re
        code_pattern = r'[A-Z0-9]{8}'
        codes = re.findall(code_pattern, response_text)
        assert len(codes) == 5
        
        # 验证所有码都有效
        bindings_db = BindingsDatabase()
        for code in codes:
            is_valid = await bindings_db.validate_binding_code(code)
            assert is_valid
    
    @pytest.mark.asyncio
    async def test_binding_code_expiration_management(self, mock_admin_user, config_override, db_manager):
        """测试绑定码过期管理"""
        
        from handlers.admin import cmd_cleanup_codes
        
        # 先创建一些即将过期的绑定码
        bindings_db = BindingsDatabase()
        
        # 创建过期码（手动插入到数据库）
        expired_time = datetime.now() - timedelta(hours=1)
        
        # 执行清理命令
        cleanup_msg = AsyncMock(spec=Message)
        cleanup_msg.from_user = mock_admin_user
        cleanup_msg.text = "/cleanup_codes"
        
        await cmd_cleanup_codes(cleanup_msg, AsyncMock())
        
        # 验证清理报告
        cleanup_msg.answer.assert_called_once()
        response_text = cleanup_msg.answer.call_args[0][0]
        assert "清理" in response_text or "过期" in response_text


class TestMerchantManagement:
    """商家管理测试"""
    
    @pytest.fixture
    async def setup_test_merchants(self, db_manager):
        """设置测试商家"""
        merchants_db = MerchantsDatabase()
        
        test_merchants = [
            {
                "chat_id": 111111111,
                "name": "测试教育机构A",
                "region": "北京",
                "category": "教育培训",
                "contact_info": "微信：edu_a",
                "status": "active"
            },
            {
                "chat_id": 222222222,
                "name": "测试美容店B",
                "region": "上海",
                "category": "美容美发",
                "contact_info": "微信：beauty_b",
                "status": "inactive"
            },
            {
                "chat_id": 333333333,
                "name": "测试餐厅C",
                "region": "广州",
                "category": "餐饮服务",
                "contact_info": "微信：food_c",
                "status": "active"
            }
        ]
        
        merchant_ids = []
        for merchant_data in test_merchants:
            merchant_id = await merchants_db.create_merchant(merchant_data)
            merchant_ids.append(merchant_id)
        
        return merchant_ids
    
    @pytest.mark.asyncio
    async def test_list_all_merchants(self, mock_admin_user, config_override, setup_test_merchants):
        """测试列出所有商家"""
        
        from handlers.admin import cmd_list_merchants
        
        list_msg = AsyncMock(spec=Message)
        list_msg.from_user = mock_admin_user
        list_msg.text = "/list_merchants"
        
        await cmd_list_merchants(list_msg, AsyncMock())
        
        # 验证商家列表
        list_msg.answer.assert_called_once()
        response_text = list_msg.answer.call_args[0][0]
        
        # 验证包含测试商家
        assert "测试教育机构A" in response_text
        assert "测试美容店B" in response_text
        assert "测试餐厅C" in response_text
        
        # 验证状态显示
        assert "active" in response_text or "激活" in response_text
        assert "inactive" in response_text or "未激活" in response_text
    
    @pytest.mark.asyncio
    async def test_merchant_status_management(self, mock_admin_user, config_override, setup_test_merchants, db_manager):
        """测试商家状态管理"""
        
        from handlers.admin import handle_merchant_status_change
        
        merchant_id = setup_test_merchants[0]  # 使用第一个测试商家
        
        # 暂停商家
        pause_callback = AsyncMock(spec=CallbackQuery)
        pause_callback.from_user = mock_admin_user
        pause_callback.data = f"pause_merchant_{merchant_id}"
        pause_callback.message = AsyncMock()
        
        await handle_merchant_status_change(pause_callback, AsyncMock())
        
        # 验证状态更改
        merchants_db = MerchantsDatabase()
        merchant = await merchants_db.get_merchant(merchant_id)
        assert merchant["status"] == "inactive"
        
        # 验证响应
        pause_callback.answer.assert_called_once()
        
        # 重新激活商家
        activate_callback = AsyncMock(spec=CallbackQuery)
        activate_callback.from_user = mock_admin_user
        activate_callback.data = f"activate_merchant_{merchant_id}"
        activate_callback.message = AsyncMock()
        
        await handle_merchant_status_change(activate_callback, AsyncMock())
        
        # 验证状态恢复
        merchant = await merchants_db.get_merchant(merchant_id)
        assert merchant["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_merchant_deletion_with_confirmation(self, mock_admin_user, config_override, setup_test_merchants, db_manager):
        """测试带确认的商家删除"""
        
        from handlers.admin import handle_merchant_deletion
        
        merchant_id = setup_test_merchants[2]  # 使用第三个测试商家
        
        # 请求删除（第一步：确认）
        delete_callback = AsyncMock(spec=CallbackQuery)
        delete_callback.from_user = mock_admin_user
        delete_callback.data = f"delete_merchant_{merchant_id}"
        delete_callback.message = AsyncMock()
        
        await handle_merchant_deletion(delete_callback, AsyncMock())
        
        # 验证确认提示
        delete_callback.message.edit_text.assert_called_once()
        confirm_text = delete_callback.message.edit_text.call_args[0][0]
        assert "确认" in confirm_text and "删除" in confirm_text
        
        # 确认删除（第二步：执行删除）
        confirm_callback = AsyncMock(spec=CallbackQuery)
        confirm_callback.from_user = mock_admin_user
        confirm_callback.data = f"confirm_delete_{merchant_id}"
        confirm_callback.message = AsyncMock()
        
        await handle_merchant_deletion(confirm_callback, AsyncMock())
        
        # 验证商家被删除
        merchants_db = MerchantsDatabase()
        merchant = await merchants_db.get_merchant(merchant_id)
        assert merchant is None


class TestSystemMonitoring:
    """系统监控测试"""
    
    @pytest.mark.asyncio
    async def test_system_health_check(self, mock_admin_user, config_override):
        """测试系统健康检查"""
        
        from handlers.admin import cmd_system_health
        
        health_msg = AsyncMock(spec=Message)
        health_msg.from_user = mock_admin_user
        health_msg.text = "/system_health"
        
        await cmd_system_health(health_msg, AsyncMock())
        
        # 验证健康报告
        health_msg.answer.assert_called_once()
        response_text = health_msg.answer.call_args[0][0]
        
        # 验证包含系统状态信息
        assert "数据库" in response_text or "系统" in response_text
        assert "状态" in response_text
    
    @pytest.mark.asyncio
    async def test_error_log_review(self, mock_admin_user, config_override):
        """测试错误日志查看"""
        
        from handlers.admin import cmd_view_errors
        
        errors_msg = AsyncMock(spec=Message)
        errors_msg.from_user = mock_admin_user
        errors_msg.text = "/view_errors"
        
        await cmd_view_errors(errors_msg, AsyncMock())
        
        # 验证错误日志
        errors_msg.answer.assert_called_once()
        response_text = errors_msg.answer.call_args[0][0]
        
        # 验证日志格式
        assert "错误" in response_text or "日志" in response_text or "暂无" in response_text


class TestAdminWorkflowIntegration:
    """管理员工作流程集成测试"""
    
    @pytest.mark.asyncio
    async def test_complete_admin_daily_workflow(self, mock_admin_user, config_override, db_manager):
        """测试管理员日常完整工作流程"""
        
        # 1. 查看系统状态
        from handlers.admin import cmd_system_health
        
        health_msg = AsyncMock(spec=Message)
        health_msg.from_user = mock_admin_user
        health_msg.text = "/system_health"
        
        await cmd_system_health(health_msg, AsyncMock())
        health_msg.answer.assert_called()
        
        # 2. 查看统计信息
        from handlers.admin import cmd_view_stats
        
        stats_msg = AsyncMock(spec=Message)
        stats_msg.from_user = mock_admin_user
        stats_msg.text = "/view_stats"
        
        await cmd_view_stats(stats_msg, AsyncMock())
        stats_msg.answer.assert_called()
        
        # 3. 生成绑定码
        from handlers.admin import cmd_generate_code
        
        generate_msg = AsyncMock(spec=Message)
        generate_msg.from_user = mock_admin_user
        generate_msg.text = "/generate_code"
        
        await cmd_generate_code(generate_msg, AsyncMock())
        generate_msg.answer.assert_called()
        
        # 4. 清理过期码
        from handlers.admin import cmd_cleanup_codes
        
        cleanup_msg = AsyncMock(spec=Message)
        cleanup_msg.from_user = mock_admin_user
        cleanup_msg.text = "/cleanup_codes"
        
        await cmd_cleanup_codes(cleanup_msg, AsyncMock())
        cleanup_msg.answer.assert_called()
        
        # 验证所有操作都成功执行
        assert True  # 如果到达这里，说明所有操作都没有抛出异常
    
    @pytest.mark.asyncio
    async def test_emergency_response_workflow(self, mock_admin_user, config_override, mock_bot):
        """测试紧急响应工作流程"""
        
        # 模拟系统错误报告
        from utils.error_recovery import ErrorRecoveryService
        
        error_service = ErrorRecoveryService(mock_bot)
        
        # 模拟严重错误
        critical_error = Exception("Critical database corruption")
        await error_service.handle_error(
            critical_error, 
            {"operation": "database_integrity_check", "critical": True}
        )
        
        # 验证管理员收到通知
        mock_bot.send_message.assert_called()
        
        # 管理员响应：启用维护模式
        from handlers.admin import cmd_maintenance_mode
        
        maintenance_msg = AsyncMock(spec=Message)
        maintenance_msg.from_user = mock_admin_user
        maintenance_msg.text = "/maintenance_mode on"
        
        await cmd_maintenance_mode(maintenance_msg, AsyncMock())
        
        # 验证维护模式启用确认
        maintenance_msg.answer.assert_called()
        
        # 管理员响应：发送系统公告
        from handlers.admin import cmd_broadcast
        
        broadcast_msg = AsyncMock(spec=Message)
        broadcast_msg.from_user = mock_admin_user
        broadcast_msg.text = "/broadcast 系统正在维护，预计30分钟后恢复"
        
        await cmd_broadcast(broadcast_msg, AsyncMock())
        
        # 验证公告发送
        broadcast_msg.answer.assert_called()