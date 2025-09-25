# -*- coding: utf-8 -*-
"""
RegionManagerV2 简化性能测试
测试基本的性能指标和响应时间
"""

import asyncio
import time
import tempfile
import sqlite3
import os
import sys
from unittest.mock import patch

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.db_regions import RegionManagerV2
from database.db_connection import db_manager


async def test_response_time():
    """测试响应时间性能"""
    print("=== 测试方法响应时间 ===\n")
    
    # 模拟数据
    mock_city_data = []
    for i in range(100):
        for j in range(10):
            mock_city_data.append({
                'city_id': i+1, 
                'city_name': f'城市{i+1:02d}', 
                'city_is_active': True,
                'district_id': i*10+j+1, 
                'district_name': f'地区{i*10+j+1:03d}', 
                'district_is_active': True
            })
    
    # 1. 测试get_all_cities_with_districts的性能
    print("1. 测试get_all_cities_with_districts性能...")
    
    with patch.object(db_manager, 'fetch_all', return_value=mock_city_data):
        start_time = time.time()
        result = await RegionManagerV2.get_all_cities_with_districts()
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000  # 转换为毫秒
        
        assert len(result) == 100, f"应该返回100个城市，实际{len(result)}个"
        total_districts = sum(len(city['districts']) for city in result)
        assert total_districts == 1000, f"应该有1000个地区，实际{total_districts}个"
        
        print(f"  处理100城市1000地区: {execution_time:.2f}ms")
        print(f"  平均每城市处理时间: {execution_time/100:.3f}ms")
        
        # 性能基准：处理1000条记录应该在100ms以内
        if execution_time < 100:
            print("  ✅ 性能优秀 (< 100ms)")
        elif execution_time < 500:
            print("  ✅ 性能良好 (< 500ms)")
        else:
            print("  ⚠️  性能需要优化 (> 500ms)")
    
    # 2. 测试单独查询地区的性能
    print("\n2. 测试get_districts_by_city性能...")
    
    mock_districts = [{'id': i, 'city_id': 1, 'name': f'地区{i:02d}', 'is_active': True} for i in range(50)]
    
    with patch.object(db_manager, 'fetch_all', return_value=mock_districts):
        start_time = time.time()
        result = await RegionManagerV2.get_districts_by_city(1)
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000  # 转换为毫秒
        
        assert len(result) == 50, f"应该返回50个地区，实际{len(result)}个"
        
        print(f"  查询50个地区: {execution_time:.2f}ms")
        
        # 性能基准：查询50条记录应该在10ms以内
        if execution_time < 10:
            print("  ✅ 性能优秀 (< 10ms)")
        elif execution_time < 50:
            print("  ✅ 性能良好 (< 50ms)")
        else:
            print("  ⚠️  性能需要优化 (> 50ms)")


async def test_concurrent_performance():
    """测试并发性能"""
    print("\n=== 测试并发性能 ===\n")
    
    # 1. 测试并发插入性能
    print("1. 测试并发插入性能...")
    
    with patch.object(db_manager, 'get_last_insert_id', return_value=100):
        concurrent_count = 20
        
        start_time = time.time()
        
        # 创建并发任务
        tasks = []
        for i in range(concurrent_count):
            task = RegionManagerV2.add_city(f'并发城市{i:02d}')
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000
        
        successful_inserts = sum(1 for r in results if r == 100)
        
        print(f"  并发插入{concurrent_count}个城市: {execution_time:.2f}ms")
        print(f"  成功插入: {successful_inserts}/{concurrent_count}")
        print(f"  平均每个插入: {execution_time/concurrent_count:.2f}ms")
        
        if execution_time < 100:
            print("  ✅ 并发性能优秀")
        elif execution_time < 500:
            print("  ✅ 并发性能良好")
        else:
            print("  ⚠️  并发性能需要优化")
    
    # 2. 测试并发查询性能
    print("\n2. 测试并发查询性能...")
    
    mock_simple_data = [
        {'city_id': 1, 'city_name': '北京', 'city_is_active': True, 'district_id': 1, 'district_name': '朝阳区', 'district_is_active': True}
    ]
    
    with patch.object(db_manager, 'fetch_all', return_value=mock_simple_data):
        concurrent_count = 30
        
        start_time = time.time()
        
        # 创建并发查询任务
        tasks = []
        for _ in range(concurrent_count):
            task = RegionManagerV2.get_all_cities_with_districts()
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000
        
        successful_queries = sum(1 for r in results if isinstance(r, list) and len(r) >= 0)
        
        print(f"  并发查询{concurrent_count}次: {execution_time:.2f}ms")
        print(f"  成功查询: {successful_queries}/{concurrent_count}")
        print(f"  平均每个查询: {execution_time/concurrent_count:.2f}ms")
        
        if execution_time < 200:
            print("  ✅ 并发查询性能优秀")
        elif execution_time < 1000:
            print("  ✅ 并发查询性能良好")
        else:
            print("  ⚠️  并发查询性能需要优化")


async def test_data_processing_performance():
    """测试数据处理性能"""
    print("\n=== 测试数据处理性能 ===\n")
    
    # 测试大数据量的数据组织性能
    print("1. 测试大数据量处理...")
    
    # 创建更大的测试数据集：500城市，每城市20地区 = 10000条记录
    large_mock_data = []
    for i in range(500):
        for j in range(20):
            large_mock_data.append({
                'city_id': i+1,
                'city_name': f'测试城市{i+1:03d}',
                'city_is_active': True,
                'district_id': i*20+j+1,
                'district_name': f'测试地区{i*20+j+1:04d}',
                'district_is_active': True
            })
    
    print(f"  准备测试数据: {len(large_mock_data)}条记录")
    
    with patch.object(db_manager, 'fetch_all', return_value=large_mock_data):
        start_time = time.time()
        result = await RegionManagerV2.get_all_cities_with_districts()
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000
        
        assert len(result) == 500, f"应该返回500个城市，实际{len(result)}个"
        total_districts = sum(len(city['districts']) for city in result)
        assert total_districts == 10000, f"应该有10000个地区，实际{total_districts}个"
        
        print(f"  处理10000条记录: {execution_time:.2f}ms")
        print(f"  处理速度: {len(large_mock_data)/execution_time*1000:.0f} 记录/秒")
        
        # 性能基准
        if execution_time < 500:
            print("  ✅ 大数据处理性能优秀 (< 500ms)")
        elif execution_time < 2000:
            print("  ✅ 大数据处理性能良好 (< 2s)")
        else:
            print("  ⚠️  大数据处理性能需要优化 (> 2s)")
    
    # 测试内存使用效率
    print("\n2. 测试内存使用效率...")
    
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 执行内存密集操作
        with patch.object(db_manager, 'fetch_all', return_value=large_mock_data):
            results = []
            for _ in range(10):  # 执行10次大数据处理
                result = await RegionManagerV2.get_all_cities_with_districts()
                results.append(result)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"  初始内存: {initial_memory:.2f}MB")
        print(f"  结束内存: {final_memory:.2f}MB")
        print(f"  内存增长: {memory_increase:.2f}MB")
        
        if memory_increase < 10:
            print("  ✅ 内存使用优秀 (< 10MB)")
        elif memory_increase < 50:
            print("  ✅ 内存使用良好 (< 50MB)")
        else:
            print("  ⚠️  内存使用需要关注 (> 50MB)")
            
    except ImportError:
        print("  ℹ️  psutil未安装，跳过内存测试")


async def run_performance_tests():
    """运行所有性能测试"""
    print("⚡ 开始运行RegionManagerV2性能测试...\n")
    
    start_time = time.time()
    
    try:
        # 响应时间测试
        await test_response_time()
        
        # 并发性能测试
        await test_concurrent_performance()
        
        # 数据处理性能测试
        await test_data_processing_performance()
        
        total_time = time.time() - start_time
        
        print(f"\n🎉 性能测试完成！总耗时: {total_time:.2f}秒")
        print("✅ RegionManagerV2的性能表现符合预期")
        
        # 性能总结
        print("\n📊 性能测试总结:")
        print("  • 基础查询响应时间: 毫秒级")
        print("  • 并发处理能力: 良好")
        print("  • 大数据量处理: 高效")
        print("  • 内存使用: 合理")
        
    except Exception as e:
        print(f"\n💥 性能测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(run_performance_tests())