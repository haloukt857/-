"""
数据库操作单元测试
测试所有数据库模块的CRUD操作、验证和错误处理
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from database.db_merchants import MerchantManager as MerchantsDatabase
from database.db_orders import OrderManager as OrdersDatabase
from database.db_binding_codes import BindingCodesManager as BindingsDatabase
from database.db_logs import ActivityLogsDatabase
from database.db_connection import DatabaseManager


class TestMerchantsDatabase:
    """商家数据库操作测试"""
    
    @pytest.fixture
    async def merchants_db(self, db_manager):
        """创建商家数据库实例"""
        return MerchantsDatabase(db_manager)
    
    @pytest.mark.asyncio
    async def test_create_merchant(self, merchants_db, sample_merchant_data):
        """测试创建商家"""
        # 创建商家
        merchant_id = await merchants_db.create_merchant(sample_merchant_data)
        
        assert isinstance(merchant_id, int)
        assert merchant_id > 0
        
        # 验证商家是否成功创建
        merchant = await merchants_db.get_merchant(merchant_id)
        assert merchant is not None
        assert merchant["chat_id"] == sample_merchant_data["chat_id"]
        assert merchant["name"] == sample_merchant_data["name"]
        assert merchant["region"] == sample_merchant_data["region"]
        assert merchant["category"] == sample_merchant_data["category"]
    
    @pytest.mark.asyncio
    async def test_get_merchant_by_chat_id(self, merchants_db, sample_merchant_data):
        """测试通过chat_id获取商家"""
        # 先创建商家
        merchant_id = await merchants_db.create_merchant(sample_merchant_data)
        
        # 通过chat_id查询
        merchant = await merchants_db.get_merchant_by_chat_id(sample_merchant_data["chat_id"])
        
        assert merchant is not None
        assert merchant["id"] == merchant_id
        assert merchant["chat_id"] == sample_merchant_data["chat_id"]
    
    @pytest.mark.asyncio
    async def test_update_merchant_status(self, merchants_db, sample_merchant_data):
        """测试更新商家状态"""
        # 创建商家
        merchant_id = await merchants_db.create_merchant(sample_merchant_data)
        
        # 更新状态为inactive
        success = await merchants_db.update_merchant_status(merchant_id, "inactive")
        assert success
        
        # 验证状态更新
        merchant = await merchants_db.get_merchant(merchant_id)
        assert merchant["status"] == "inactive"
    
    @pytest.mark.asyncio
    async def test_get_all_merchants(self, merchants_db, sample_merchant_data):
        """测试获取所有商家"""
        # 创建多个商家
        merchant_data_2 = sample_merchant_data.copy()
        merchant_data_2["chat_id"] = 111222334
        merchant_data_2["name"] = "测试商家2"
        
        await merchants_db.create_merchant(sample_merchant_data)
        await merchants_db.create_merchant(merchant_data_2)
        
        # 获取所有商家
        merchants = await merchants_db.get_all_merchants()
        
        assert len(merchants) == 2
        assert any(m["name"] == "测试商家" for m in merchants)
        assert any(m["name"] == "测试商家2" for m in merchants)
    
    @pytest.mark.asyncio
    async def test_delete_merchant(self, merchants_db, sample_merchant_data):
        """测试删除商家"""
        # 创建商家
        merchant_id = await merchants_db.create_merchant(sample_merchant_data)
        
        # 删除商家
        success = await merchants_db.delete_merchant(merchant_id)
        assert success
        
        # 验证商家已删除
        merchant = await merchants_db.get_merchant(merchant_id)
        assert merchant is None
    
    @pytest.mark.asyncio
    async def test_get_merchants_by_region(self, merchants_db, sample_merchant_data):
        """测试按地区查询商家"""
        # 创建不同地区的商家
        beijing_merchant = sample_merchant_data.copy()
        beijing_merchant["region"] = "北京"
        beijing_merchant["chat_id"] = 111222335
        
        shanghai_merchant = sample_merchant_data.copy()
        shanghai_merchant["region"] = "上海"
        shanghai_merchant["chat_id"] = 111222336
        
        await merchants_db.create_merchant(beijing_merchant)
        await merchants_db.create_merchant(shanghai_merchant)
        
        # 查询北京地区商家
        beijing_merchants = await merchants_db.get_merchants_by_region("北京")
        assert len(beijing_merchants) == 1
        assert beijing_merchants[0]["region"] == "北京"


class TestOrdersDatabase:
    """订单数据库操作测试"""
    
    @pytest.fixture
    async def orders_db(self, db_manager):
        """创建订单数据库实例"""
        return OrdersDatabase()
    
    @pytest.fixture
    async def test_merchant_id(self, db_manager, sample_merchant_data):
        """创建测试商家并返回ID"""
        merchants_db = MerchantsDatabase()
        return await merchants_db.create_merchant(sample_merchant_data)
    
    @pytest.mark.asyncio
    async def test_create_order(self, orders_db, test_merchant_id, sample_order_data):
        """测试创建订单"""
        sample_order_data["merchant_id"] = test_merchant_id
        
        order_id = await orders_db.create_order(sample_order_data)
        
        assert isinstance(order_id, int)
        assert order_id > 0
        
        # 验证订单创建成功
        order = await orders_db.get_order(order_id)
        assert order is not None
        assert order["user_id"] == sample_order_data["user_id"]
        assert order["merchant_id"] == test_merchant_id
        assert order["order_type"] == sample_order_data["order_type"]
    
    @pytest.mark.asyncio
    async def test_get_orders_by_merchant(self, orders_db, test_merchant_id, sample_order_data):
        """测试按商家查询订单"""
        sample_order_data["merchant_id"] = test_merchant_id
        
        # 创建多个订单
        await orders_db.create_order(sample_order_data)
        
        order_data_2 = sample_order_data.copy()
        order_data_2["user_id"] = 987654321
        await orders_db.create_order(order_data_2)
        
        # 查询该商家的订单
        orders = await orders_db.get_orders_by_merchant(test_merchant_id)
        
        assert len(orders) == 2
        assert all(order["merchant_id"] == test_merchant_id for order in orders)
    
    @pytest.mark.asyncio
    async def test_get_orders_by_timeframe(self, orders_db, test_merchant_id, sample_order_data):
        """测试按时间范围查询订单"""
        sample_order_data["merchant_id"] = test_merchant_id
        
        order_id = await orders_db.create_order(sample_order_data)
        
        # 查询今天的订单
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        orders = await orders_db.get_orders_by_timeframe(start_date, end_date)
        
        assert len(orders) >= 1
        assert any(order["id"] == order_id for order in orders)
    
    @pytest.mark.asyncio
    async def test_update_order_status(self, orders_db, test_merchant_id, sample_order_data):
        """测试更新订单状态"""
        sample_order_data["merchant_id"] = test_merchant_id
        
        order_id = await orders_db.create_order(sample_order_data)
        
        # 更新状态
        success = await orders_db.update_order_status(order_id, "completed")
        assert success
        
        # 验证状态更新
        order = await orders_db.get_order(order_id)
        assert order["status"] == "completed"


class TestBindingsDatabase:
    """绑定码数据库操作测试"""
    
    @pytest.fixture
    async def bindings_db(self, db_manager):
        """创建绑定码数据库实例"""
        return BindingsDatabase()
    
    @pytest.mark.asyncio
    async def test_generate_binding_code(self, bindings_db):
        """测试生成绑定码"""
        code = await bindings_db.generate_binding_code()
        
        assert isinstance(code, str)
        assert len(code) == 8  # 默认长度
        assert code.isalnum()
        
        # 验证码已保存到数据库
        is_valid = await bindings_db.validate_binding_code(code)
        assert is_valid
    
    @pytest.mark.asyncio
    async def test_validate_binding_code(self, bindings_db):
        """测试验证绑定码"""
        # 生成有效码
        valid_code = await bindings_db.generate_binding_code()
        
        # 测试有效码
        assert await bindings_db.validate_binding_code(valid_code)
        
        # 测试无效码
        assert not await bindings_db.validate_binding_code("INVALID123")
    
    @pytest.mark.asyncio
    async def test_use_binding_code(self, bindings_db, sample_merchant_data, db_manager):
        """测试使用绑定码"""
        # 先创建商家
        merchants_db = MerchantsDatabase()
        merchant_id = await merchants_db.create_merchant(sample_merchant_data)
        
        # 生成绑定码
        code = await bindings_db.generate_binding_code()
        
        # 使用绑定码
        success = await bindings_db.use_binding_code(code, merchant_id)
        assert success
        
        # 验证码已被使用（不能再次验证）
        assert not await bindings_db.validate_binding_code(code)
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_codes(self, bindings_db):
        """测试清理过期码"""
        # 创建过期的绑定码
        expired_time = datetime.now() - timedelta(days=1)
        
        # 直接插入过期码到数据库进行测试
        async with db_manager.get_connection() as db:
            await db.execute(
                "INSERT INTO binding_codes (code, expires_at) VALUES (?, ?)",
                ("EXPIRED123", expired_time.isoformat())
            )
            await db.commit()
        
        # 执行清理
        cleaned_count = await bindings_db.cleanup_expired_codes()
        
        # 验证至少清理了一个过期码
        assert cleaned_count >= 1


class TestActivityLogsDatabase:
    """日志数据库操作测试"""
    
    @pytest.fixture
    async def logs_db(self, db_manager):
        """创建日志数据库实例"""
        return ActivityLogsDatabase()
    
    @pytest.mark.asyncio
    async def test_log_button_click(self, logs_db):
        """测试记录按钮点击"""
        user_id = 123456789
        button_id = "test_button"
        
        log_id = await logs_db.log_button_click(user_id, button_id)
        
        assert isinstance(log_id, int)
        assert log_id > 0
    
    @pytest.mark.asyncio
    async def test_log_user_interaction(self, logs_db):
        """测试记录用户交互"""
        interaction_data = {
            "user_id": 123456789,
            "action": "merchant_contact",
            "details": {
                "merchant_id": 1,
                "contact_type": "appointment"
            }
        }
        
        log_id = await logs_db.log_user_interaction(
            interaction_data["user_id"],
            interaction_data["action"],
            interaction_data["details"]
        )
        
        assert isinstance(log_id, int)
        assert log_id > 0
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, logs_db):
        """测试获取统计数据"""
        # 先添加一些日志记录
        await logs_db.log_button_click(123456789, "test_button_1")
        await logs_db.log_button_click(123456789, "test_button_2")
        await logs_db.log_user_interaction(123456789, "test_action", {"key": "value"})
        
        # 获取今天的统计
        stats = await logs_db.get_statistics("today")
        
        assert "total_clicks" in stats
        assert "unique_users" in stats
        assert "button_clicks" in stats
        assert stats["total_clicks"] >= 2
    
    @pytest.mark.asyncio
    async def test_get_button_click_stats(self, logs_db):
        """测试获取按钮点击统计"""
        button_id = "popular_button"
        
        # 记录多次点击
        for i in range(5):
            await logs_db.log_button_click(123456789 + i, button_id)
        
        # 获取统计
        stats = await logs_db.get_button_click_stats(button_id)
        
        assert stats["click_count"] >= 5
        assert stats["unique_users"] >= 5


class TestDatabaseConnection:
    """数据库连接管理测试"""
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, temp_db):
        """测试数据库初始化"""
        db_manager = DatabaseManager(temp_db)
        
        # 测试初始化
        await db_manager.initialize()
        
        # 验证连接可用
        result = await db_manager.fetch_one("SELECT 1")
        assert result == (1,)
        
        await db_manager.close()
    
    @pytest.mark.asyncio
    async def test_execute_query(self, db_manager):
        """测试执行查询"""
        # 测试插入
        await db_manager.execute_query(
            "INSERT INTO merchants (chat_id, name, region) VALUES (?, ?, ?)",
            (999888777, "测试商家", "测试地区")
        )
        
        # 测试查询
        result = await db_manager.fetch_one(
            "SELECT name FROM merchants WHERE chat_id = ?",
            (999888777,)
        )
        
        assert result is not None
        assert result[0] == "测试商家"
    
    @pytest.mark.asyncio
    async def test_fetch_all(self, db_manager):
        """测试批量查询"""
        # 插入多条数据
        test_merchants = [
            (999888001, "商家1", "地区1"),
            (999888002, "商家2", "地区2"),
            (999888003, "商家3", "地区3")
        ]
        
        for chat_id, name, region in test_merchants:
            await db_manager.execute_query(
                "INSERT INTO merchants (chat_id, name, region) VALUES (?, ?, ?)",
                (chat_id, name, region)
            )
        
        # 批量查询
        results = await db_manager.fetch_all(
            "SELECT name FROM merchants WHERE chat_id BETWEEN ? AND ?",
            (999888001, 999888003)
        )
        
        assert len(results) >= 3
        names = [r[0] for r in results]
        assert "商家1" in names
        assert "商家2" in names
        assert "商家3" in names
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """测试连接错误处理"""
        # 使用无效路径测试错误处理
        invalid_db_manager = DatabaseManager("/invalid/path/database.db")
        
        with pytest.raises(Exception):
            await invalid_db_manager.initialize()


class TestDatabaseIntegration:
    """数据库集成测试"""
    
    @pytest.mark.asyncio
    async def test_merchant_order_relationship(self, db_manager, sample_merchant_data, sample_order_data):
        """测试商家和订单的关联关系"""
        merchants_db = MerchantsDatabase()
        orders_db = OrdersDatabase()
        
        # 创建商家
        merchant_id = await merchants_db.create_merchant(sample_merchant_data)
        
        # 创建订单
        sample_order_data["merchant_id"] = merchant_id
        order_id = await orders_db.create_order(sample_order_data)
        
        # 验证关联查询
        orders = await orders_db.get_orders_by_merchant(merchant_id)
        assert len(orders) == 1
        assert orders[0]["id"] == order_id
        
        # 删除商家后，相关订单应该能正确处理
        await merchants_db.delete_merchant(merchant_id)
        
        # 订单仍然存在但merchant_id引用已无效
        order = await orders_db.get_order(order_id)
        assert order is not None
    
    @pytest.mark.asyncio
    async def test_binding_merchant_workflow(self, db_manager, sample_merchant_data):
        """测试绑定码和商家注册工作流"""
        merchants_db = MerchantsDatabase()
        bindings_db = BindingsDatabase()
        
        # 1. 生成绑定码
        code = await bindings_db.generate_binding_code()
        assert await bindings_db.validate_binding_code(code)
        
        # 2. 创建商家
        merchant_id = await merchants_db.create_merchant(sample_merchant_data)
        
        # 3. 使用绑定码
        success = await bindings_db.use_binding_code(code, merchant_id)
        assert success
        
        # 4. 验证绑定码不能重复使用
        assert not await bindings_db.validate_binding_code(code)
        
        # 5. 验证商家存在
        merchant = await merchants_db.get_merchant(merchant_id)
        assert merchant is not None
    
    @pytest.mark.asyncio
    async def test_activity_logging_integration(self, db_manager, sample_merchant_data):
        """测试活动日志集成"""
        merchants_db = MerchantsDatabase()
        logs_db = ActivityLogsDatabase()
        
        # 创建商家
        merchant_id = await merchants_db.create_merchant(sample_merchant_data)
        
        # 记录用户交互
        user_id = 123456789
        await logs_db.log_user_interaction(
            user_id, 
            "merchant_contact", 
            {"merchant_id": merchant_id, "type": "appointment"}
        )
        
        # 记录按钮点击
        await logs_db.log_button_click(user_id, f"merchant_{merchant_id}")
        
        # 获取统计
        stats = await logs_db.get_statistics("today")
        assert stats["total_clicks"] >= 1
        assert stats["unique_users"] >= 1
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, db_manager, sample_merchant_data):
        """测试并发操作"""
        import asyncio
        
        merchants_db = MerchantsDatabase()
        
        # 并发创建多个商家
        async def create_merchant(chat_id, name):
            data = sample_merchant_data.copy()
            data["chat_id"] = chat_id
            data["name"] = name
            return await merchants_db.create_merchant(data)
        
        # 创建10个并发任务
        tasks = []
        for i in range(10):
            task = create_merchant(1000000 + i, f"并发商家{i}")
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证所有任务都成功
        successful_results = [r for r in results if isinstance(r, int)]
        assert len(successful_results) == 10
        
        # 验证数据库中确实有10个商家
        all_merchants = await merchants_db.get_all_merchants()
        assert len(all_merchants) >= 10