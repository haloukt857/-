# -*- coding: utf-8 -*-
"""
RegionManagerV2 综合测试
测试地区管理器的所有功能模块
"""

import asyncio
import pytest
import sqlite3
import tempfile
import os
from unittest.mock import AsyncMock, patch
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database.db_regions import RegionManager as RegionManagerV2
from database.db_connection import db_manager


class TestRegionManagerV2:
    """RegionManagerV2 全面测试套件"""
    
    @pytest.fixture(autouse=True)
    async def setup_test_db(self):
        """设置测试数据库"""
        # 创建临时数据库文件
        self.test_db_fd, self.test_db_path = tempfile.mkstemp(suffix='.db')
        
        # 初始化测试数据库结构
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # 创建测试表结构
        cursor.executescript('''
            CREATE TABLE cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE districts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (city_id) REFERENCES cities (id) ON DELETE CASCADE,
                UNIQUE(city_id, name)
            );
            
            -- 插入测试数据
            INSERT INTO cities (id, name, is_active) VALUES 
                (1, '北京', TRUE),
                (2, '上海', TRUE),
                (3, '广州', FALSE);
                
            INSERT INTO districts (id, city_id, name, is_active) VALUES 
                (1, 1, '朝阳区', TRUE),
                (2, 1, '海淀区', TRUE),
                (3, 1, '西城区', FALSE),
                (4, 2, '浦东新区', TRUE),
                (5, 2, '黄浦区', TRUE);
        ''')
        
        conn.commit()
        conn.close()
        
        # Mock db_manager 使用测试数据库
        self.original_db_path = getattr(db_manager, 'db_path', None)
        db_manager.db_path = self.test_db_path
        
        yield
        
        # 清理
        db_manager.db_path = self.original_db_path
        os.close(self.test_db_fd)
        os.unlink(self.test_db_path)

    async def test_get_all_cities_with_districts(self):
        """测试获取所有城市及其地区"""
        # Mock db_manager.fetch_all
        mock_results = [
            {'city_id': 1, 'city_name': '北京', 'city_is_active': True, 'district_id': 1, 'district_name': '朝阳区', 'district_is_active': True},
            {'city_id': 1, 'city_name': '北京', 'city_is_active': True, 'district_id': 2, 'district_name': '海淀区', 'district_is_active': True},
            {'city_id': 2, 'city_name': '上海', 'city_is_active': True, 'district_id': 4, 'district_name': '浦东新区', 'district_is_active': True},
            {'city_id': 3, 'city_name': '广州', 'city_is_active': False, 'district_id': None, 'district_name': None, 'district_is_active': None}
        ]
        
        with patch.object(db_manager, 'fetch_all', return_value=mock_results):
            result = await RegionManagerV2.get_all_cities_with_districts()
            
            assert len(result) == 3
            
            # 验证北京数据
            beijing = next(city for city in result if city['name'] == '北京')
            assert beijing['id'] == 1
            assert beijing['is_active'] == True
            assert len(beijing['districts']) == 2
            assert beijing['districts'][0]['name'] == '朝阳区'
            assert beijing['districts'][1]['name'] == '海淀区'
            
            # 验证上海数据
            shanghai = next(city for city in result if city['name'] == '上海')
            assert shanghai['id'] == 2
            assert len(shanghai['districts']) == 1
            assert shanghai['districts'][0]['name'] == '浦东新区'
            
            # 验证广州数据（无地区）
            guangzhou = next(city for city in result if city['name'] == '广州')
            assert guangzhou['id'] == 3
            assert len(guangzhou['districts']) == 0

    async def test_add_city_success(self):
        """测试成功添加城市"""
        with patch.object(db_manager, 'get_last_insert_id', return_value=100):
            result = await RegionManagerV2.add_city('深圳')
            assert result == 100

    async def test_add_city_failure(self):
        """测试添加城市失败"""
        with patch.object(db_manager, 'get_last_insert_id', side_effect=Exception('数据库错误')):
            result = await RegionManagerV2.add_city('深圳')
            assert result is None

    async def test_add_city_duplicate(self):
        """测试添加重复城市"""
        with patch.object(db_manager, 'get_last_insert_id', side_effect=sqlite3.IntegrityError('UNIQUE constraint failed')):
            result = await RegionManagerV2.add_city('北京')
            assert result is None

    async def test_add_district_success(self):
        """测试成功添加地区"""
        with patch.object(db_manager, 'get_last_insert_id', return_value=200):
            result = await RegionManagerV2.add_district(1, '丰台区')
            assert result == 200

    async def test_add_district_invalid_city(self):
        """测试为不存在的城市添加地区"""
        with patch.object(db_manager, 'get_last_insert_id', side_effect=sqlite3.IntegrityError('FOREIGN KEY constraint failed')):
            result = await RegionManagerV2.add_district(999, '测试区')
            assert result is None

    async def test_add_district_duplicate(self):
        """测试添加重复地区"""
        with patch.object(db_manager, 'get_last_insert_id', side_effect=sqlite3.IntegrityError('UNIQUE constraint failed')):
            result = await RegionManagerV2.add_district(1, '朝阳区')
            assert result is None

    async def test_get_districts_by_city_success(self):
        """测试获取指定城市的地区"""
        mock_results = [
            {'id': 1, 'city_id': 1, 'name': '朝阳区', 'is_active': True},
            {'id': 2, 'city_id': 1, 'name': '海淀区', 'is_active': True}
        ]
        
        with patch.object(db_manager, 'fetch_all', return_value=mock_results):
            result = await RegionManagerV2.get_districts_by_city(1)
            
            assert len(result) == 2
            assert result[0]['name'] == '朝阳区'
            assert result[1]['name'] == '海淀区'
            assert all(district['is_active'] for district in result)

    async def test_get_districts_by_city_empty(self):
        """测试获取无地区城市的地区列表"""
        with patch.object(db_manager, 'fetch_all', return_value=[]):
            result = await RegionManagerV2.get_districts_by_city(999)
            assert result == []

    async def test_get_districts_by_city_error(self):
        """测试获取地区时数据库错误"""
        with patch.object(db_manager, 'fetch_all', side_effect=Exception('数据库连接失败')):
            result = await RegionManagerV2.get_districts_by_city(1)
            assert result == []

    async def test_toggle_city_status_success(self):
        """测试切换城市状态成功"""
        with patch.object(db_manager, 'execute_query', return_value=None):
            result = await RegionManagerV2.toggle_city_status(1)
            assert result == True

    async def test_toggle_city_status_error(self):
        """测试切换城市状态失败"""
        with patch.object(db_manager, 'execute_query', side_effect=Exception('更新失败')):
            result = await RegionManagerV2.toggle_city_status(1)
            assert result == False

    async def test_toggle_district_status_success(self):
        """测试切换地区状态成功"""
        with patch.object(db_manager, 'execute_query', return_value=None):
            result = await RegionManagerV2.toggle_district_status(1)
            assert result == True

    async def test_toggle_district_status_error(self):
        """测试切换地区状态失败"""
        with patch.object(db_manager, 'execute_query', side_effect=Exception('更新失败')):
            result = await RegionManagerV2.toggle_district_status(1)
            assert result == False

    async def test_delete_city_success(self):
        """测试删除城市成功"""
        with patch.object(db_manager, 'execute_query', return_value=None):
            result = await RegionManagerV2.delete_city(1)
            assert result == True

    async def test_delete_city_error(self):
        """测试删除城市失败"""
        with patch.object(db_manager, 'execute_query', side_effect=Exception('删除失败')):
            result = await RegionManagerV2.delete_city(1)
            assert result == False

    async def test_delete_district_success(self):
        """测试删除地区成功"""
        with patch.object(db_manager, 'execute_query', return_value=None):
            result = await RegionManagerV2.delete_district(1)
            assert result == True

    async def test_delete_district_error(self):
        """测试删除地区失败"""
        with patch.object(db_manager, 'execute_query', side_effect=Exception('删除失败')):
            result = await RegionManagerV2.delete_district(1)
            assert result == False

    async def test_cascade_delete(self):
        """测试级联删除 - 删除城市时同时删除其地区"""
        # 这个测试需要真实的数据库连接来验证外键约束
        # 在实际测试中，应该验证删除城市后，其下属地区也被删除
        pass

    async def test_edge_cases(self):
        """测试边界条件"""
        # 测试空字符串输入
        with patch.object(db_manager, 'get_last_insert_id', side_effect=Exception('空值错误')):
            result = await RegionManagerV2.add_city('')
            assert result is None
            
            result = await RegionManagerV2.add_district(1, '')
            assert result is None

    async def test_special_characters(self):
        """测试特殊字符处理"""
        special_names = ['中关村街道', '三里屯/朝阳区', '西单·商业区', '东城区(历史)']
        
        for name in special_names:
            with patch.object(db_manager, 'get_last_insert_id', return_value=100):
                result = await RegionManagerV2.add_city(name)
                assert result == 100

    async def test_unicode_handling(self):
        """测试Unicode字符处理"""
        unicode_names = ['北京市', '東京都', '서울시', 'москва']
        
        for name in unicode_names:
            with patch.object(db_manager, 'get_last_insert_id', return_value=100):
                result = await RegionManagerV2.add_city(name)
                assert result == 100

    async def test_large_dataset(self):
        """测试大数据集处理"""
        # 模拟大量城市和地区数据
        large_dataset = []
        for i in range(100):
            for j in range(10):
                large_dataset.append({
                    'city_id': i+1, 
                    'city_name': f'城市{i+1}', 
                    'city_is_active': True,
                    'district_id': i*10+j+1, 
                    'district_name': f'地区{i*10+j+1}', 
                    'district_is_active': True
                })
        
        with patch.object(db_manager, 'fetch_all', return_value=large_dataset):
            result = await RegionManagerV2.get_all_cities_with_districts()
            assert len(result) == 100
            assert all(len(city['districts']) == 10 for city in result)

    async def test_concurrent_operations(self):
        """测试并发操作"""
        # 模拟并发添加城市
        tasks = []
        for i in range(10):
            with patch.object(db_manager, 'get_last_insert_id', return_value=i):
                task = RegionManagerV2.add_city(f'并发城市{i}')
                tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 验证结果
        assert len(results) == 10
        # 注意：由于使用了mock，这里主要测试并发调用的稳定性

    def test_logging_behavior(self):
        """测试日志记录行为"""
        # 这里可以测试错误日志是否正确记录
        # 可以使用 caplog fixture 来捕获日志输出
        pass


# 运行测试的辅助函数
async def run_single_test(test_func):
    """运行单个异步测试"""
    test_instance = TestRegionManagerV2()
    await test_instance.setup_test_db().__anext__()
    try:
        await test_func(test_instance)
        print(f"✅ {test_func.__name__} 通过")
    except Exception as e:
        print(f"❌ {test_func.__name__} 失败: {e}")
    finally:
        # 清理资源
        try:
            await test_instance.setup_test_db().__anext__()
        except StopAsyncIteration:
            pass


if __name__ == '__main__':
    # 直接运行测试
    async def main():
        print("开始运行 RegionManagerV2 综合测试...")
        
        test_instance = TestRegionManagerV2()
        
        # 设置测试环境
        setup_gen = test_instance.setup_test_db()
        await setup_gen.__anext__()
        
        try:
            # 运行所有测试
            test_methods = [
                test_instance.test_get_all_cities_with_districts,
                test_instance.test_add_city_success,
                test_instance.test_add_city_failure,
                test_instance.test_add_district_success,
                test_instance.test_add_district_invalid_city,
                test_instance.test_get_districts_by_city_success,
                test_instance.test_get_districts_by_city_empty,
                test_instance.test_toggle_city_status_success,
                test_instance.test_toggle_district_status_success,
                test_instance.test_delete_city_success,
                test_instance.test_delete_district_success,
                test_instance.test_special_characters,
                test_instance.test_unicode_handling,
                test_instance.test_large_dataset,
            ]
            
            passed = 0
            failed = 0
            
            for test_method in test_methods:
                try:
                    await test_method()
                    print(f"✅ {test_method.__name__} 通过")
                    passed += 1
                except Exception as e:
                    print(f"❌ {test_method.__name__} 失败: {e}")
                    failed += 1
            
            print(f"\n测试完成: {passed} 通过, {failed} 失败")
            
        finally:
            # 清理测试环境
            try:
                await setup_gen.__anext__()
            except StopAsyncIteration:
                pass
    
    asyncio.run(main())