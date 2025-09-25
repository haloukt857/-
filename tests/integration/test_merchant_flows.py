"""
商家流程集成测试
测试商家注册、管理和交互的完整工作流程
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
from states.merchant_states import MerchantStates
from dialogs.binding_flow import BindingFlow


class TestMerchantRegistrationFlow:
    """商家注册流程测试"""
    
    @pytest.fixture
    def storage(self):
        return MemoryStorage()
    
    @pytest.fixture
    async def merchant_fsm_context(self, storage, mock_user, mock_chat):
        context = FSMContext(
            storage=storage,
            key=storage.get_key(
                bot_id=12345,
                chat_id=mock_chat.id,
                user_id=mock_user.id
            )
        )
        return context
    
    @pytest.fixture
    async def valid_binding_code(self, db_manager):
        """创建有效的绑定码"""
        bindings_db = BindingsDatabase()
        return await bindings_db.generate_binding_code()
    
    @pytest.mark.asyncio
    async def test_complete_registration_success_flow(self, mock_user, mock_chat, merchant_fsm_context, valid_binding_code, db_manager):
        """测试成功的完整注册流程"""
        
        # 1. 商家输入"上榜流程"
        from handlers.merchant import handle_binding_request
        
        binding_msg = AsyncMock(spec=Message)
        binding_msg.from_user = mock_user
        binding_msg.chat = mock_chat
        binding_msg.text = "上榜流程"
        
        await handle_binding_request(binding_msg, merchant_fsm_context)
        
        # 验证引导信息和状态
        binding_msg.answer.assert_called_once()
        state = await merchant_fsm_context.get_state()
        assert state == MerchantStates.entering_binding_code
        
        # 2. 商家输入有效绑定码
        from handlers.merchant import handle_binding_code_entry
        
        code_msg = AsyncMock(spec=Message)
        code_msg.from_user = mock_user
        code_msg.text = valid_binding_code
        
        await handle_binding_code_entry(code_msg, merchant_fsm_context)
        
        # 验证码验证成功
        code_msg.answer.assert_called()
        state = await merchant_fsm_context.get_state()
        assert state == MerchantStates.selecting_region
        
        # 验证FSM数据
        data = await merchant_fsm_context.get_data()
        assert data["binding_code"] == valid_binding_code
        
        # 3. 选择地区
        from dialogs.binding_flow import handle_region_selection
        
        region_callback = AsyncMock(spec=CallbackQuery)
        region_callback.from_user = mock_user
        region_callback.data = "region_beijing"
        region_callback.message = AsyncMock()
        
        await handle_region_selection(region_callback, merchant_fsm_context)
        
        # 验证地区选择
        data = await merchant_fsm_context.get_data()
        assert "region" in data
        state = await merchant_fsm_context.get_state()
        assert state == MerchantStates.selecting_category
        
        # 4. 选择类别
        from dialogs.binding_flow import handle_category_selection
        
        category_callback = AsyncMock(spec=CallbackQuery)
        category_callback.from_user = mock_user
        category_callback.data = "category_education"
        category_callback.message = AsyncMock()
        
        await handle_category_selection(category_callback, merchant_fsm_context)
        
        # 验证类别选择
        data = await merchant_fsm_context.get_data()
        assert "category" in data
        state = await merchant_fsm_context.get_state()
        assert state == MerchantStates.entering_details
        
        # 5. 输入商家详细信息
        from dialogs.binding_flow import handle_merchant_details
        
        details_msg = AsyncMock(spec=Message)
        details_msg.from_user = mock_user
        details_msg.text = "张老师英语培训\n专业雅思托福培训\n微信：english_zhang"
        
        await handle_merchant_details(details_msg, merchant_fsm_context)
        
        # 验证详细信息
        data = await merchant_fsm_context.get_data()
        assert "merchant_name" in data
        assert "description" in data
        assert "contact_info" in data
        state = await merchant_fsm_context.get_state()
        assert state == MerchantStates.confirming_profile
        
        # 6. 确认档案
        from dialogs.binding_flow import handle_profile_confirmation
        
        confirm_callback = AsyncMock(spec=CallbackQuery)
        confirm_callback.from_user = mock_user
        confirm_callback.data = "confirm_profile"
        confirm_callback.message = AsyncMock()
        
        await handle_profile_confirmation(confirm_callback, merchant_fsm_context)
        
        # 验证商家创建成功
        merchants_db = MerchantsDatabase()
        merchant = await merchants_db.get_merchant_by_chat_id(mock_user.id)
        assert merchant is not None
        assert merchant["status"] == "active"
        
        # 验证绑定码被使用
        bindings_db = BindingsDatabase()
        is_valid = await bindings_db.validate_binding_code(valid_binding_code)
        assert not is_valid
        
        # 验证FSM状态清除
        state = await merchant_fsm_context.get_state()
        assert state is None
        
        # 验证成功通知
        confirm_callback.message.edit_text.assert_called()
        success_text = confirm_callback.message.edit_text.call_args[0][0]
        assert "成功" in success_text or "欢迎" in success_text
    
    @pytest.mark.asyncio
    async def test_registration_with_back_navigation(self, mock_user, merchant_fsm_context, valid_binding_code, db_manager):
        """测试注册过程中的返回导航"""
        
        # 设置用户已完成到类别选择的状态
        await merchant_fsm_context.set_state(MerchantStates.selecting_category)
        await merchant_fsm_context.update_data({
            "binding_code": valid_binding_code,
            "region": "北京",
            "category": "教育培训"
        })
        
        # 用户点击返回按钮
        from dialogs.binding_flow import handle_back_navigation
        
        back_callback = AsyncMock(spec=CallbackQuery)
        back_callback.from_user = mock_user
        back_callback.data = "back_to_region"
        back_callback.message = AsyncMock()
        
        await handle_back_navigation(back_callback, merchant_fsm_context)
        
        # 验证状态回退
        state = await merchant_fsm_context.get_state()
        assert state == MerchantStates.selecting_region
        
        # 验证数据回退（category应该被清除）
        data = await merchant_fsm_context.get_data()
        assert "region" in data
        assert "category" not in data
        
        # 验证界面更新
        back_callback.message.edit_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_registration_cancellation(self, mock_user, merchant_fsm_context, valid_binding_code, db_manager):
        """测试注册过程取消"""
        
        # 设置用户在选择地区状态
        await merchant_fsm_context.set_state(MerchantStates.selecting_region)
        await merchant_fsm_context.update_data({"binding_code": valid_binding_code})
        
        # 用户选择取消注册
        from dialogs.binding_flow import handle_registration_cancellation
        
        cancel_callback = AsyncMock(spec=CallbackQuery)
        cancel_callback.from_user = mock_user
        cancel_callback.data = "cancel_registration"
        cancel_callback.message = AsyncMock()
        
        await handle_registration_cancellation(cancel_callback, merchant_fsm_context)
        
        # 验证状态清除
        state = await merchant_fsm_context.get_state()
        assert state is None
        
        # 验证绑定码未被使用（可以被其他人使用）
        bindings_db = BindingsDatabase()
        is_valid = await bindings_db.validate_binding_code(valid_binding_code)
        assert is_valid
        
        # 验证取消确认信息
        cancel_callback.message.edit_text.assert_called()
        cancel_text = cancel_callback.message.edit_text.call_args[0][0]
        assert "取消" in cancel_text or "退出" in cancel_text


class TestMerchantProfileManagement:
    """商家档案管理测试"""
    
    @pytest.fixture
    async def registered_merchant(self, db_manager, mock_user):
        """创建已注册的商家"""
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": mock_user.id,
            "name": "测试英语培训",
            "region": "北京",
            "category": "教育培训",
            "contact_info": "微信：test_english",
            "profile_data": {
                "description": "专业英语培训服务",
                "services": ["雅思", "托福", "商务英语"],
                "price_range": "200-500元/小时"
            },
            "status": "active"
        }
        merchant_id = await merchants_db.create_merchant(merchant_data)
        return merchant_id
    
    @pytest.mark.asyncio
    async def test_view_merchant_profile(self, mock_user, registered_merchant, db_manager):
        """测试查看商家档案"""
        
        from handlers.merchant import cmd_view_profile
        
        profile_msg = AsyncMock(spec=Message)
        profile_msg.from_user = mock_user
        profile_msg.text = "/profile"
        
        await cmd_view_profile(profile_msg, AsyncMock())
        
        # 验证档案信息显示
        profile_msg.answer.assert_called_once()
        response_text = profile_msg.answer.call_args[0][0]
        
        # 验证包含商家信息
        assert "测试英语培训" in response_text
        assert "北京" in response_text
        assert "教育培训" in response_text
        assert "active" in response_text or "激活" in response_text
    
    @pytest.mark.asyncio
    async def test_update_merchant_contact_info(self, mock_user, registered_merchant, merchant_fsm_context, db_manager):
        """测试更新商家联系信息"""
        
        from handlers.merchant import cmd_update_contact
        
        # 商家请求更新联系信息
        update_msg = AsyncMock(spec=Message)
        update_msg.from_user = mock_user
        update_msg.text = "/update_contact"
        
        await cmd_update_contact(update_msg, merchant_fsm_context)
        
        # 验证进入更新状态
        state = await merchant_fsm_context.get_state()
        assert state == MerchantStates.updating_contact
        
        # 商家提供新的联系信息
        from handlers.merchant import handle_contact_update
        
        new_contact_msg = AsyncMock(spec=Message)
        new_contact_msg.from_user = mock_user
        new_contact_msg.text = "微信：new_english_teacher\n电话：13800138000"
        
        await handle_contact_update(new_contact_msg, merchant_fsm_context)
        
        # 验证联系信息更新
        merchants_db = MerchantsDatabase()
        merchant = await merchants_db.get_merchant(registered_merchant)
        assert "new_english_teacher" in merchant["contact_info"]
        assert "13800138000" in merchant["contact_info"]
        
        # 验证状态清除
        state = await merchant_fsm_context.get_state()
        assert state is None
    
    @pytest.mark.asyncio
    async def test_update_merchant_services(self, mock_user, registered_merchant, merchant_fsm_context, db_manager):
        """测试更新商家服务信息"""
        
        from handlers.merchant import cmd_update_services
        
        # 商家请求更新服务信息
        update_services_msg = AsyncMock(spec=Message)
        update_services_msg.from_user = mock_user
        update_services_msg.text = "/update_services"
        
        await cmd_update_services(update_services_msg, merchant_fsm_context)
        
        # 验证进入更新状态
        state = await merchant_fsm_context.get_state()
        assert state == MerchantStates.updating_services
        
        # 商家提供新的服务信息
        from handlers.merchant import handle_services_update
        
        new_services_msg = AsyncMock(spec=Message)
        new_services_msg.from_user = mock_user
        new_services_msg.text = "新增服务：\n• GRE培训\n• 学术英语写作\n• 商务英语口语\n价格：300-800元/小时"
        
        await handle_services_update(new_services_msg, merchant_fsm_context)
        
        # 验证服务信息更新
        merchants_db = MerchantsDatabase()
        merchant = await merchants_db.get_merchant(registered_merchant)
        profile_data = merchant["profile_data"]
        
        # 验证新服务被添加
        assert "GRE培训" in str(profile_data)
        assert "学术英语写作" in str(profile_data)
        assert "300-800元/小时" in str(profile_data)


class TestMerchantOrderManagement:
    """商家订单管理测试"""
    
    @pytest.fixture
    async def merchant_with_orders(self, db_manager, mock_user):
        """创建有订单的商家"""
        # 创建商家
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": mock_user.id,
            "name": "订单测试商家",
            "region": "上海",
            "category": "教育培训",
            "contact_info": "微信：order_test"
        }
        merchant_id = await merchants_db.create_merchant(merchant_data)
        
        # 创建测试订单
        order_manager_v2 = OrderManagerV2()
        test_orders = [
            {
                "user_id": 123456,
                "username": "@user123",
                "merchant_id": merchant_id,
                "order_type": "appointment",
                "price": 300.00,
                "status": "pending"
            },
            {
                "user_id": 234567,
                "username": "@user234",
                "merchant_id": merchant_id,
                "order_type": "follow",
                "price": 0.00,
                "status": "completed"
            },
            {
                "user_id": 345678,
                "username": "@user345",
                "merchant_id": merchant_id,
                "order_type": "appointment",
                "price": 450.00,
                "status": "confirmed"
            }
        ]
        
        order_ids = []
        for order_data in test_orders:
            order_id = await order_manager_v2.create_order(order_data)
            order_ids.append(order_id)
        
        return {"merchant_id": merchant_id, "order_ids": order_ids}
    
    @pytest.mark.asyncio
    async def test_view_merchant_orders(self, mock_user, merchant_with_orders, db_manager):
        """测试查看商家订单"""
        
        from handlers.merchant import cmd_view_orders
        
        orders_msg = AsyncMock(spec=Message)
        orders_msg.from_user = mock_user
        orders_msg.text = "/orders"
        
        await cmd_view_orders(orders_msg, AsyncMock())
        
        # 验证订单列表显示
        orders_msg.answer.assert_called_once()
        response_text = orders_msg.answer.call_args[0][0]
        
        # 验证包含测试订单信息
        assert "@user123" in response_text
        assert "@user234" in response_text
        assert "@user345" in response_text
        assert "appointment" in response_text or "预约" in response_text
        assert "follow" in response_text or "关注" in response_text
        assert "300" in response_text
        assert "450" in response_text
    
    @pytest.mark.asyncio
    async def test_update_order_status(self, mock_user, merchant_with_orders, db_manager):
        """测试更新订单状态"""
        
        from handlers.merchant import handle_order_status_update
        
        order_id = merchant_with_orders["order_ids"][0]  # 第一个订单
        
        # 商家更新订单状态
        status_callback = AsyncMock(spec=CallbackQuery)
        status_callback.from_user = mock_user
        status_callback.data = f"order_status_{order_id}_confirmed"
        status_callback.message = AsyncMock()
        
        await handle_order_status_update(status_callback, AsyncMock())
        
        # 验证订单状态更新
        order_manager_v2 = OrderManagerV2()
        order = await order_manager_v2.get_order(order_id)
        assert order["status"] == "confirmed"
        
        # 验证响应确认
        status_callback.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_merchant_order_statistics(self, mock_user, merchant_with_orders, db_manager):
        """测试商家订单统计"""
        
        from handlers.merchant import cmd_order_stats
        
        stats_msg = AsyncMock(spec=Message)
        stats_msg.from_user = mock_user
        stats_msg.text = "/order_stats"
        
        await cmd_order_stats(stats_msg, AsyncMock())
        
        # 验证统计信息
        stats_msg.answer.assert_called_once()
        response_text = stats_msg.answer.call_args[0][0]
        
        # 验证统计数据
        assert "订单" in response_text
        assert "预约" in response_text or "appointment" in response_text
        assert "关注" in response_text or "follow" in response_text
        
        # 应该包含数量统计
        import re
        numbers = re.findall(r'\d+', response_text)
        assert len(numbers) > 0


class TestMerchantNotifications:
    """商家通知测试"""
    
    @pytest.fixture
    async def active_merchant(self, db_manager, mock_user):
        """创建激活的商家"""
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": mock_user.id,
            "name": "通知测试商家",
            "region": "深圳",
            "category": "美容美发",
            "contact_info": "微信：notify_test"
        }
        return await merchants_db.create_merchant(merchant_data)
    
    @pytest.mark.asyncio
    async def test_new_order_notification(self, mock_bot, active_merchant, mock_user, db_manager):
        """测试新订单通知"""
        
        from handlers.merchant import notify_merchant_new_order
        
        # 模拟新订单数据
        order_data = {
            "user_id": 555666,
            "username": "@new_customer",
            "merchant_id": active_merchant,
            "order_type": "appointment",
            "price": 280.00,
            "created_at": datetime.now()
        }
        
        await notify_merchant_new_order(mock_bot, order_data)
        
        # 验证通知发送给商家
        mock_bot.send_message.assert_called_once_with(
            mock_user.id,
            pytest.approx(str, abs=0)
        )
        
        # 验证通知内容
        notification_text = mock_bot.send_message.call_args[0][1]
        assert "新订单" in notification_text or "预约" in notification_text
        assert "@new_customer" in notification_text
        assert "280" in notification_text
    
    @pytest.mark.asyncio
    async def test_order_cancellation_notification(self, mock_bot, active_merchant, mock_user, db_manager):
        """测试订单取消通知"""
        
        from handlers.merchant import notify_merchant_order_cancelled
        
        # 模拟订单取消数据
        cancellation_data = {
            "order_id": 12345,
            "user_id": 666777,
            "username": "@cancelled_customer",
            "merchant_id": active_merchant,
            "reason": "时间冲突",
            "cancelled_at": datetime.now()
        }
        
        await notify_merchant_order_cancelled(mock_bot, cancellation_data)
        
        # 验证取消通知
        mock_bot.send_message.assert_called_once()
        notification_text = mock_bot.send_message.call_args[0][1]
        
        assert "取消" in notification_text
        assert "@cancelled_customer" in notification_text
        assert "时间冲突" in notification_text
    
    @pytest.mark.asyncio
    async def test_merchant_notification_preferences(self, mock_user, active_merchant, db_manager):
        """测试商家通知偏好设置"""
        
        from handlers.merchant import cmd_notification_settings
        
        settings_msg = AsyncMock(spec=Message)
        settings_msg.from_user = mock_user
        settings_msg.text = "/notification_settings"
        
        await cmd_notification_settings(settings_msg, AsyncMock())
        
        # 验证设置界面显示
        settings_msg.answer.assert_called_once()
        
        # 模拟设置通知偏好
        from handlers.merchant import handle_notification_preference
        
        pref_callback = AsyncMock(spec=CallbackQuery)
        pref_callback.from_user = mock_user
        pref_callback.data = "notify_new_orders_on"
        pref_callback.message = AsyncMock()
        
        await handle_notification_preference(pref_callback, AsyncMock())
        
        # 验证偏好保存
        pref_callback.answer.assert_called_once()


class TestMerchantStatusChanges:
    """商家状态变更测试"""
    
    @pytest.fixture
    async def status_test_merchant(self, db_manager, mock_user):
        """创建状态测试商家"""
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": mock_user.id,
            "name": "状态测试商家",
            "region": "杭州",
            "category": "餐饮服务",
            "contact_info": "微信：status_test",
            "status": "active"
        }
        return await merchants_db.create_merchant(merchant_data)
    
    @pytest.mark.asyncio
    async def test_merchant_self_pause(self, mock_user, status_test_merchant, db_manager):
        """测试商家自行暂停服务"""
        
        from handlers.merchant import cmd_pause_service
        
        pause_msg = AsyncMock(spec=Message)
        pause_msg.from_user = mock_user
        pause_msg.text = "/pause_service"
        
        await cmd_pause_service(pause_msg, AsyncMock())
        
        # 验证状态更新
        merchants_db = MerchantsDatabase()
        merchant = await merchants_db.get_merchant(status_test_merchant)
        assert merchant["status"] == "paused"
        
        # 验证确认消息
        pause_msg.answer.assert_called_once()
        response_text = pause_msg.answer.call_args[0][0]
        assert "暂停" in response_text
    
    @pytest.mark.asyncio
    async def test_merchant_resume_service(self, mock_user, status_test_merchant, db_manager):
        """测试商家恢复服务"""
        
        # 先设置为暂停状态
        merchants_db = MerchantsDatabase()
        await merchants_db.update_merchant_status(status_test_merchant, "paused")
        
        from handlers.merchant import cmd_resume_service
        
        resume_msg = AsyncMock(spec=Message)
        resume_msg.from_user = mock_user
        resume_msg.text = "/resume_service"
        
        await cmd_resume_service(resume_msg, AsyncMock())
        
        # 验证状态恢复
        merchant = await merchants_db.get_merchant(status_test_merchant)
        assert merchant["status"] == "active"
        
        # 验证确认消息
        resume_msg.answer.assert_called_once()
        response_text = resume_msg.answer.call_args[0][0]
        assert "恢复" in response_text or "激活" in response_text
    
    @pytest.mark.asyncio
    async def test_merchant_status_change_notifications(self, mock_bot, mock_user, status_test_merchant, db_manager):
        """测试状态变更通知"""
        
        from handlers.merchant import notify_status_change
        
        # 模拟管理员暂停商家
        await notify_status_change(
            mock_bot, 
            mock_user.id, 
            "paused", 
            "管理员操作：暂时维护"
        )
        
        # 验证通知发送
        mock_bot.send_message.assert_called_once()
        notification_text = mock_bot.send_message.call_args[0][1]
        
        assert "状态" in notification_text
        assert "暂停" in notification_text or "paused" in notification_text
        assert "管理员操作" in notification_text


class TestMerchantDataIntegrity:
    """商家数据完整性测试"""
    
    @pytest.mark.asyncio
    async def test_prevent_duplicate_registration(self, mock_user, db_manager):
        """测试防止重复注册"""
        
        # 先注册一个商家
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": mock_user.id,
            "name": "重复测试商家",
            "region": "成都",
            "category": "维修服务",
            "contact_info": "微信：duplicate_test"
        }
        first_merchant_id = await merchants_db.create_merchant(merchant_data)
        
        # 尝试再次注册相同chat_id的商家（应该失败）
        duplicate_data = merchant_data.copy()
        duplicate_data["name"] = "重复商家2"
        
        with pytest.raises(Exception):  # 应该抛出唯一性约束异常
            await merchants_db.create_merchant(duplicate_data)
    
    @pytest.mark.asyncio
    async def test_merchant_data_validation(self, db_manager):
        """测试商家数据验证"""
        
        from handlers.merchant import validate_merchant_data
        
        # 测试有效数据
        valid_data = {
            "chat_id": 999888777,
            "name": "有效商家",
            "region": "西安",
            "category": "教育培训",
            "contact_info": "微信：valid_merchant"
        }
        
        validation_result = validate_merchant_data(valid_data)
        assert validation_result["valid"] is True
        assert len(validation_result["errors"]) == 0
        
        # 测试无效数据
        invalid_data = {
            "chat_id": "not_a_number",  # 应该是整数
            "name": "",  # 不能为空
            "region": None,  # 不能为空
            "category": "未知类别",  # 不在允许的类别中
            "contact_info": ""  # 不能为空
        }
        
        validation_result = validate_merchant_data(invalid_data)
        assert validation_result["valid"] is False
        assert len(validation_result["errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_merchant_profile_consistency(self, mock_user, db_manager):
        """测试商家档案一致性"""
        
        # 创建商家
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": mock_user.id,
            "name": "一致性测试商家",
            "region": "武汉",
            "category": "健康医疗",
            "contact_info": "微信：consistency_test",
            "profile_data": {
                "services": ["中医推拿", "针灸"],
                "price_range": "80-200元/次",
                "experience": "10年经验"
            }
        }
        merchant_id = await merchants_db.create_merchant(merchant_data)
        
        # 更新部分信息
        await merchants_db.update_merchant_contact(merchant_id, "微信：updated_contact\n电话：13900139000")
        
        # 验证更新后的一致性
        updated_merchant = await merchants_db.get_merchant(merchant_id)
        assert updated_merchant["contact_info"] == "微信：updated_contact\n电话：13900139000"
        assert updated_merchant["name"] == "一致性测试商家"  # 其他信息应该保持不变
        assert updated_merchant["region"] == "武汉"
        assert updated_merchant["category"] == "健康医疗"


class TestMerchantConcurrencyHandling:
    """商家并发处理测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_order_updates(self, db_manager, mock_user):
        """测试并发订单更新"""
        
        # 创建测试商家和订单
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": mock_user.id,
            "name": "并发测试商家",
            "region": "天津",
            "category": "教育培训"
        }
        merchant_id = await merchants_db.create_merchant(merchant_data)
        
        order_manager_v2 = OrderManagerV2()
        order_data = {
            "user_id": 777888,
            "merchant_id": merchant_id,
            "order_type": "appointment",
            "price": 200.00,
            "status": "pending"
        }
        order_id = await order_manager_v2.create_order(order_data)
        
        # 模拟并发状态更新
        async def update_order_status(status):
            return await order_manager_v2.update_order_status(order_id, status)
        
        # 并发执行多个状态更新
        import asyncio
        tasks = [
            update_order_status("confirmed"),
            update_order_status("completed"),
            update_order_status("cancelled")
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证至少有一个更新成功
        successful_updates = [r for r in results if r is True]
        assert len(successful_updates) >= 1
        
        # 验证最终状态是一致的
        final_order = await order_manager_v2.get_order(order_id)
        assert final_order["status"] in ["confirmed", "completed", "cancelled"]
    
    @pytest.mark.asyncio
    async def test_concurrent_profile_updates(self, db_manager, mock_user):
        """测试并发档案更新"""
        
        # 创建测试商家
        merchants_db = MerchantsDatabase()
        merchant_data = {
            "chat_id": mock_user.id,
            "name": "档案并发测试",
            "region": "重庆",
            "category": "生活服务"
        }
        merchant_id = await merchants_db.create_merchant(merchant_data)
        
        # 模拟并发档案更新任务
        async def update_contact_info(new_contact):
            return await merchants_db.update_merchant_contact(merchant_id, new_contact)
        
        async def update_profile_data(new_data):
            return await merchants_db.update_merchant_profile(merchant_id, new_data)
        
        # 并发执行更新
        import asyncio
        tasks = [
            update_contact_info("微信：concurrent_test_1"),
            update_contact_info("微信：concurrent_test_2"),
            update_profile_data({"description": "并发测试服务1"}),
            update_profile_data({"description": "并发测试服务2"})
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证更新操作没有导致数据损坏
        final_merchant = await merchants_db.get_merchant(merchant_id)
        assert final_merchant is not None
        assert final_merchant["name"] == "档案并发测试"  # 基本信息应该保持一致