# -*- coding: utf-8 -*-
"""
MerchantManager 全面单元测试

测试覆盖：
1. 基础功能测试：创建、查询、更新商户
2. 永久ID系统测试：永久ID唯一性、TG账号绑定、换绑功能
3. 媒体文件测试：关联、查询、删除
4. 地区搜索测试：按地区搜索、分页查询
5. 数据完整性测试：必填字段验证、类型验证、边界条件
"""

import pytest
import json
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

import aiosqlite

# 导入被测试的模块
from database.db_merchants import MerchantManager
from database.db_connection import DatabaseManager


class TestDatabaseFixture:
    """测试数据库fixture类"""
    
    @pytest.fixture
    async def temp_test_db(self):
        """创建临时测试数据库"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        db_path = temp_file.name
        
        # 初始化测试数据库结构
        async with aiosqlite.connect(db_path) as db:
            # 设置行工厂
            db.row_factory = aiosqlite.Row
            
            # 创建完整的表结构
            await db.execute('''
                CREATE TABLE merchants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER UNIQUE NOT NULL,
                    name TEXT NOT NULL DEFAULT '待完善',
                    region TEXT,
                    category TEXT,
                    contact_info TEXT,
                    profile_data JSON,
                    status TEXT DEFAULT 'pending',
                    merchant_type TEXT DEFAULT 'teacher',
                    province_id INTEGER,
                    region_id INTEGER,
                    p_price REAL,
                    pp_price REAL,
                    custom_description TEXT,
                    user_info TEXT,
                    channel_link TEXT,
                    show_in_region_search BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建provinces表
            await db.execute('''
                CREATE TABLE provinces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # 创建regions表
            await db.execute('''
                CREATE TABLE regions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    province_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (province_id) REFERENCES provinces(id),
                    UNIQUE(province_id, name)
                )
            ''')
            
            # 创建media表（用于媒体文件测试）
            await db.execute('''
                CREATE TABLE media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merchant_id INTEGER NOT NULL,
                    telegram_file_id TEXT NOT NULL,
                    file_type TEXT,
                    file_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE
                )
            ''')
            
            # 创建activity_logs表
            await db.execute('''
                CREATE TABLE activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT NOT NULL,
                    details JSON,
                    merchant_id INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建orders表（用于统计测试）
            await db.execute('''
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    merchant_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
                )
            ''')
            
            # 插入测试省份和地区数据
            await db.execute("INSERT INTO provinces (id, name) VALUES (1, '北京市')")
            await db.execute("INSERT INTO provinces (id, name) VALUES (2, '上海市')")
            await db.execute("INSERT INTO provinces (id, name) VALUES (3, '广东省')")
            
            await db.execute("INSERT INTO regions (id, province_id, name) VALUES (1, 1, '朝阳区')")
            await db.execute("INSERT INTO regions (id, province_id, name) VALUES (2, 1, '海淀区')")
            await db.execute("INSERT INTO regions (id, province_id, name) VALUES (3, 2, '浦东新区')")
            await db.execute("INSERT INTO regions (id, province_id, name) VALUES (4, 3, '天河区')")
            
            await db.commit()
        
        yield db_path
        
        # 清理临时文件
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    async def mock_db_manager(self, temp_test_db):
        """创建模拟数据库管理器"""
        # 创建实际的数据库连接用于测试
        real_conn = await aiosqlite.connect(temp_test_db)
        real_conn.row_factory = aiosqlite.Row
        
        # 创建模拟管理器对象
        mock_manager = MagicMock()
        
        # 设置真实的数据库连接用于测试
        mock_manager._real_conn = real_conn
        
        # 重新定义方法以使用真实连接
        async def real_get_last_insert_id(query, params):
            cursor = await real_conn.execute(query, params)
            await real_conn.commit()
            return cursor.lastrowid
        
        async def real_fetch_one(query, params=None):
            if params:
                cursor = await real_conn.execute(query, params)
            else:
                cursor = await real_conn.execute(query)
            return await cursor.fetchone()
        
        async def real_fetch_all(query, params=None):
            if params:
                cursor = await real_conn.execute(query, params)
            else:
                cursor = await real_conn.execute(query)
            return await cursor.fetchall()
        
        async def real_execute_query(query, params=None):
            if params:
                cursor = await real_conn.execute(query, params)
            else:
                cursor = await real_conn.execute(query)
            await real_conn.commit()
            return cursor.rowcount
        
        mock_manager.get_last_insert_id = AsyncMock(side_effect=real_get_last_insert_id)
        mock_manager.fetch_one = AsyncMock(side_effect=real_fetch_one)
        mock_manager.fetch_all = AsyncMock(side_effect=real_fetch_all)
        mock_manager.execute_query = AsyncMock(side_effect=real_execute_query)
        
        # 使用patch替换全局的db_manager
        with patch('database.db_merchants_v2.db_manager', mock_manager):
            yield mock_manager
        
        await real_conn.close()


class TestMerchantManagerBasic(TestDatabaseFixture):
    """基础功能测试"""
    
    @pytest.mark.asyncio
    async def test_create_merchant_basic(self, mock_db_manager):
        """测试基础商户创建"""
        merchant_data = {
            'chat_id': 123456789,
            'name': '测试商户',
            'merchant_type': 'teacher',
            'status': 'pending'
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        assert merchant_id is not None
        assert isinstance(merchant_id, int)
        assert merchant_id > 0
    
    @pytest.mark.asyncio
    async def test_create_merchant_duplicate_chat_id(self, mock_db_manager):
        """测试重复chat_id的处理"""
        merchant_data = {
            'chat_id': 123456789,
            'name': '测试商户1',
        }
        
        # 第一次创建
        merchant_id_1 = await MerchantManager.create_merchant(merchant_data)
        assert merchant_id_1 is not None
        
        # 第二次创建相同chat_id
        merchant_data['name'] = '测试商户2'
        merchant_id_2 = await MerchantManager.create_merchant(merchant_data)
        
        # 应该返回已存在的商户ID
        assert merchant_id_2 == merchant_id_1
    
    @pytest.mark.asyncio
    async def test_create_merchant_missing_chat_id(self, mock_db_manager):
        """测试缺少必需字段chat_id"""
        merchant_data = {
            'name': '测试商户',
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        assert merchant_id is None
    
    @pytest.mark.asyncio
    async def test_get_merchant_by_id(self, mock_db_manager):
        """测试根据ID获取商户"""
        # 先创建商户
        merchant_data = {
            'chat_id': 123456789,
            'name': '测试商户',
            'region': '北京',
            'category': '教育培训',
            'contact_info': '微信：test123',
            'profile_data': {'test': 'data'},
            'province_id': 1,
            'region_id': 1
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 获取商户信息
        merchant = await MerchantManager.get_merchant(merchant_id)
        
        assert merchant is not None
        assert merchant['id'] == merchant_id
        assert merchant['chat_id'] == 123456789
        assert merchant['name'] == '测试商户'
        assert merchant['region'] == '北京'
        assert merchant['category'] == '教育培训'
        assert merchant['contact_info'] == '微信：test123'
        assert isinstance(merchant['profile_data'], dict)
        assert merchant['profile_data']['test'] == 'data'
        assert merchant['province_name'] == '北京市'
        assert merchant['region_name'] == '朝阳区'
        assert merchant['region_display'] == '北京市 - 朝阳区'
    
    @pytest.mark.asyncio
    async def test_get_merchant_by_chat_id(self, mock_db_manager):
        """测试根据chat_id获取商户"""
        # 先创建商户
        chat_id = 987654321
        merchant_data = {
            'chat_id': chat_id,
            'name': '测试商户V2'
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 根据chat_id获取商户
        merchant = await MerchantManager.get_merchant_by_chat_id(chat_id)
        
        assert merchant is not None
        assert merchant['id'] == merchant_id
        assert merchant['chat_id'] == chat_id
        assert merchant['name'] == '测试商户V2'
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_merchant(self, mock_db_manager):
        """测试获取不存在的商户"""
        merchant = await MerchantManager.get_merchant(999999)
        assert merchant is None
        
        merchant = await MerchantManager.get_merchant_by_chat_id(999999999)
        assert merchant is None
    
    @pytest.mark.asyncio
    async def test_update_merchant(self, mock_db_manager):
        """测试更新商户信息"""
        # 先创建商户
        merchant_data = {
            'chat_id': 123456789,
            'name': '原始名称'
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 更新商户信息
        update_data = {
            'name': '更新后名称',
            'region': '上海',
            'category': '生活服务',
            'p_price': 100.5,
            'pp_price': 200.0,
            'profile_data': {'updated': True}
        }
        
        success = await MerchantManager.update_merchant(merchant_id, update_data)
        assert success
        
        # 验证更新结果
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['name'] == '更新后名称'
        assert merchant['region'] == '上海'
        assert merchant['category'] == '生活服务'
        assert merchant['p_price'] == 100.5
        assert merchant['pp_price'] == 200.0
        assert merchant['profile_data']['updated'] == True
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_merchant(self, mock_db_manager):
        """测试更新不存在的商户"""
        success = await MerchantManager.update_merchant(999999, {'name': '测试'})
        assert not success


class TestMerchantManagerStatus(TestDatabaseFixture):
    """状态管理测试"""
    
    @pytest.mark.asyncio
    async def test_update_merchant_status(self, mock_db_manager):
        """测试更新商户状态"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 测试各种状态
        valid_statuses = ['active', 'inactive', 'pending']
        
        for status in valid_statuses:
            success = await MerchantManager.update_merchant_status(merchant_id, status)
            assert success
            
            merchant = await MerchantManager.get_merchant(merchant_id)
            assert merchant['status'] == status
    
    @pytest.mark.asyncio
    async def test_update_invalid_status(self, mock_db_manager):
        """测试更新无效状态"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 测试无效状态
        success = await MerchantManager.update_merchant_status(merchant_id, 'invalid_status')
        assert not success
    
    @pytest.mark.asyncio
    async def test_get_merchants_by_status(self, mock_db_manager):
        """测试按状态查询商户"""
        # 创建不同状态的商户
        merchants_data = [
            {'chat_id': 111, 'name': '活跃商户1', 'status': 'active'},
            {'chat_id': 222, 'name': '活跃商户2', 'status': 'active'},
            {'chat_id': 333, 'name': '待审核商户', 'status': 'pending'},
            {'chat_id': 444, 'name': '非活跃商户', 'status': 'inactive'},
        ]
        
        for data in merchants_data:
            await MerchantManager.create_merchant(data)
        
        # 查询活跃商户
        active_merchants = await MerchantManager.get_merchants(status='active')
        assert len(active_merchants) == 2
        assert all(m['status'] == 'active' for m in active_merchants)
        
        # 查询待审核商户
        pending_merchants = await MerchantManager.get_merchants(status='pending')
        assert len(pending_merchants) == 1
        assert pending_merchants[0]['status'] == 'pending'


class TestMerchantManagerSearch(TestDatabaseFixture):
    """搜索功能测试"""
    
    @pytest.mark.asyncio
    async def test_get_merchants_with_search(self, mock_db_manager):
        """测试搜索商户"""
        # 创建测试商户
        merchants_data = [
            {'chat_id': 111, 'name': '北京教育培训机构'},
            {'chat_id': 222, 'name': '上海美容院'},
            {'chat_id': 333, 'name': '广州健身中心'},
            {'chat_id': 444, 'name': '深圳教育咨询'},
        ]
        
        merchant_ids = []
        for data in merchants_data:
            merchant_id = await MerchantManager.create_merchant(data)
            merchant_ids.append(merchant_id)
        
        # 按名称搜索
        results = await MerchantManager.get_merchants(search='教育')
        assert len(results) == 2
        assert all('教育' in m['name'] for m in results)
        
        # 按ID精确搜索
        results = await MerchantManager.get_merchants(search=str(merchant_ids[0]))
        assert len(results) == 1
        assert results[0]['id'] == merchant_ids[0]
    
    @pytest.mark.asyncio
    async def test_search_merchants(self, mock_db_manager):
        """测试高级搜索功能"""
        # 创建测试商户
        merchants_data = [
            {
                'chat_id': 111, 
                'name': '专业英语培训', 
                'custom_description': '提供专业的英语教学服务',
                'region': '北京',
                'category': '教育'
            },
            {
                'chat_id': 222, 
                'name': '美容美发沙龙', 
                'custom_description': '专业美容美发服务',
                'region': '上海',
                'category': '美容'
            }
        ]
        
        for data in merchants_data:
            await MerchantManager.create_merchant(data)
        
        # 在名称中搜索
        results = await MerchantManager.search_merchants('英语')
        assert len(results) == 1
        assert '英语' in results[0]['name']
        
        # 在描述中搜索
        results = await MerchantManager.search_merchants('专业')
        assert len(results) == 2  # 两个商户的描述都包含"专业"
        
        # 按状态过滤搜索
        results = await MerchantManager.search_merchants('专业', status_filter='pending')
        assert len(results) == 2  # 默认状态是pending
    
    @pytest.mark.asyncio
    async def test_get_merchants_by_region(self, mock_db_manager):
        """测试按地区查询商户"""
        # 创建不同地区的商户
        merchants_data = [
            {'chat_id': 111, 'name': '北京商户1', 'region_id': 1},  # 朝阳区
            {'chat_id': 222, 'name': '北京商户2', 'region_id': 2},  # 海淀区
            {'chat_id': 333, 'name': '上海商户1', 'region_id': 3},  # 浦东新区
        ]
        
        for data in merchants_data:
            await MerchantManager.create_merchant(data)
        
        # 按朝阳区查询
        results = await MerchantManager.get_merchants(region_id=1)
        assert len(results) == 1
        assert results[0]['region_name'] == '朝阳区'
        
        # 按海淀区查询
        results = await MerchantManager.get_merchants(region_id=2)
        assert len(results) == 1
        assert results[0]['region_name'] == '海淀区'
    
    @pytest.mark.asyncio
    async def test_get_merchants_pagination(self, mock_db_manager):
        """测试分页查询"""
        # 创建10个商户
        for i in range(10):
            merchant_data = {
                'chat_id': 100000 + i,
                'name': f'测试商户{i:02d}'
            }
            await MerchantManager.create_merchant(merchant_data)
        
        # 测试第一页
        page1 = await MerchantManager.get_merchants(limit=3, offset=0)
        assert len(page1) == 3
        
        # 测试第二页
        page2 = await MerchantManager.get_merchants(limit=3, offset=3)
        assert len(page2) == 3
        
        # 确保没有重复
        page1_ids = {m['id'] for m in page1}
        page2_ids = {m['id'] for m in page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestMerchantManagerStatistics(TestDatabaseFixture):
    """统计功能测试"""
    
    @pytest.mark.asyncio
    async def test_get_merchant_statistics(self, mock_db_manager):
        """测试获取商户统计信息"""
        # 创建不同类型和状态的商户
        merchants_data = [
            {'chat_id': 111, 'name': '教师1', 'merchant_type': 'teacher', 'status': 'active', 'province_id': 1, 'region_id': 1},
            {'chat_id': 222, 'name': '教师2', 'merchant_type': 'teacher', 'status': 'pending', 'province_id': 1, 'region_id': 2},
            {'chat_id': 333, 'name': '商户1', 'merchant_type': 'business', 'status': 'active', 'province_id': 2, 'region_id': 3},
            {'chat_id': 444, 'name': '商户2', 'merchant_type': 'business', 'status': 'inactive', 'province_id': 3, 'region_id': 4},
        ]
        
        for data in merchants_data:
            await MerchantManager.create_merchant(data)
        
        # 获取统计信息
        stats = await MerchantManager.get_merchant_statistics()
        
        assert stats['total_merchants'] == 4
        assert stats['by_status']['active'] == 2
        assert stats['by_status']['pending'] == 1
        assert stats['by_status']['inactive'] == 1
        assert stats['by_type']['teacher'] == 2
        assert stats['by_type']['business'] == 2
        assert stats['by_province']['北京市'] == 2
        assert stats['by_province']['上海市'] == 1
        assert stats['by_province']['广东省'] == 1
        assert stats['by_region']['朝阳区'] == 1
        assert stats['by_region']['海淀区'] == 1
        assert stats['by_region']['浦东新区'] == 1
        assert stats['by_region']['天河区'] == 1
    
    @pytest.mark.asyncio
    async def test_get_dashboard_stats(self, mock_db_manager):
        """测试仪表板统计数据"""
        # 创建不同状态的商户
        merchants_data = [
            {'chat_id': 111, 'name': '商户1', 'status': 'active'},
            {'chat_id': 222, 'name': '商户2', 'status': 'active'},
            {'chat_id': 333, 'name': '商户3', 'status': 'pending'},
            {'chat_id': 444, 'name': '商户4', 'status': 'inactive'},
        ]
        
        for data in merchants_data:
            await MerchantManager.create_merchant(data)
        
        # 获取仪表板统计
        stats = await MerchantManager.get_dashboard_stats()
        
        assert stats['total_merchants'] == 4
        assert stats['active'] == 2
        assert stats['pending'] == 1
        assert stats['inactive'] == 1
        # 订单统计应该为0（没有创建订单）
        assert stats['total_orders'] == 0
        assert stats['today_orders'] == 0


class TestMerchantManagerValidation(TestDatabaseFixture):
    """数据验证测试"""
    
    @pytest.mark.asyncio
    async def test_create_blank_merchant(self, mock_db_manager):
        """测试创建空白商户档案"""
        chat_id = 123456789
        binding_code = 'TEST123456'
        
        merchant_id = await MerchantManager.create_blank_merchant(chat_id, binding_code)
        
        assert merchant_id is not None
        
        # 验证空白商户的默认值
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['chat_id'] == chat_id
        assert merchant['name'] == '待完善'
        assert merchant['status'] == 'pending'
        assert merchant['custom_description'] == '待完善'
        assert merchant['contact_info'] == '待完善'
        assert merchant['profile_data']['binding_code'] == binding_code
        assert merchant['profile_data']['registration_mode'] == 'binding_code'
    
    @pytest.mark.asyncio
    async def test_profile_data_json_handling(self, mock_db_manager):
        """测试JSON数据处理"""
        # 测试dict类型的profile_data
        merchant_data = {
            'chat_id': 123456789,
            'name': '测试商户',
            'profile_data': {
                'services': ['英语', '数学'],
                'experience': 5,
                'certifications': ['TEFL', 'CELTA']
            }
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        merchant = await MerchantManager.get_merchant(merchant_id)
        
        assert isinstance(merchant['profile_data'], dict)
        assert merchant['profile_data']['services'] == ['英语', '数学']
        assert merchant['profile_data']['experience'] == 5
        assert merchant['profile_data']['certifications'] == ['TEFL', 'CELTA']
        
        # 测试字符串类型的profile_data
        merchant_data2 = {
            'chat_id': 987654321,
            'name': '测试商户2',
            'profile_data': '{"test": "string_json"}'
        }
        
        merchant_id2 = await MerchantManager.create_merchant(merchant_data2)
        merchant2 = await MerchantManager.get_merchant(merchant_id2)
        
        assert isinstance(merchant2['profile_data'], dict)
        assert merchant2['profile_data']['test'] == 'string_json'
    
    @pytest.mark.asyncio
    async def test_invalid_field_update(self, mock_db_manager):
        """测试无效字段更新"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 尝试更新不存在的字段
        update_data = {
            'invalid_field': '无效值',
            'another_invalid': 123
        }
        
        success = await MerchantManager.update_merchant(merchant_id, update_data)
        assert not success  # 应该失败，因为没有有效字段
        
        # 混合有效和无效字段
        update_data = {
            'name': '更新的名称',  # 有效字段
            'invalid_field': '无效值',  # 无效字段
        }
        
        success = await MerchantManager.update_merchant(merchant_id, update_data)
        assert success  # 应该成功，因为有有效字段
        
        # 验证只有有效字段被更新
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['name'] == '更新的名称'
        assert 'invalid_field' not in merchant


class TestMerchantManagerDelete(TestDatabaseFixture):
    """删除功能测试"""
    
    @pytest.mark.asyncio
    async def test_delete_merchant(self, mock_db_manager):
        """测试删除商户"""
        # 创建商户
        merchant_data = {
            'chat_id': 123456789,
            'name': '待删除商户',
            'region': '北京'
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 验证商户存在
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant is not None
        
        # 删除商户
        success = await MerchantManager.delete_merchant(merchant_id)
        assert success
        
        # 验证商户已删除
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_merchant(self, mock_db_manager):
        """测试删除不存在的商户"""
        success = await MerchantManager.delete_merchant(999999)
        assert not success


class TestMerchantManagerRegionSearch(TestDatabaseFixture):
    """地区搜索显示状态测试"""
    
    @pytest.mark.asyncio
    async def test_toggle_region_search_status(self, mock_db_manager):
        """测试切换地区搜索显示状态"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 获取初始状态（默认为1）
        merchant = await MerchantManager.get_merchant(merchant_id)
        initial_status = merchant['show_in_region_search']
        assert initial_status == 1  # 默认显示
        
        # 切换状态
        success = await MerchantManager.toggle_merchant_region_search_status(merchant_id)
        assert success
        
        # 验证状态已切换
        merchant = await MerchantManager.get_merchant(merchant_id)
        new_status = merchant['show_in_region_search']
        assert new_status == 0  # 已隐藏
        
        # 再次切换
        success = await MerchantManager.toggle_merchant_region_search_status(merchant_id)
        assert success
        
        # 验证状态又切换回来
        merchant = await MerchantManager.get_merchant(merchant_id)
        final_status = merchant['show_in_region_search']
        assert final_status == 1  # 又显示了


class TestMerchantManagerPermanentID(TestDatabaseFixture):
    """永久ID系统测试"""
    
    @pytest.mark.asyncio
    async def test_permanent_id_uniqueness(self, mock_db_manager):
        """测试永久ID的唯一性"""
        # 创建多个商户，每个应该有唯一的永久ID
        merchant_data_list = []
        for i in range(5):
            merchant_data = {
                'chat_id': 100000 + i,
                'name': f'测试商户{i}'
            }
            merchant_data_list.append(merchant_data)
        
        merchant_ids = []
        for data in merchant_data_list:
            merchant_id = await MerchantManager.create_merchant(data)
            merchant_ids.append(merchant_id)
        
        # 验证所有ID都是唯一的
        assert len(set(merchant_ids)) == len(merchant_ids)
        
        # 验证所有ID都大于0
        assert all(mid > 0 for mid in merchant_ids)
        
        # 验证每个ID都能正确获取对应商户
        for i, merchant_id in enumerate(merchant_ids):
            merchant = await MerchantManager.get_merchant(merchant_id)
            assert merchant is not None
            assert merchant['chat_id'] == 100000 + i
            assert merchant['name'] == f'测试商户{i}'
    
    @pytest.mark.asyncio
    async def test_telegram_account_binding(self, mock_db_manager):
        """测试Telegram账号绑定功能"""
        # 创建商户
        original_chat_id = 123456789
        merchant_data = {
            'chat_id': original_chat_id,
            'name': '测试商户'
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 验证原始绑定
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['chat_id'] == original_chat_id
        
        # 通过chat_id能找到商户
        merchant_by_chat = await MerchantManager.get_merchant_by_chat_id(original_chat_id)
        assert merchant_by_chat is not None
        assert merchant_by_chat['id'] == merchant_id
    
    @pytest.mark.asyncio
    async def test_telegram_account_rebinding(self, mock_db_manager):
        """测试TG账号换绑功能"""
        # 创建商户
        original_chat_id = 123456789
        new_chat_id = 987654321
        
        merchant_data = {
            'chat_id': original_chat_id,
            'name': '测试商户'
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 更新到新的chat_id（模拟换绑）
        update_data = {'chat_id': new_chat_id}
        success = await MerchantManager.update_merchant(merchant_id, update_data)
        assert success
        
        # 验证新绑定
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['chat_id'] == new_chat_id
        
        # 通过新chat_id能找到商户
        merchant_by_new_chat = await MerchantManager.get_merchant_by_chat_id(new_chat_id)
        assert merchant_by_new_chat is not None
        assert merchant_by_new_chat['id'] == merchant_id
        
        # 通过旧chat_id找不到商户
        merchant_by_old_chat = await MerchantManager.get_merchant_by_chat_id(original_chat_id)
        assert merchant_by_old_chat is None
    
    @pytest.mark.asyncio
    async def test_permanent_id_persistence_across_rebinding(self, mock_db_manager):
        """测试永久ID在换绑过程中的持久性"""
        # 创建商户
        original_chat_id = 111111111
        merchant_data = {
            'chat_id': original_chat_id,
            'name': '测试持久性商户',
            'profile_data': {'重要数据': '不应该丢失'}
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 记录原始信息
        original_merchant = await MerchantManager.get_merchant(merchant_id)
        
        # 多次换绑不同的TG账号
        chat_ids = [222222222, 333333333, 444444444]
        
        for new_chat_id in chat_ids:
            # 换绑到新账号
            success = await MerchantManager.update_merchant(merchant_id, {'chat_id': new_chat_id})
            assert success
            
            # 验证永久ID不变，数据完整
            merchant = await MerchantManager.get_merchant(merchant_id)
            assert merchant['id'] == merchant_id  # 永久ID不变
            assert merchant['chat_id'] == new_chat_id  # TG ID已更新
            assert merchant['name'] == original_merchant['name']  # 其他数据保持
            assert merchant['profile_data'] == original_merchant['profile_data']
            
            # 通过新chat_id能找到
            merchant_by_chat = await MerchantManager.get_merchant_by_chat_id(new_chat_id)
            assert merchant_by_chat['id'] == merchant_id


class TestMerchantManagerMediaFiles(TestDatabaseFixture):
    """媒体文件管理测试"""
    
    async def add_media_to_merchant(self, db_conn, merchant_id, file_id, file_type='image', file_name=None):
        """辅助函数：为商户添加媒体文件"""
        await db_conn.execute(
            "INSERT INTO media (merchant_id, telegram_file_id, file_type, file_name) VALUES (?, ?, ?, ?)",
            (merchant_id, file_id, file_type, file_name)
        )
        await db_conn.commit()
    
    async def get_merchant_media(self, db_conn, merchant_id):
        """辅助函数：获取商户的媒体文件"""
        cursor = await db_conn.execute(
            "SELECT * FROM media WHERE merchant_id = ?", (merchant_id,)
        )
        return await cursor.fetchall()
    
    @pytest.mark.asyncio
    async def test_media_file_association(self, mock_db_manager):
        """测试媒体文件关联"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 添加媒体文件
        test_files = [
            ('BAADBAADzwADBREAAWYVAAE7gkVl', 'image', '头像.jpg'),
            ('BAADBAADzwADBREAAWYVAAE8gkVm', 'image', '环境照片.jpg'),
            ('BAADBAADzwADBREAAWYVAAE9gkVn', 'video', '介绍视频.mp4')
        ]
        
        for file_id, file_type, file_name in test_files:
            await self.add_media_to_merchant(
                mock_db_manager._real_conn, merchant_id, file_id, file_type, file_name
            )
        
        # 查询媒体文件
        media_files = await self.get_merchant_media(mock_db_manager._real_conn, merchant_id)
        
        assert len(media_files) == 3
        assert all(m['merchant_id'] == merchant_id for m in media_files)
        
        # 验证文件类型和名称
        file_types = [m['file_type'] for m in media_files]
        file_names = [m['file_name'] for m in media_files]
        
        assert 'image' in file_types
        assert 'video' in file_types
        assert '头像.jpg' in file_names
        assert '介绍视频.mp4' in file_names
    
    @pytest.mark.asyncio
    async def test_media_file_deletion_on_merchant_delete(self, mock_db_manager):
        """测试删除商户时级联删除媒体文件"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 添加媒体文件
        await self.add_media_to_merchant(
            mock_db_manager._real_conn, merchant_id, 'test_file_id_123', 'image', 'test.jpg'
        )
        
        # 验证媒体文件存在
        media_files = await self.get_merchant_media(mock_db_manager._real_conn, merchant_id)
        assert len(media_files) == 1
        
        # 删除商户
        success = await MerchantManager.delete_merchant(merchant_id)
        assert success
        
        # 验证媒体文件也被删除
        media_files = await self.get_merchant_media(mock_db_manager._real_conn, merchant_id)
        assert len(media_files) == 0
    
    @pytest.mark.asyncio
    async def test_telegram_file_id_storage(self, mock_db_manager):
        """测试Telegram文件ID存储"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 测试各种Telegram文件ID格式
        telegram_file_ids = [
            'AgACAgIAAxkDAAICGGYVAAE7gkVlAAELm4qh1Jl0AAFvOA', # 图片
            'BAACAgIAAxkDAAICGGYVAAE7gkVlAAELm4qh1Jl0AAFvOB', # 文档
            'AwACAgIAAxkDAAICGGYVAAE7gkVlAAELm4qh1Jl0AAFvOC', # 音频
            'CgACAgIAAxkDAAICGGYVAAE7gkVlAAELm4qh1Jl0AAFvOD'  # 视频
        ]
        
        file_types = ['photo', 'document', 'audio', 'video']
        
        for i, (file_id, file_type) in enumerate(zip(telegram_file_ids, file_types)):
            await self.add_media_to_merchant(
                mock_db_manager._real_conn, merchant_id, file_id, file_type, f'test{i}.file'
            )
        
        # 验证所有文件都正确存储
        media_files = await self.get_merchant_media(mock_db_manager._real_conn, merchant_id)
        assert len(media_files) == 4
        
        stored_file_ids = [m['telegram_file_id'] for m in media_files]
        for file_id in telegram_file_ids:
            assert file_id in stored_file_ids
    
    @pytest.mark.asyncio
    async def test_media_file_query_performance(self, mock_db_manager):
        """测试媒体文件查询性能"""
        # 创建多个商户
        merchant_ids = []
        for i in range(10):
            merchant_data = {'chat_id': 100000 + i, 'name': f'商户{i}'}
            merchant_id = await MerchantManager.create_merchant(merchant_data)
            merchant_ids.append(merchant_id)
        
        # 为每个商户添加多个媒体文件
        for merchant_id in merchant_ids:
            for j in range(5):
                file_id = f"test_file_{merchant_id}_{j}"
                await self.add_media_to_merchant(
                    mock_db_manager._real_conn, merchant_id, file_id, 'image', f'file{j}.jpg'
                )
        
        # 测试单个商户的媒体查询
        import time
        start_time = time.time()
        
        media_files = await self.get_merchant_media(mock_db_manager._real_conn, merchant_ids[0])
        
        query_time = time.time() - start_time
        
        assert len(media_files) == 5
        assert query_time < 1.0  # 查询时间应该少于1秒
        
        # 验证查询结果正确性
        file_ids = [m['telegram_file_id'] for m in media_files]
        for j in range(5):
            expected_file_id = f"test_file_{merchant_ids[0]}_{j}"
            assert expected_file_id in file_ids


class TestMerchantManagerErrorHandling(TestDatabaseFixture):
    """错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_db_manager):
        """测试数据库错误处理"""
        # 模拟数据库连接错误
        mock_db_manager.get_last_insert_id.side_effect = Exception("Database connection failed")
        
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 应该返回None表示创建失败
        assert merchant_id is None
    
    @pytest.mark.asyncio
    async def test_invalid_json_profile_data(self, mock_db_manager):
        """测试无效JSON数据处理"""
        # 首先插入一个包含无效JSON的记录（通过直接数据库操作）
        await mock_db_manager._real_conn.execute(
            "INSERT INTO merchants (chat_id, name, profile_data) VALUES (?, ?, ?)",
            (123456789, '测试商户', 'invalid json string')
        )
        await mock_db_manager._real_conn.commit()
        
        # 获取商户应该能正常处理无效JSON
        merchant = await MerchantManager.get_merchant_by_chat_id(123456789)
        
        assert merchant is not None
        assert merchant['profile_data'] == {}  # 无效JSON应该被转换为空字典
    
    @pytest.mark.asyncio
    async def test_concurrent_merchant_creation(self, mock_db_manager):
        """测试并发商户创建"""
        import asyncio
        
        async def create_merchant_task(chat_id):
            merchant_data = {
                'chat_id': chat_id,
                'name': f'并发商户{chat_id}'
            }
            return await MerchantManager.create_merchant(merchant_data)
        
        # 创建20个并发任务
        tasks = []
        for i in range(20):
            task = create_merchant_task(2000000 + i)
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 检查结果
        successful_results = [r for r in results if isinstance(r, int) and r > 0]
        failed_results = [r for r in results if not isinstance(r, int) or r <= 0]
        
        # 大部分应该成功
        assert len(successful_results) >= 15  # 允许少量失败
        
        # 验证没有重复的ID
        assert len(set(successful_results)) == len(successful_results)
    
    @pytest.mark.asyncio
    async def test_large_profile_data_handling(self, mock_db_manager):
        """测试大型JSON数据处理"""
        # 创建大量的profile_data
        large_profile_data = {
            'services': [f'服务{i}' for i in range(100)],
            'experience_details': {f'年份{i}': f'经验描述{i}' * 100 for i in range(50)},
            'certifications': [
                {
                    'name': f'证书{i}',
                    'description': f'证书描述{i}' * 50,
                    'year': 2020 + i
                } for i in range(30)
            ]
        }
        
        merchant_data = {
            'chat_id': 123456789,
            'name': '大数据测试商户',
            'profile_data': large_profile_data
        }
        
        # 创建商户
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        assert merchant_id is not None
        
        # 获取商户并验证数据完整性
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant is not None
        
        # 验证JSON数据完整性
        assert len(merchant['profile_data']['services']) == 100
        assert len(merchant['profile_data']['experience_details']) == 50
        assert len(merchant['profile_data']['certifications']) == 30
        
        # 验证数据内容正确性
        assert merchant['profile_data']['services'][0] == '服务0'
        assert merchant['profile_data']['certifications'][0]['name'] == '证书0'


# 运行测试的辅助函数
async def run_single_test(test_name, test_class=None):
    """运行单个测试函数"""
    import pytest
    
    if test_class:
        test_path = f"{__file__}::{test_class}::{test_name}"
    else:
        test_path = f"{__file__}::{test_name}"
    
    result = pytest.main(["-v", test_path])
    return result == 0


if __name__ == "__main__":
    # 如果直接运行此文件，执行所有测试
    import pytest
    
    print("开始运行 MerchantManager 全面单元测试...")
    
    # 运行所有测试
    result = pytest.main(["-v", __file__])
    
    if result == 0:
        print("\n✅ 所有测试通过！")
    else:
        print(f"\n❌ 测试失败，退出码: {result}")
    
    exit(result)