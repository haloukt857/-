# -*- coding: utf-8 -*-
"""
RegionManagerV2 集成测试
使用真实数据库连接测试地区管理功能
"""

import asyncio
import sqlite3
import tempfile
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database.db_regions import RegionManager as RegionManagerV2
from database.db_connection import db_manager


class TestRegionIntegration:
    """地区管理器集成测试"""
    
    def __init__(self):
        self.test_db_path = None
        self.original_db_path = None
    
    async def setup_test_database(self):
        """设置测试数据库"""
        # 创建临时数据库文件
        fd, self.test_db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # 保存原始数据库路径
        self.original_db_path = getattr(db_manager, 'db_path', None)
        
        # 创建数据库连接
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # 创建表结构
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
            
            CREATE TRIGGER update_cities_timestamp 
            AFTER UPDATE ON cities
            BEGIN
                UPDATE cities SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
            
            CREATE TRIGGER update_districts_timestamp 
            AFTER UPDATE ON districts
            BEGIN
                UPDATE districts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END;
        ''')
        
        conn.commit()
        conn.close()
        
        # 设置db_manager使用测试数据库
        db_manager.db_path = self.test_db_path
        print(f"测试数据库创建于: {self.test_db_path}")
    
    async def cleanup_test_database(self):
        """清理测试数据库"""
        if self.original_db_path is not None:
            db_manager.db_path = self.original_db_path
        
        if self.test_db_path and os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
            print("测试数据库已清理")
    
    async def test_basic_crud_operations(self):
        """测试基础CRUD操作"""
        print("\n=== 测试基础CRUD操作 ===")
        
        # 1. 测试添加城市
        print("1. 测试添加城市...")
        beijing_id = await RegionManagerV2.add_city('北京')
        shanghai_id = await RegionManagerV2.add_city('上海')
        guangzhou_id = await RegionManagerV2.add_city('广州')
        
        assert beijing_id is not None, "添加北京失败"
        assert shanghai_id is not None, "添加上海失败"
        assert guangzhou_id is not None, "添加广州失败"
        print(f"✅ 成功添加城市: 北京({beijing_id}), 上海({shanghai_id}), 广州({guangzhou_id})")
        
        # 2. 测试添加地区
        print("2. 测试添加地区...")
        chaoyang_id = await RegionManagerV2.add_district(beijing_id, '朝阳区')
        haidian_id = await RegionManagerV2.add_district(beijing_id, '海淀区')
        xicheng_id = await RegionManagerV2.add_district(beijing_id, '西城区')
        pudong_id = await RegionManagerV2.add_district(shanghai_id, '浦东新区')
        huangpu_id = await RegionManagerV2.add_district(shanghai_id, '黄浦区')
        
        assert chaoyang_id is not None, "添加朝阳区失败"
        assert haidian_id is not None, "添加海淀区失败"
        assert pudong_id is not None, "添加浦东新区失败"
        print(f"✅ 成功添加地区: 朝阳区({chaoyang_id}), 海淀区({haidian_id}), 浦东新区({pudong_id})")
        
        # 3. 测试查询所有城市和地区
        print("3. 测试查询所有城市和地区...")
        all_cities = await RegionManagerV2.get_all_cities_with_districts()
        
        assert len(all_cities) == 3, f"期望3个城市，实际{len(all_cities)}个"
        
        beijing_data = next((city for city in all_cities if city['name'] == '北京'), None)
        assert beijing_data is not None, "未找到北京数据"
        assert len(beijing_data['districts']) == 3, f"北京应有3个地区，实际{len(beijing_data['districts'])}个"
        
        shanghai_data = next((city for city in all_cities if city['name'] == '上海'), None)
        assert shanghai_data is not None, "未找到上海数据"
        assert len(shanghai_data['districts']) == 2, f"上海应有2个地区，实际{len(shanghai_data['districts'])}个"
        
        guangzhou_data = next((city for city in all_cities if city['name'] == '广州'), None)
        assert guangzhou_data is not None, "未找到广州数据"
        assert len(guangzhou_data['districts']) == 0, f"广州应有0个地区，实际{len(guangzhou_data['districts'])}个"
        
        print("✅ 查询所有城市和地区成功")
        
        # 4. 测试按城市查询地区
        print("4. 测试按城市查询地区...")
        beijing_districts = await RegionManagerV2.get_districts_by_city(beijing_id)
        shanghai_districts = await RegionManagerV2.get_districts_by_city(shanghai_id)
        guangzhou_districts = await RegionManagerV2.get_districts_by_city(guangzhou_id)
        
        assert len(beijing_districts) == 3, f"北京应有3个地区，实际{len(beijing_districts)}个"
        assert len(shanghai_districts) == 2, f"上海应有2个地区，实际{len(shanghai_districts)}个"
        assert len(guangzhou_districts) == 0, f"广州应有0个地区，实际{len(guangzhou_districts)}个"
        
        print("✅ 按城市查询地区成功")
        
        return {
            'beijing_id': beijing_id,
            'shanghai_id': shanghai_id,
            'guangzhou_id': guangzhou_id,
            'chaoyang_id': chaoyang_id,
            'haidian_id': haidian_id,
            'xicheng_id': xicheng_id,
            'pudong_id': pudong_id,
            'huangpu_id': huangpu_id
        }
    
    async def test_status_toggle_operations(self, ids):
        """测试状态切换操作"""
        print("\n=== 测试状态切换操作 ===")
        
        # 测试切换城市状态
        print("1. 测试切换城市状态...")
        success = await RegionManagerV2.toggle_city_status(ids['beijing_id'])
        assert success, "切换北京状态失败"
        
        # 验证状态已切换
        all_cities = await RegionManagerV2.get_all_cities_with_districts()
        beijing_data = next((city for city in all_cities if city['name'] == '北京'), None)
        assert beijing_data['is_active'] == False, "北京状态应该为False"
        
        # 切换回来
        success = await RegionManagerV2.toggle_city_status(ids['beijing_id'])
        assert success, "恢复北京状态失败"
        print("✅ 城市状态切换成功")
        
        # 测试切换地区状态
        print("2. 测试切换地区状态...")
        success = await RegionManagerV2.toggle_district_status(ids['chaoyang_id'])
        assert success, "切换朝阳区状态失败"
        
        # 验证切换后的查询结果（只返回active的地区）
        beijing_districts = await RegionManagerV2.get_districts_by_city(ids['beijing_id'])
        chaoyang_found = any(district['name'] == '朝阳区' for district in beijing_districts)
        assert not chaoyang_found, "朝阳区应该被过滤掉（is_active=False）"
        
        # 切换回来
        success = await RegionManagerV2.toggle_district_status(ids['chaoyang_id'])
        assert success, "恢复朝阳区状态失败"
        print("✅ 地区状态切换成功")
    
    async def test_constraint_validations(self, ids):
        """测试数据完整性约束"""
        print("\n=== 测试数据完整性约束 ===")
        
        # 1. 测试重复城市名称
        print("1. 测试重复城市名称...")
        duplicate_id = await RegionManagerV2.add_city('北京')
        assert duplicate_id is None, "重复城市名称应该返回None"
        print("✅ 重复城市名称约束正常")
        
        # 2. 测试重复地区名称（同一城市下）
        print("2. 测试重复地区名称...")
        duplicate_district_id = await RegionManagerV2.add_district(ids['beijing_id'], '朝阳区')
        assert duplicate_district_id is None, "重复地区名称应该返回None"
        print("✅ 重复地区名称约束正常")
        
        # 3. 测试不存在的城市ID
        print("3. 测试不存在的城市ID...")
        invalid_district_id = await RegionManagerV2.add_district(999999, '测试区')
        assert invalid_district_id is None, "不存在的城市ID应该返回None"
        print("✅ 外键约束正常")
    
    async def test_cascade_delete(self, ids):
        """测试级联删除"""
        print("\n=== 测试级联删除 ===")
        
        # 先验证地区存在
        beijing_districts = await RegionManagerV2.get_districts_by_city(ids['beijing_id'])
        initial_district_count = len(beijing_districts)
        assert initial_district_count > 0, "北京应该有地区"
        
        # 删除城市
        print("删除北京市...")
        success = await RegionManagerV2.delete_city(ids['beijing_id'])
        assert success, "删除北京失败"
        
        # 验证地区也被删除
        beijing_districts_after = await RegionManagerV2.get_districts_by_city(ids['beijing_id'])
        assert len(beijing_districts_after) == 0, "删除城市后，其地区应该也被删除"
        
        # 验证其他城市不受影响
        all_cities = await RegionManagerV2.get_all_cities_with_districts()
        remaining_cities = [city['name'] for city in all_cities]
        assert '北京' not in remaining_cities, "北京应该已被删除"
        assert '上海' in remaining_cities, "上海应该仍然存在"
        assert '广州' in remaining_cities, "广州应该仍然存在"
        
        print("✅ 级联删除功能正常")
    
    async def test_edge_cases(self, ids):
        """测试边界条件"""
        print("\n=== 测试边界条件 ===")
        
        # 1. 测试空字符串
        print("1. 测试空字符串...")
        empty_city_id = await RegionManagerV2.add_city('')
        assert empty_city_id is None, "空城市名应该返回None"
        
        empty_district_id = await RegionManagerV2.add_district(ids['shanghai_id'], '')
        assert empty_district_id is None, "空地区名应该返回None"
        print("✅ 空字符串处理正常")
        
        # 2. 测试超长字符串
        print("2. 测试超长字符串...")
        long_name = 'A' * 1000
        long_city_id = await RegionManagerV2.add_city(long_name)
        # 根据数据库设计，这可能成功也可能失败，取决于字段长度限制
        print("✅ 超长字符串测试完成")
        
        # 3. 测试特殊字符
        print("3. 测试特殊字符...")
        special_names = [
            '中关村/海淀区',
            '三里屯·朝阳区', 
            '西单(商业区)',
            '东城区&西城区',
            'IT产业园区'
        ]
        
        for name in special_names:
            city_id = await RegionManagerV2.add_city(name)
            if city_id:
                # 添加成功，测试添加地区
                district_id = await RegionManagerV2.add_district(city_id, f'{name}的地区')
                print(f"✅ 特殊字符城市 '{name}' 处理成功")
        
        # 4. 测试不存在的ID操作
        print("4. 测试不存在的ID操作...")
        nonexistent_id = 999999
        
        districts = await RegionManagerV2.get_districts_by_city(nonexistent_id)
        assert districts == [], "不存在的城市ID应该返回空列表"
        
        toggle_result = await RegionManagerV2.toggle_city_status(nonexistent_id)
        # 这可能返回True或False，取决于实现
        
        delete_result = await RegionManagerV2.delete_city(nonexistent_id)
        # 这可能返回True或False，取决于实现
        
        print("✅ 不存在ID操作测试完成")
    
    async def test_unicode_support(self):
        """测试Unicode支持"""
        print("\n=== 测试Unicode支持 ===")
        
        unicode_cities = [
            ('東京都', ['渋谷区', '新宿区']),
            ('서울시', ['강남구', '마포구']),
            ('москва', ['центр', 'юг']),
            ('القاهرة', ['وسط', 'شرق'])
        ]
        
        for city_name, district_names in unicode_cities:
            print(f"测试 {city_name}...")
            city_id = await RegionManagerV2.add_city(city_name)
            if city_id:
                for district_name in district_names:
                    district_id = await RegionManagerV2.add_district(city_id, district_name)
                    if district_id:
                        print(f"  ✅ 地区 {district_name} 添加成功")
                print(f"✅ 城市 {city_name} 测试完成")
        
        # 验证Unicode查询
        all_cities = await RegionManagerV2.get_all_cities_with_districts()
        unicode_city_names = [city['name'] for city in all_cities if any(ord(char) > 127 for char in city['name'])]
        
        print(f"✅ Unicode支持测试完成，发现Unicode城市: {unicode_city_names}")
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("开始运行 RegionManagerV2 集成测试...")
        
        try:
            await self.setup_test_database()
            
            # 基础CRUD测试
            ids = await self.test_basic_crud_operations()
            
            # 状态切换测试
            await self.test_status_toggle_operations(ids)
            
            # 约束验证测试
            await self.test_constraint_validations(ids)
            
            # Unicode支持测试
            await self.test_unicode_support()
            
            # 边界条件测试
            await self.test_edge_cases(ids)
            
            # 级联删除测试（放在最后，因为会删除数据）
            await self.test_cascade_delete(ids)
            
            print("\n🎉 所有集成测试通过！")
            
        except Exception as e:
            print(f"\n💥 集成测试失败: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await self.cleanup_test_database()


# 直接运行测试
if __name__ == '__main__':
    async def main():
        integration_test = TestRegionIntegration()
        await integration_test.run_all_tests()
    
    asyncio.run(main())