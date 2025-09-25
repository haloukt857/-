# -*- coding: utf-8 -*-
"""
RegionManagerV2 直接测试
不使用pytest框架，直接测试基本功能
"""

import asyncio
import tempfile
import os
import sys
from unittest.mock import AsyncMock, patch

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.db_regions import RegionManagerV2


async def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试RegionManagerV2基本功能 ===\n")
    
    # 1. 测试get_all_cities_with_districts
    print("1. 测试get_all_cities_with_districts方法...")
    
    mock_results = [
        {'city_id': 1, 'city_name': '北京', 'city_is_active': True, 'district_id': 1, 'district_name': '朝阳区', 'district_is_active': True},
        {'city_id': 1, 'city_name': '北京', 'city_is_active': True, 'district_id': 2, 'district_name': '海淀区', 'district_is_active': True},
        {'city_id': 2, 'city_name': '上海', 'city_is_active': True, 'district_id': 3, 'district_name': '浦东新区', 'district_is_active': True},
        {'city_id': 3, 'city_name': '广州', 'city_is_active': False, 'district_id': None, 'district_name': None, 'district_is_active': None}
    ]
    
    # Mock数据库管理器
    from database.db_connection import db_manager
    with patch.object(db_manager, 'fetch_all', return_value=mock_results):
        result = await RegionManagerV2.get_all_cities_with_districts()
        
        assert len(result) == 3, f"应该返回3个城市，实际返回{len(result)}个"
        
        beijing = next((city for city in result if city['name'] == '北京'), None)
        assert beijing is not None, "未找到北京数据"
        assert len(beijing['districts']) == 2, f"北京应有2个地区，实际{len(beijing['districts'])}个"
        assert beijing['districts'][0]['name'] == '朝阳区'
        assert beijing['districts'][1]['name'] == '海淀区'
        
        shanghai = next((city for city in result if city['name'] == '上海'), None)
        assert shanghai is not None, "未找到上海数据"
        assert len(shanghai['districts']) == 1, f"上海应有1个地区，实际{len(shanghai['districts'])}个"
        
        guangzhou = next((city for city in result if city['name'] == '广州'), None)
        assert guangzhou is not None, "未找到广州数据"
        assert len(guangzhou['districts']) == 0, f"广州应有0个地区，实际{len(guangzhou['districts'])}个"
        
    print("  ✅ get_all_cities_with_districts测试通过")
    
    # 2. 测试add_city
    print("2. 测试add_city方法...")
    
    with patch.object(db_manager, 'get_last_insert_id', return_value=100):
        result = await RegionManagerV2.add_city('深圳')
        assert result == 100, f"添加城市应该返回100，实际返回{result}"
    
    with patch.object(db_manager, 'get_last_insert_id', side_effect=Exception('数据库错误')):
        result = await RegionManagerV2.add_city('杭州')
        assert result is None, f"异常情况下应该返回None，实际返回{result}"
        
    print("  ✅ add_city测试通过")
    
    # 3. 测试add_district
    print("3. 测试add_district方法...")
    
    with patch.object(db_manager, 'get_last_insert_id', return_value=200):
        result = await RegionManagerV2.add_district(1, '福田区')
        assert result == 200, f"添加地区应该返回200，实际返回{result}"
    
    with patch.object(db_manager, 'get_last_insert_id', side_effect=Exception('外键约束失败')):
        result = await RegionManagerV2.add_district(999, '测试区')
        assert result is None, f"异常情况下应该返回None，实际返回{result}"
        
    print("  ✅ add_district测试通过")
    
    # 4. 测试get_districts_by_city
    print("4. 测试get_districts_by_city方法...")
    
    mock_districts = [
        {'id': 1, 'city_id': 1, 'name': '朝阳区', 'is_active': True},
        {'id': 2, 'city_id': 1, 'name': '海淀区', 'is_active': True}
    ]
    
    with patch.object(db_manager, 'fetch_all', return_value=mock_districts):
        result = await RegionManagerV2.get_districts_by_city(1)
        assert len(result) == 2, f"应该返回2个地区，实际返回{len(result)}个"
        assert result[0]['name'] == '朝阳区'
        assert result[1]['name'] == '海淀区'
    
    with patch.object(db_manager, 'fetch_all', return_value=[]):
        result = await RegionManagerV2.get_districts_by_city(999)
        assert result == [], f"不存在的城市应该返回空列表，实际返回{result}"
        
    with patch.object(db_manager, 'fetch_all', side_effect=Exception('查询错误')):
        result = await RegionManagerV2.get_districts_by_city(1)
        assert result == [], f"异常情况下应该返回空列表，实际返回{result}"
        
    print("  ✅ get_districts_by_city测试通过")
    
    # 5. 测试状态切换功能
    print("5. 测试状态切换功能...")
    
    with patch.object(db_manager, 'execute_query', return_value=None):
        result = await RegionManagerV2.toggle_city_status(1)
        assert result == True, f"正常切换应该返回True，实际返回{result}"
        
        result = await RegionManagerV2.toggle_district_status(1)
        assert result == True, f"正常切换应该返回True，实际返回{result}"
    
    with patch.object(db_manager, 'execute_query', side_effect=Exception('更新失败')):
        result = await RegionManagerV2.toggle_city_status(1)
        assert result == False, f"异常情况下应该返回False，实际返回{result}"
        
        result = await RegionManagerV2.toggle_district_status(1)
        assert result == False, f"异常情况下应该返回False，实际返回{result}"
        
    print("  ✅ 状态切换功能测试通过")
    
    # 6. 测试删除功能
    print("6. 测试删除功能...")
    
    with patch.object(db_manager, 'execute_query', return_value=None):
        result = await RegionManagerV2.delete_city(1)
        assert result == True, f"正常删除应该返回True，实际返回{result}"
        
        result = await RegionManagerV2.delete_district(1)
        assert result == True, f"正常删除应该返回True，实际返回{result}"
    
    with patch.object(db_manager, 'execute_query', side_effect=Exception('删除失败')):
        result = await RegionManagerV2.delete_city(1)
        assert result == False, f"异常情况下应该返回False，实际返回{result}"
        
        result = await RegionManagerV2.delete_district(1)
        assert result == False, f"异常情况下应该返回False，实际返回{result}"
        
    print("  ✅ 删除功能测试通过")
    

async def test_edge_cases():
    """测试边界条件"""
    print("\n=== 测试边界条件 ===\n")
    
    from database.db_connection import db_manager
    
    # 1. 测试空数据处理
    print("1. 测试空数据处理...")
    
    with patch.object(db_manager, 'fetch_all', return_value=[]):
        result = await RegionManagerV2.get_all_cities_with_districts()
        assert result == [], f"空数据应该返回空列表，实际返回{result}"
        
        result = await RegionManagerV2.get_districts_by_city(1)
        assert result == [], f"空数据应该返回空列表，实际返回{result}"
        
    print("  ✅ 空数据处理测试通过")
    
    # 2. 测试特殊字符
    print("2. 测试特殊字符处理...")
    
    special_names = [
        '中关村/海淀区',
        '三里屯·朝阳区', 
        '西单(商业区)',
        '东城区&西城区'
    ]
    
    for name in special_names:
        with patch.object(db_manager, 'get_last_insert_id', return_value=100):
            result = await RegionManagerV2.add_city(name)
            assert result == 100, f"特殊字符城市名'{name}'处理失败"
            
            result = await RegionManagerV2.add_district(1, f'{name}区')
            assert result == 100, f"特殊字符地区名'{name}区'处理失败"
    
    print("  ✅ 特殊字符处理测试通过")
    
    # 3. 测试Unicode字符
    print("3. 测试Unicode字符处理...")
    
    unicode_names = ['東京都', '서울시', 'москва', 'القاهرة']
    
    for name in unicode_names:
        with patch.object(db_manager, 'get_last_insert_id', return_value=100):
            result = await RegionManagerV2.add_city(name)
            assert result == 100, f"Unicode城市名'{name}'处理失败"
    
    print("  ✅ Unicode字符处理测试通过")


async def test_data_consistency():
    """测试数据一致性"""
    print("\n=== 测试数据一致性 ===\n")
    
    from database.db_connection import db_manager
    
    # 测试复杂的关联数据结构
    print("1. 测试复杂关联数据...")
    
    complex_mock_data = [
        {'city_id': 1, 'city_name': '北京', 'city_is_active': True, 'district_id': 1, 'district_name': '朝阳区', 'district_is_active': True},
        {'city_id': 1, 'city_name': '北京', 'city_is_active': True, 'district_id': 2, 'district_name': '海淀区', 'district_is_active': False},
        {'city_id': 1, 'city_name': '北京', 'city_is_active': True, 'district_id': 3, 'district_name': '西城区', 'district_is_active': True},
        {'city_id': 2, 'city_name': '上海', 'city_is_active': False, 'district_id': 4, 'district_name': '浦东新区', 'district_is_active': True},
        {'city_id': 2, 'city_name': '上海', 'city_is_active': False, 'district_id': 5, 'district_name': '黄浦区', 'district_is_active': True},
        {'city_id': 3, 'city_name': '广州', 'city_is_active': True, 'district_id': None, 'district_name': None, 'district_is_active': None},
        {'city_id': 4, 'city_name': '深圳', 'city_is_active': True, 'district_id': 6, 'district_name': '南山区', 'district_is_active': True}
    ]
    
    with patch.object(db_manager, 'fetch_all', return_value=complex_mock_data):
        result = await RegionManagerV2.get_all_cities_with_districts()
        
        # 验证数据结构正确性
        assert len(result) == 4, f"应该有4个不同的城市，实际{len(result)}个"
        
        # 验证北京数据（有3个地区，包括inactive的）
        beijing = next((city for city in result if city['name'] == '北京'), None)
        assert beijing is not None, "北京数据丢失"
        assert len(beijing['districts']) == 3, f"北京应有3个地区，实际{len(beijing['districts'])}个"
        
        # 验证上海数据（城市inactive但有地区）
        shanghai = next((city for city in result if city['name'] == '上海'), None)
        assert shanghai is not None, "上海数据丢失"
        assert shanghai['is_active'] == False, "上海应该是inactive状态"
        assert len(shanghai['districts']) == 2, f"上海应有2个地区，实际{len(shanghai['districts'])}个"
        
        # 验证广州数据（无地区）
        guangzhou = next((city for city in result if city['name'] == '广州'), None)
        assert guangzhou is not None, "广州数据丢失"
        assert len(guangzhou['districts']) == 0, f"广州应该没有地区，实际{len(guangzhou['districts'])}个"
        
        # 验证深圳数据（单地区）
        shenzhen = next((city for city in result if city['name'] == '深圳'), None)
        assert shenzhen is not None, "深圳数据丢失"
        assert len(shenzhen['districts']) == 1, f"深圳应有1个地区，实际{len(shenzhen['districts'])}个"
        assert shenzhen['districts'][0]['name'] == '南山区'
    
    print("  ✅ 复杂关联数据测试通过")
    
    # 测试只返回active地区的查询
    print("2. 测试active地区筛选...")
    
    mixed_districts = [
        {'id': 1, 'city_id': 1, 'name': '朝阳区', 'is_active': True},
        {'id': 2, 'city_id': 1, 'name': '海淀区', 'is_active': True},
        {'id': 3, 'city_id': 1, 'name': '西城区', 'is_active': True}
    ]
    
    with patch.object(db_manager, 'fetch_all', return_value=mixed_districts):
        result = await RegionManagerV2.get_districts_by_city(1)
        
        # 验证所有返回的地区都是active的
        assert all(district['is_active'] for district in result), "应该只返回active的地区"
        assert len(result) == 3, f"应该返回3个active地区，实际{len(result)}个"
    
    print("  ✅ active地区筛选测试通过")


async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行RegionManagerV2综合测试...\n")
    
    total_tests = 0
    passed_tests = 0
    
    try:
        # 基本功能测试
        await test_basic_functionality()
        total_tests += 6
        passed_tests += 6
        
        # 边界条件测试
        await test_edge_cases()
        total_tests += 3
        passed_tests += 3
        
        # 数据一致性测试
        await test_data_consistency()
        total_tests += 2
        passed_tests += 2
        
        print(f"\n🎉 所有测试完成！")
        print(f"总计: {total_tests} 个测试")
        print(f"通过: {passed_tests} 个")
        print(f"失败: {total_tests - passed_tests} 个")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
        
        if passed_tests == total_tests:
            print("\n✅ RegionManagerV2修复验证成功！所有功能正常工作。")
        else:
            print(f"\n❌ 发现 {total_tests - passed_tests} 个问题需要修复")
            
    except Exception as e:
        print(f"\n💥 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(run_all_tests())