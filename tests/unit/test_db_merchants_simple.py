# -*- coding: utf-8 -*-
"""
MerchantManager 简化单元测试

专注于核心功能测试，使用简化的测试设置
"""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, AsyncMock, MagicMock

import aiosqlite

# 导入被测试的模块
from database.db_merchants import MerchantManager


class TestMerchantManagerSimple:
    """简化的MerchantManager测试"""
    
    @pytest.fixture
    async def test_db(self):
        """创建临时测试数据库"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        db_path = temp_file.name
        
        # 初始化测试数据库
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # 创建merchants表（城市/区县标准）
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
                    city_id INTEGER,
                    district_id INTEGER,
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
            
            # 创建城市/区县表
            await db.execute('''
                CREATE TABLE cities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            await db.execute('''
                CREATE TABLE districts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (city_id) REFERENCES cities(id),
                    UNIQUE(city_id, name)
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
            
            # 插入测试数据
            await db.execute("INSERT INTO cities (id, name) VALUES (1, '北京市')")
            await db.execute("INSERT INTO cities (id, name) VALUES (2, '上海市')")
            await db.execute("INSERT INTO districts (id, city_id, name) VALUES (1, 1, '朝阳区')")
            await db.execute("INSERT INTO districts (id, city_id, name) VALUES (2, 1, '海淀区')")
            await db.execute("INSERT INTO districts (id, city_id, name) VALUES (3, 2, '浦东新区')")
            
            await db.commit()
        
        yield db_path
        
        # 清理
        try:
            os.unlink(db_path)
        except OSError:
            pass
    
    @pytest.fixture
    async def db_connection(self, test_db):
        """创建数据库连接"""
        conn = await aiosqlite.connect(test_db)
        conn.row_factory = aiosqlite.Row
        yield conn
        await conn.close()
    
    @pytest.fixture
    async def patched_db_manager(self, db_connection):
        """创建模拟的数据库管理器"""
        mock_manager = MagicMock()
        
        # 实现真实的数据库操作
        async def get_last_insert_id(query, params):
            cursor = await db_connection.execute(query, params)
            await db_connection.commit()
            return cursor.lastrowid
        
        async def fetch_one(query, params=None):
            if params:
                cursor = await db_connection.execute(query, params)
            else:
                cursor = await db_connection.execute(query)
            return await cursor.fetchone()
        
        async def fetch_all(query, params=None):
            if params:
                cursor = await db_connection.execute(query, params)
            else:
                cursor = await db_connection.execute(query)
            return await cursor.fetchall()
        
        async def execute_query(query, params=None):
            if params:
                cursor = await db_connection.execute(query, params)
            else:
                cursor = await db_connection.execute(query)
            await db_connection.commit()
            return cursor.rowcount
        
        mock_manager.get_last_insert_id = AsyncMock(side_effect=get_last_insert_id)
        mock_manager.fetch_one = AsyncMock(side_effect=fetch_one)
        mock_manager.fetch_all = AsyncMock(side_effect=fetch_all)
        mock_manager.execute_query = AsyncMock(side_effect=execute_query)
        
        # 使用patch替换全局db_manager
        with patch('database.db_merchants.db_manager', mock_manager):
            yield mock_manager
    
    @pytest.mark.asyncio
    async def test_create_merchant_basic(self, patched_db_manager):
        """测试基本商户创建"""
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
    async def test_get_merchant_by_id(self, patched_db_manager):
        """测试通过ID获取商户"""
        # 创建商户
        merchant_data = {
            'chat_id': 123456789,
            'name': '测试商户',
            'city_id': 1,   # 北京市
            'district_id': 1  # 朝阳区
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 获取商户
        merchant = await MerchantManager.get_merchant(merchant_id)
        
        assert merchant is not None
        assert merchant['id'] == merchant_id
        assert merchant['chat_id'] == 123456789
        assert merchant['name'] == '测试商户'
    
    @pytest.mark.asyncio
    async def test_get_merchant_by_chat_id(self, patched_db_manager):
        """测试通过chat_id获取商户"""
        chat_id = 987654321
        merchant_data = {
            'chat_id': chat_id,
            'name': '测试商户2'
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 通过chat_id获取
        merchant = await MerchantManager.get_merchant_by_chat_id(chat_id)
        
        assert merchant is not None
        assert merchant['id'] == merchant_id
        assert merchant['chat_id'] == chat_id
    
    @pytest.mark.asyncio
    async def test_update_merchant(self, patched_db_manager):
        """测试更新商户"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '原始名称'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 更新商户
        update_data = {
            'name': '更新后名称',
            'p_price': 100.5,
            'profile_data': {'test': 'data'}
        }
        
        success = await MerchantManager.update_merchant(merchant_id, update_data)
        assert success
        
        # 验证更新
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['name'] == '更新后名称'
        assert merchant['p_price'] == 100.5
    
    @pytest.mark.asyncio
    async def test_update_merchant_status(self, patched_db_manager):
        """测试更新商户状态"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 更新状态
        success = await MerchantManager.update_merchant_status(merchant_id, 'active')
        assert success
        
        # 验证状态
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['status'] == 'active'
    
    @pytest.mark.asyncio
    async def test_delete_merchant(self, patched_db_manager):
        """测试删除商户"""
        # 创建商户
        merchant_data = {'chat_id': 123456789, 'name': '待删除商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        # 删除商户
        success = await MerchantManager.delete_merchant(merchant_id)
        assert success
        
        # 验证删除
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant is None
    
    @pytest.mark.asyncio
    async def test_create_blank_merchant(self, patched_db_manager):
        """测试创建空白商户"""
        chat_id = 123456789
        binding_code = 'TEST123456'
        
        merchant_id = await MerchantManager.create_blank_merchant(chat_id, binding_code)
        
        assert merchant_id is not None
        
        # 验证空白商户属性
        merchant = await MerchantManager.get_merchant(merchant_id)
        assert merchant['name'] == '待完善'
        assert merchant['status'] == 'pending'
        assert merchant['custom_description'] == '待完善'
        assert merchant['contact_info'] == '待完善'
    
    @pytest.mark.asyncio
    async def test_get_merchants_list(self, patched_db_manager):
        """测试获取商户列表"""
        # 创建多个商户
        for i in range(3):
            merchant_data = {
                'chat_id': 100000 + i,
                'name': f'测试商户{i}',
                'status': 'active' if i < 2 else 'pending'
            }
            await MerchantManager.create_merchant(merchant_data)
        
        # 获取所有商户
        all_merchants = await MerchantManager.get_merchants()
        assert len(all_merchants) >= 3
        
        # 按状态筛选
        active_merchants = await MerchantManager.get_merchants(status='active')
        assert len(active_merchants) >= 2
        
        pending_merchants = await MerchantManager.get_merchants(status='pending')
        assert len(pending_merchants) >= 1
    
    @pytest.mark.asyncio
    async def test_search_merchants(self, patched_db_manager):
        """测试搜索商户"""
        # 创建测试商户
        merchants_data = [
            {'chat_id': 111, 'name': '北京教育机构', 'custom_description': '专业教育'},
            {'chat_id': 222, 'name': '上海美容院', 'custom_description': '美容服务'},
            {'chat_id': 333, 'name': '广州健身中心', 'custom_description': '健身培训'},
        ]
        
        for data in merchants_data:
            await MerchantManager.create_merchant(data)
        
        # 搜索测试
        results = await MerchantManager.search_merchants('教育')
        assert len(results) >= 1
        assert any('教育' in m['name'] or '教育' in m['custom_description'] for m in results)
        
        results = await MerchantManager.search_merchants('美容')
        assert len(results) >= 1
        assert any('美容' in m['name'] or '美容' in m['custom_description'] for m in results)
    
    @pytest.mark.asyncio
    async def test_duplicate_chat_id_handling(self, patched_db_manager):
        """测试重复chat_id处理"""
        chat_id = 123456789
        merchant_data = {'chat_id': chat_id, 'name': '第一个商户'}
        
        # 第一次创建
        merchant_id1 = await MerchantManager.create_merchant(merchant_data)
        assert merchant_id1 is not None
        
        # 第二次创建相同chat_id
        merchant_data['name'] = '第二个商户'
        merchant_id2 = await MerchantManager.create_merchant(merchant_data)
        
        # 应该返回相同的ID
        assert merchant_id2 == merchant_id1
    
    @pytest.mark.asyncio
    async def test_invalid_operations(self, patched_db_manager):
        """测试无效操作"""
        # 测试获取不存在的商户
        merchant = await MerchantManager.get_merchant(999999)
        assert merchant is None
        
        merchant = await MerchantManager.get_merchant_by_chat_id(999999999)
        assert merchant is None
        
        # 测试更新不存在的商户
        success = await MerchantManager.update_merchant(999999, {'name': '测试'})
        assert not success
        
        # 测试删除不存在的商户
        success = await MerchantManager.delete_merchant(999999)
        assert not success
        
        # 测试无效状态更新
        merchant_data = {'chat_id': 123456789, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        
        success = await MerchantManager.update_merchant_status(merchant_id, 'invalid_status')
        assert not success
    
    @pytest.mark.asyncio
    async def test_profile_data_json_handling(self, patched_db_manager):
        """测试JSON数据处理"""
        # 测试dict类型的profile_data
        profile_data = {
            'services': ['英语', '数学'],
            'experience': 5,
            'certifications': ['TEFL', 'CELTA']
        }
        
        merchant_data = {
            'chat_id': 123456789,
            'name': '测试商户',
            'profile_data': profile_data
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        merchant = await MerchantManager.get_merchant(merchant_id)
        
        assert isinstance(merchant['profile_data'], dict)
        assert merchant['profile_data']['services'] == ['英语', '数学']
        assert merchant['profile_data']['experience'] == 5
    
    @pytest.mark.asyncio
    async def test_region_display_generation(self, patched_db_manager):
        """测试地区显示信息生成"""
        merchant_data = {
            'chat_id': 123456789,
            'name': '测试商户',
            'province_id': 1,  # 北京市
            'region_id': 1     # 朝阳区
        }
        
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        merchant = await MerchantManager.get_merchant(merchant_id)
        
        assert merchant['city_name'] == '北京市'
        assert merchant['district_name'] == '朝阳区'
        assert merchant['region_display'] == '北京市 - 朝阳区'
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, patched_db_manager):
        """测试缺少必需字段"""
        # 缺少chat_id
        merchant_data = {'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        assert merchant_id is None
        
        # 空的chat_id
        merchant_data = {'chat_id': None, 'name': '测试商户'}
        merchant_id = await MerchantManager.create_merchant(merchant_data)
        assert merchant_id is None


# 运行单个测试的辅助函数
async def run_test():
    """运行测试的辅助函数"""
    import pytest
    
    # 运行测试
    result = pytest.main(["-v", __file__, "--tb=short"])
    return result == 0


if __name__ == "__main__":
    # 如果直接运行此文件，执行测试
    import pytest
    
    print("开始运行 MerchantManager 简化单元测试...")
    
    # 运行所有测试
    result = pytest.main(["-v", __file__, "--tb=short"])
    
    if result == 0:
        print("\n✅ 所有测试通过！")
    else:
        print(f"\n❌ 测试失败，退出码: {result}")
    
    exit(result)
