# -*- coding: utf-8 -*-
"""
绑定码管理器V2全面单元测试
测试覆盖：生命周期管理、状态转换、批量操作、安全性、性能
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import time

# 导入被测试的模块
from database.db_binding_codes import BindingCodesManager
from database.db_connection import DatabaseManager
import aiosqlite


@pytest.fixture
async def test_db():
    """创建测试数据库"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    db_path = temp_file.name
    
    # 创建测试数据库结构
    async with aiosqlite.connect(db_path) as db:
        # 创建绑定码表
        await db.execute('''
            CREATE TABLE binding_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                used_by_merchant_id INTEGER,
                used_at DATETIME,
                bound_telegram_username TEXT,
                bound_telegram_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建商户表（用于测试外键关系）
        await db.execute('''
            CREATE TABLE merchants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                status TEXT DEFAULT 'pending_submission',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.commit()
    
    # 设置数据库管理器使用测试数据库
    original_db_path = DatabaseManager._instance.db_path if DatabaseManager._instance else None
    
    # 创建新的数据库管理器实例用于测试
    db_manager = DatabaseManager()
    db_manager.db_path = db_path
    db_manager.connection_pool = []
    
    # 替换全局实例
    from database.db_connection import db_manager as global_db_manager
    global_db_manager.db_path = db_path
    global_db_manager.connection_pool = []
    
    yield db_path
    
    # 清理
    try:
        await global_db_manager.close_all_connections()
        os.unlink(db_path)
    except OSError:
        pass
    
    # 恢复原始数据库路径
    if original_db_path:
        global_db_manager.db_path = original_db_path


class TestBindingCodesManager:
    """绑定码管理器V2测试类"""
    
    @pytest.mark.asyncio
    async def test_generate_binding_code_success(self, test_db):
        """测试成功生成绑定码"""
        code = await BindingCodesManager.generate_binding_code()
        
        # 验证绑定码格式
        assert isinstance(code, str)
        assert len(code) == BindingCodesManager.CODE_LENGTH
        assert all(c in BindingCodesManager.CODE_CHARSET for c in code)
        
        # 验证绑定码已保存到数据库
        code_info = await BindingCodesManager.get_binding_code_info(code)
        assert code_info is not None
        assert code_info['code'] == code
        assert code_info['is_used'] is False
    
    @pytest.mark.asyncio
    async def test_generate_binding_code_custom_expiry(self, test_db):
        """测试使用自定义过期时间生成绑定码"""
        code = await BindingCodesManager.generate_binding_code(expiry_hours=48)
        
        assert isinstance(code, str)
        assert len(code) == BindingCodesManager.CODE_LENGTH
        
        # 验证绑定码信息
        code_info = await BindingCodesManager.get_binding_code_info(code)
        assert code_info is not None
    
    @pytest.mark.asyncio
    async def test_generate_unique_binding_codes(self, test_db):
        """测试生成多个不同的绑定码"""
        codes = []
        for _ in range(10):
            code = await BindingCodesManager.generate_binding_code()
            assert code not in codes, "生成了重复的绑定码"
            codes.append(code)
    
    @pytest.mark.asyncio
    async def test_check_code_exists(self, test_db):
        """测试检查绑定码是否存在"""
        # 生成一个绑定码
        code = await BindingCodesManager.generate_binding_code()
        
        # 检查存在的绑定码
        exists = await BindingCodesManager._check_code_exists(code)
        assert exists is True
        
        # 检查不存在的绑定码
        exists = await BindingCodesManager._check_code_exists("NOTEXIST")
        assert exists is False
    
    @pytest.mark.asyncio
    async def test_get_binding_code_info_valid(self, test_db):
        """测试获取有效绑定码信息"""
        code = await BindingCodesManager.generate_binding_code()
        
        info = await BindingCodesManager.get_binding_code_info(code)
        
        assert info is not None
        assert info['code'] == code
        assert info['is_used'] is False
        assert info['used_by_merchant_id'] is None
    
    @pytest.mark.asyncio
    async def test_get_binding_code_info_invalid(self, test_db):
        """测试获取无效绑定码信息"""
        info = await BindingCodesManager.get_binding_code_info("INVALID")
        assert info is None
    
    @pytest.mark.asyncio
    async def test_get_binding_code_info_case_insensitive(self, test_db):
        """测试绑定码查询不区分大小写"""
        code = await BindingCodesManager.generate_binding_code()
        
        # 测试小写查询
        info = await BindingCodesManager.get_binding_code_info(code.lower())
        assert info is not None
        assert info['code'] == code
        
        # 测试混合大小写查询
        mixed_case = ''.join([c.lower() if i % 2 else c for i, c in enumerate(code)])
        info = await BindingCodesManager.get_binding_code_info(mixed_case)
        assert info is not None
        assert info['code'] == code
    
    @pytest.mark.asyncio
    async def test_use_binding_code_success(self, test_db):
        """测试成功使用绑定码"""
        code = await BindingCodesManager.generate_binding_code()
        
        # 创建测试商户
        from database.db_connection import db_manager
        merchant_query = """
            INSERT INTO merchants (chat_id, name, status)
            VALUES (?, ?, ?)
        """
        merchant_id = await db_manager.get_last_insert_id(
            merchant_query, (123456789, "测试商户", "pending_submission")
        )
        
        # 使用绑定码
        result = await BindingCodesManager.use_binding_code(code, merchant_id)
        assert result is True
        
        # 验证绑定码已被标记为使用
        info = await BindingCodesManager.get_binding_code_info(code)
        assert info['is_used'] is True
        assert info['used_by_merchant_id'] == merchant_id
        assert info['used_at'] is not None
    
    @pytest.mark.asyncio
    async def test_use_binding_code_already_used(self, test_db):
        """测试使用已使用的绑定码"""
        code = await BindingCodesManager.generate_binding_code()
        
        # 创建测试商户
        from database.db_connection import db_manager
        merchant_query = """
            INSERT INTO merchants (chat_id, name, status)
            VALUES (?, ?, ?)
        """
        merchant_id1 = await db_manager.get_last_insert_id(
            merchant_query, (123456789, "商户1", "pending_submission")
        )
        merchant_id2 = await db_manager.get_last_insert_id(
            merchant_query, (987654321, "商户2", "pending_submission")
        )
        
        # 第一次使用绑定码
        result1 = await BindingCodesManager.use_binding_code(code, merchant_id1)
        assert result1 is True
        
        # 第二次使用同一绑定码（应该失败）
        result2 = await BindingCodesManager.use_binding_code(code, merchant_id2)
        assert result2 is False
    
    @pytest.mark.asyncio
    async def test_use_binding_code_nonexistent(self, test_db):
        """测试使用不存在的绑定码"""
        from database.db_connection import db_manager
        merchant_query = """
            INSERT INTO merchants (chat_id, name, status)
            VALUES (?, ?, ?)
        """
        merchant_id = await db_manager.get_last_insert_id(
            merchant_query, (123456789, "测试商户", "pending_submission")
        )
        
        result = await BindingCodesManager.use_binding_code("NOTEXIST", merchant_id)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_and_use_binding_code_success(self, test_db):
        """测试完整的绑定码验证和使用流程"""
        code = await BindingCodesManager.generate_binding_code()
        user_id = 123456789
        
        # 模拟商户管理器
        with patch('database.db_binding_codes_v2.MerchantManagerV2') as mock_merchant:
            mock_merchant.get_merchant_by_chat_id.return_value = None
            mock_merchant.create_merchant.return_value = 1
            mock_merchant.delete_merchant.return_value = True
            
            result = await BindingCodesManager.validate_and_use_binding_code(code, user_id)
            
            assert result['success'] is True
            assert result['merchant_id'] == 1
            assert '绑定成功' in result['message']
    
    @pytest.mark.asyncio
    async def test_validate_and_use_binding_code_empty_code(self, test_db):
        """测试使用空绑定码"""
        result = await BindingCodesManager.validate_and_use_binding_code("", 123456789)
        
        assert result['success'] is False
        assert result['merchant_id'] is None
        assert '绑定码不能为空' in result['message']
    
    @pytest.mark.asyncio
    async def test_validate_and_use_binding_code_invalid(self, test_db):
        """测试使用无效绑定码"""
        result = await BindingCodesManager.validate_and_use_binding_code("INVALID", 123456789)
        
        assert result['success'] is False
        assert result['merchant_id'] is None
        assert '绑定码无效或已被使用' in result['message']
    
    @pytest.mark.asyncio
    async def test_validate_and_use_binding_code_user_already_bound(self, test_db):
        """测试已绑定用户尝试再次绑定"""
        code = await BindingCodesManager.generate_binding_code()
        user_id = 123456789
        
        # 模拟用户已绑定
        with patch('database.db_binding_codes_v2.MerchantManagerV2') as mock_merchant:
            mock_merchant.get_merchant_by_chat_id.return_value = {'id': 999}
            
            result = await BindingCodesManager.validate_and_use_binding_code(code, user_id)
            
            assert result['success'] is False
            assert result['merchant_id'] is None
            assert '您的账号已绑定到商户ID: 999' in result['message']
    
    @pytest.mark.asyncio
    async def test_get_all_binding_codes(self, test_db):
        """测试获取所有绑定码列表"""
        # 生成测试数据
        codes = []
        for i in range(5):
            code = await BindingCodesManager.generate_binding_code()
            codes.append(code)
        
        # 使用其中一些绑定码
        from database.db_connection import db_manager
        merchant_query = """
            INSERT INTO merchants (chat_id, name, status)
            VALUES (?, ?, ?)
        """
        merchant_id = await db_manager.get_last_insert_id(
            merchant_query, (123456789, "测试商户", "pending_submission")
        )
        
        await BindingCodesManager.use_binding_code(codes[0], merchant_id)
        await BindingCodesManager.use_binding_code(codes[1], merchant_id)
        
        # 测试获取所有绑定码
        all_codes = await BindingCodesManager.get_all_binding_codes()
        assert len(all_codes) == 5
        
        # 测试只获取未使用的绑定码
        unused_codes = await BindingCodesManager.get_all_binding_codes(include_used=False)
        assert len(unused_codes) == 3
        
        # 测试限制返回数量
        limited_codes = await BindingCodesManager.get_all_binding_codes(limit=2)
        assert len(limited_codes) == 2
    
    @pytest.mark.asyncio
    async def test_get_binding_code_statistics(self, test_db):
        """测试获取绑定码统计信息"""
        # 生成测试数据
        codes = []
        for i in range(10):
            code = await BindingCodesManager.generate_binding_code()
            codes.append(code)
        
        # 使用部分绑定码
        from database.db_connection import db_manager
        merchant_query = """
            INSERT INTO merchants (chat_id, name, status)
            VALUES (?, ?, ?)
        """
        merchant_id = await db_manager.get_last_insert_id(
            merchant_query, (123456789, "测试商户", "pending_submission")
        )
        
        for i in range(0, 6):
            await BindingCodesManager.use_binding_code(codes[i], merchant_id)
        
        stats = await BindingCodesManager.get_binding_code_statistics()
        
        assert stats['total_codes'] == 10
        assert stats['used_codes'] == 6
        assert stats['valid_codes'] == 4
        assert stats['usage_rate'] == 60.0
        assert 'generated_at' in stats
    
    @pytest.mark.asyncio
    async def test_delete_binding_code(self, test_db):
        """测试删除绑定码"""
        code = await BindingCodesManager.generate_binding_code()
        
        # 确认绑定码存在
        info = await BindingCodesManager.get_binding_code_info(code)
        assert info is not None
        
        # 删除绑定码
        result = await BindingCodesManager.delete_binding_code(code)
        assert result is True
        
        # 确认绑定码已删除
        info = await BindingCodesManager.get_binding_code_info(code)
        assert info is None
        
        # 尝试删除不存在的绑定码
        result = await BindingCodesManager.delete_binding_code("NOTEXIST")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_merchant_binding_codes(self, test_db):
        """测试获取商户使用的绑定码"""
        # 创建商户
        from database.db_connection import db_manager
        merchant_query = """
            INSERT INTO merchants (chat_id, name, status)
            VALUES (?, ?, ?)
        """
        merchant_id = await db_manager.get_last_insert_id(
            merchant_query, (123456789, "测试商户", "pending_submission")
        )
        
        # 生成并使用多个绑定码
        used_codes = []
        for i in range(3):
            code = await BindingCodesManager.generate_binding_code()
            await BindingCodesManager.use_binding_code(code, merchant_id)
            used_codes.append(code)
        
        # 获取商户的绑定码
        merchant_codes = await BindingCodesManager.get_merchant_binding_codes(merchant_id)
        
        assert len(merchant_codes) == 3
        for code_info in merchant_codes:
            assert code_info['used_by_merchant_id'] == merchant_id
            assert code_info['is_used'] is True
    
    @pytest.mark.asyncio
    async def test_update_binding_code_merchant(self, test_db):
        """测试更新绑定码的商户ID"""
        code = await BindingCodesManager.generate_binding_code()
        
        # 创建两个商户
        from database.db_connection import db_manager
        merchant_query = """
            INSERT INTO merchants (chat_id, name, status)
            VALUES (?, ?, ?)
        """
        merchant_id1 = await db_manager.get_last_insert_id(
            merchant_query, (123456789, "商户1", "pending_submission")
        )
        merchant_id2 = await db_manager.get_last_insert_id(
            merchant_query, (987654321, "商户2", "pending_submission")
        )
        
        # 使用绑定码
        await BindingCodesManager.use_binding_code(code, merchant_id1)
        
        # 更新商户ID
        result = await BindingCodesManager.update_binding_code_merchant(code, merchant_id2)
        assert result is True
        
        # 验证更新
        info = await BindingCodesManager.get_binding_code_info(code)
        assert info['used_by_merchant_id'] == merchant_id2
    
    @pytest.mark.asyncio
    async def test_update_binding_code_merchant_invalid(self, test_db):
        """测试更新无效绑定码的商户ID"""
        with pytest.raises(ValueError, match="绑定码不存在"):
            await BindingCodesManager.update_binding_code_merchant("NOTEXIST", 1)
    
    @pytest.mark.asyncio
    async def test_update_binding_code_merchant_unused(self, test_db):
        """测试更新未使用绑定码的商户ID"""
        code = await BindingCodesManager.generate_binding_code()
        
        with pytest.raises(ValueError, match="绑定码尚未使用"):
            await BindingCodesManager.update_binding_code_merchant(code, 1)
    
    @pytest.mark.asyncio
    async def test_mark_code_as_used(self, test_db):
        """测试标记绑定码为已使用（增强版本）"""
        code = await BindingCodesManager.generate_binding_code()
        
        # 创建商户
        from database.db_connection import db_manager
        merchant_query = """
            INSERT INTO merchants (chat_id, name, status)
            VALUES (?, ?, ?)
        """
        merchant_id = await db_manager.get_last_insert_id(
            merchant_query, (123456789, "测试商户", "pending_submission")
        )
        
        # 标记为使用
        await BindingCodesManager.mark_code_as_used(
            code, merchant_id, "testuser", "Test User"
        )
        
        # 验证标记结果
        info = await BindingCodesManager.get_binding_code_info(code)
        assert info['is_used'] is True
        assert info['used_by_merchant_id'] == merchant_id
        assert info['bound_telegram_username'] == "testuser"
        assert info['bound_telegram_name'] == "Test User"
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_codes(self, test_db):
        """测试清理过期绑定码（V2版本不支持）"""
        # V2版本暂不支持过期机制
        result = await BindingCodesManager.cleanup_expired_codes()
        assert result == 0
    
    @pytest.mark.asyncio
    async def test_extend_binding_code_expiry(self, test_db):
        """测试延长绑定码有效期（V2版本不支持）"""
        code = await BindingCodesManager.generate_binding_code()
        
        # V2版本暂不支持有效期延长
        result = await BindingCodesManager.extend_binding_code_expiry(code, 24)
        assert result is False


class TestBindingCodesSecurity:
    """绑定码安全性测试"""
    
    @pytest.mark.asyncio
    async def test_prevent_duplicate_binding(self, test_db):
        """测试防止重复绑定"""
        code1 = await BindingCodesManager.generate_binding_code()
        code2 = await BindingCodesManager.generate_binding_code()
        user_id = 123456789
        
        with patch('database.db_binding_codes_v2.MerchantManagerV2') as mock_merchant:
            # 第一次绑定成功
            mock_merchant.get_merchant_by_chat_id.return_value = None
            mock_merchant.create_merchant.return_value = 1
            mock_merchant.delete_merchant.return_value = True
            
            result1 = await BindingCodesManager.validate_and_use_binding_code(code1, user_id)
            assert result1['success'] is True
            
            # 第二次绑定应该失败（用户已绑定）
            mock_merchant.get_merchant_by_chat_id.return_value = {'id': 1}
            
            result2 = await BindingCodesManager.validate_and_use_binding_code(code2, user_id)
            assert result2['success'] is False
            assert '您的账号已绑定到商户ID' in result2['message']
    
    @pytest.mark.asyncio
    async def test_concurrent_code_usage_protection(self, test_db):
        """测试并发使用绑定码的保护机制"""
        code = await BindingCodesManager.generate_binding_code()
        user_id1 = 123456789
        user_id2 = 987654321
        
        with patch('database.db_binding_codes_v2.MerchantManagerV2') as mock_merchant:
            mock_merchant.get_merchant_by_chat_id.return_value = None
            mock_merchant.create_merchant.side_effect = [1, 2]
            mock_merchant.delete_merchant.return_value = True
            
            # 模拟两个用户同时尝试使用同一绑定码
            tasks = [
                BindingCodesManager.validate_and_use_binding_code(code, user_id1),
                BindingCodesManager.validate_and_use_binding_code(code, user_id2)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 只有一个应该成功
            success_count = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
            assert success_count == 1
    
    @pytest.mark.asyncio
    async def test_sql_injection_protection(self, test_db):
        """测试SQL注入防护"""
        # 尝试使用包含SQL注入的绑定码
        malicious_code = "ABC'; DROP TABLE binding_codes; --"
        
        result = await BindingCodesManager.validate_and_use_binding_code(malicious_code, 123456789)
        
        # 应该安全处理，不会导致SQL注入
        assert result['success'] is False
        assert '绑定码无效或已被使用' in result['message']
        
        # 验证表仍然存在
        stats = await BindingCodesManager.get_binding_code_statistics()
        assert isinstance(stats, dict)


class TestBindingCodesPerformance:
    """绑定码性能测试"""
    
    @pytest.mark.asyncio
    async def test_bulk_generation_performance(self, test_db):
        """测试批量生成绑定码性能"""
        start_time = time.time()
        
        # 批量生成100个绑定码
        tasks = []
        for _ in range(100):
            task = BindingCodesManager.generate_binding_code()
            tasks.append(task)
        
        codes = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 验证生成结果
        assert len(codes) == 100
        assert len(set(codes)) == 100  # 确保都是唯一的
        
        # 性能断言（应该在合理时间内完成）
        assert duration < 10.0, f"批量生成耗时过长: {duration}秒"
        
        print(f"批量生成100个绑定码耗时: {duration:.3f}秒")
    
    @pytest.mark.asyncio
    async def test_concurrent_usage_performance(self, test_db):
        """测试并发使用绑定码性能"""
        # 预生成绑定码
        codes = []
        for i in range(50):
            code = await BindingCodesManager.generate_binding_code()
            codes.append(code)
        
        start_time = time.time()
        
        # 并发使用绑定码
        with patch('database.db_binding_codes_v2.MerchantManagerV2') as mock_merchant:
            mock_merchant.get_merchant_by_chat_id.return_value = None
            mock_merchant.create_merchant.side_effect = range(1, 51)
            mock_merchant.delete_merchant.return_value = True
            
            tasks = []
            for i, code in enumerate(codes):
                task = BindingCodesManager.validate_and_use_binding_code(code, 123456789 + i)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 验证结果
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
        assert success_count == 50
        
        # 性能断言
        assert duration < 15.0, f"并发使用耗时过长: {duration}秒"
        
        print(f"并发使用50个绑定码耗时: {duration:.3f}秒")
    
    @pytest.mark.asyncio
    async def test_query_efficiency(self, test_db):
        """测试查询效率"""
        # 生成大量测试数据
        codes = []
        for i in range(1000):
            code = await BindingCodesManager.generate_binding_code()
            codes.append(code)
        
        start_time = time.time()
        
        # 执行多种查询操作
        for _ in range(100):
            # 随机查询绑定码信息
            import random
            random_code = random.choice(codes)
            info = await BindingCodesManager.get_binding_code_info(random_code)
            assert info is not None
        
        # 查询统计信息
        stats = await BindingCodesManager.get_binding_code_statistics()
        assert stats['total_codes'] == 1000
        
        # 查询所有绑定码
        all_codes = await BindingCodesManager.get_all_binding_codes(limit=100)
        assert len(all_codes) == 100
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 性能断言
        assert duration < 5.0, f"查询操作耗时过长: {duration}秒"
        
        print(f"100次随机查询+统计+列表查询耗时: {duration:.3f}秒")


class TestBindingCodesRobustness:
    """绑定码健壮性测试"""
    
    @pytest.mark.asyncio
    async def test_database_connection_failure_handling(self, test_db):
        """测试数据库连接失败处理"""
        with patch('database.db_connection.db_manager.execute_query', side_effect=Exception("连接失败")):
            with pytest.raises(Exception):
                await BindingCodesManager.generate_binding_code()
    
    @pytest.mark.asyncio
    async def test_invalid_input_handling(self, test_db):
        """测试无效输入处理"""
        # 测试None输入
        result = await BindingCodesManager.validate_and_use_binding_code(None, 123456789)
        assert result['success'] is False
        
        # 测试空字符串
        result = await BindingCodesManager.validate_and_use_binding_code("   ", 123456789)
        assert result['success'] is False
        
        # 测试特殊字符
        result = await BindingCodesManager.validate_and_use_binding_code("ABC@#$", 123456789)
        assert result['success'] is False
    
    @pytest.mark.asyncio
    async def test_large_dataset_handling(self, test_db):
        """测试大数据集处理"""
        # 生成大量绑定码
        codes = []
        batch_size = 100
        
        for batch in range(10):  # 生成1000个绑定码
            batch_tasks = []
            for _ in range(batch_size):
                task = BindingCodesManager.generate_binding_code()
                batch_tasks.append(task)
            
            batch_codes = await asyncio.gather(*batch_tasks)
            codes.extend(batch_codes)
        
        assert len(codes) == 1000
        assert len(set(codes)) == 1000  # 确保唯一性
        
        # 测试大数据集查询
        stats = await BindingCodesManager.get_binding_code_statistics()
        assert stats['total_codes'] == 1000
        
        # 测试分页查询
        page1 = await BindingCodesManager.get_all_binding_codes(limit=100)
        assert len(page1) == 100


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])