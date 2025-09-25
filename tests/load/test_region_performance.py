# -*- coding: utf-8 -*-
"""
RegionManagerV2 性能测试
测试大数据量下的性能表现和并发处理能力
"""

import asyncio
import time
import statistics
import sqlite3
import tempfile
import os
import sys
from concurrent.futures import ThreadPoolExecutor

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from database.db_regions import RegionManagerV2
from database.db_connection import db_manager


class RegionPerformanceTest:
    """地区管理器性能测试"""
    
    def __init__(self):
        self.test_db_path = None
        self.original_db_path = None
        self.performance_results = {}
    
    async def setup_performance_database(self):
        """设置性能测试数据库"""
        # 创建临时数据库文件
        fd, self.test_db_path = tempfile.mkstemp(suffix='_perf.db')
        os.close(fd)
        
        # 保存原始数据库路径
        self.original_db_path = getattr(db_manager, 'db_path', None)
        
        # 创建数据库连接
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        
        # 创建表结构并优化索引
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
            
            -- 性能优化索引
            CREATE INDEX idx_cities_name ON cities(name);
            CREATE INDEX idx_cities_is_active ON cities(is_active);
            CREATE INDEX idx_districts_city_id ON districts(city_id);
            CREATE INDEX idx_districts_name ON districts(name);
            CREATE INDEX idx_districts_is_active ON districts(is_active);
            CREATE INDEX idx_districts_city_active ON districts(city_id, is_active);
        ''')
        
        conn.commit()
        conn.close()
        
        # 设置db_manager使用测试数据库
        db_manager.db_path = self.test_db_path
        print(f"性能测试数据库创建于: {self.test_db_path}")
    
    async def cleanup_performance_database(self):
        """清理性能测试数据库"""
        if self.original_db_path is not None:
            db_manager.db_path = self.original_db_path
        
        if self.test_db_path and os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
            print("性能测试数据库已清理")
    
    async def measure_time(self, func, *args, **kwargs):
        """测量函数执行时间"""
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    
    async def test_bulk_insert_performance(self):
        """测试批量插入性能"""
        print("\n=== 测试批量插入性能 ===")
        
        # 测试不同数量级的城市插入
        city_counts = [10, 50, 100, 500]
        results = {}
        
        for count in city_counts:
            print(f"测试插入 {count} 个城市...")
            
            start_time = time.time()
            city_ids = []
            
            # 批量插入城市
            for i in range(count):
                city_id = await RegionManagerV2.add_city(f'性能测试城市{i:04d}')
                if city_id:
                    city_ids.append(city_id)
            
            end_time = time.time()
            insert_time = end_time - start_time
            
            results[f'{count}_cities'] = {
                'insert_time': insert_time,
                'success_count': len(city_ids),
                'avg_time_per_city': insert_time / count if count > 0 else 0
            }
            
            print(f"  插入 {len(city_ids)}/{count} 个城市，耗时 {insert_time:.3f}s，平均 {insert_time/count*1000:.2f}ms/城市")
            
            # 为每个城市添加地区
            districts_per_city = 5
            start_time = time.time()
            district_count = 0
            
            for city_id in city_ids[:min(50, len(city_ids))]:  # 限制城市数量以避免测试时间过长
                for j in range(districts_per_city):
                    district_id = await RegionManagerV2.add_district(city_id, f'地区{j:02d}')
                    if district_id:
                        district_count += 1
            
            end_time = time.time()
            district_insert_time = end_time - start_time
            
            results[f'{count}_districts'] = {
                'insert_time': district_insert_time,
                'success_count': district_count,
                'avg_time_per_district': district_insert_time / (districts_per_city * min(50, count)) if count > 0 else 0
            }
            
            print(f"  插入 {district_count} 个地区，耗时 {district_insert_time:.3f}s")
        
        self.performance_results['bulk_insert'] = results
        return results
    
    async def test_query_performance(self):
        """测试查询性能"""
        print("\n=== 测试查询性能 ===")
        
        # 先准备测试数据
        city_ids = []
        for i in range(100):
            city_id = await RegionManagerV2.add_city(f'查询测试城市{i:03d}')
            if city_id:
                city_ids.append(city_id)
                # 每个城市添加10个地区
                for j in range(10):
                    await RegionManagerV2.add_district(city_id, f'查询测试地区{j:02d}')
        
        print(f"准备了 {len(city_ids)} 个城市的测试数据")
        
        # 测试查询性能
        query_results = {}
        
        # 1. 测试获取所有城市和地区
        print("1. 测试获取所有城市和地区...")
        times = []
        for _ in range(10):  # 运行10次取平均值
            _, exec_time = await self.measure_time(RegionManagerV2.get_all_cities_with_districts)
            times.append(exec_time)
        
        query_results['get_all_cities_with_districts'] = {
            'avg_time': statistics.mean(times),
            'min_time': min(times),
            'max_time': max(times),
            'std_dev': statistics.stdev(times) if len(times) > 1 else 0
        }
        
        print(f"  平均耗时: {statistics.mean(times):.3f}s")
        
        # 2. 测试按城市ID查询地区
        print("2. 测试按城市ID查询地区...")
        times = []
        for city_id in city_ids[:20]:  # 测试前20个城市
            _, exec_time = await self.measure_time(RegionManagerV2.get_districts_by_city, city_id)
            times.append(exec_time)
        
        query_results['get_districts_by_city'] = {
            'avg_time': statistics.mean(times),
            'min_time': min(times),
            'max_time': max(times),
            'std_dev': statistics.stdev(times) if len(times) > 1 else 0
        }
        
        print(f"  平均耗时: {statistics.mean(times):.3f}s")
        
        self.performance_results['query_performance'] = query_results
        return query_results
    
    async def test_concurrent_operations(self):
        """测试并发操作性能"""
        print("\n=== 测试并发操作性能 ===")
        
        concurrent_results = {}
        
        # 测试并发插入城市
        print("1. 测试并发插入城市...")
        city_count = 50
        
        start_time = time.time()
        
        # 创建并发任务
        tasks = []
        for i in range(city_count):
            task = RegionManagerV2.add_city(f'并发测试城市{i:03d}')
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        concurrent_time = end_time - start_time
        
        successful_inserts = sum(1 for r in results if isinstance(r, int) and r is not None)
        
        concurrent_results['concurrent_city_insert'] = {
            'total_time': concurrent_time,
            'successful_inserts': successful_inserts,
            'total_tasks': city_count,
            'avg_time_per_task': concurrent_time / city_count
        }
        
        print(f"  并发插入 {successful_inserts}/{city_count} 个城市，总耗时 {concurrent_time:.3f}s")
        
        # 测试并发查询
        print("2. 测试并发查询...")
        query_count = 30
        
        start_time = time.time()
        
        # 创建并发查询任务
        tasks = []
        for _ in range(query_count):
            task = RegionManagerV2.get_all_cities_with_districts()
            tasks.append(task)
        
        # 等待所有任务完成
        query_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        concurrent_query_time = end_time - start_time
        
        successful_queries = sum(1 for r in query_results if isinstance(r, list))
        
        concurrent_results['concurrent_query'] = {
            'total_time': concurrent_query_time,
            'successful_queries': successful_queries,
            'total_queries': query_count,
            'avg_time_per_query': concurrent_query_time / query_count
        }
        
        print(f"  并发执行 {successful_queries}/{query_count} 个查询，总耗时 {concurrent_query_time:.3f}s")
        
        self.performance_results['concurrent_operations'] = concurrent_results
        return concurrent_results
    
    async def test_stress_operations(self):
        """测试压力操作"""
        print("\n=== 测试压力操作 ===")
        
        stress_results = {}
        
        # 压力测试：大量数据查询
        print("1. 准备大量测试数据...")
        city_ids = []
        for i in range(200):  # 200个城市
            city_id = await RegionManagerV2.add_city(f'压力测试城市{i:04d}')
            if city_id:
                city_ids.append(city_id)
                # 每个城市20个地区
                for j in range(20):
                    await RegionManagerV2.add_district(city_id, f'压力测试地区{j:03d}')
        
        print(f"  准备了 {len(city_ids)} 个城市，约 {len(city_ids) * 20} 个地区")
        
        # 测试大数据量查询
        print("2. 测试大数据量查询...")
        start_time = time.time()
        all_cities = await RegionManagerV2.get_all_cities_with_districts()
        query_time = time.time() - start_time
        
        total_districts = sum(len(city['districts']) for city in all_cities)
        
        stress_results['large_dataset_query'] = {
            'query_time': query_time,
            'cities_count': len(all_cities),
            'districts_count': total_districts,
            'time_per_city': query_time / len(all_cities) if all_cities else 0
        }
        
        print(f"  查询 {len(all_cities)} 城市 {total_districts} 地区，耗时 {query_time:.3f}s")
        
        # 测试批量状态切换
        print("3. 测试批量状态切换...")
        toggle_times = []
        
        # 切换前50个城市的状态
        for city_id in city_ids[:50]:
            start_time = time.time()
            await RegionManagerV2.toggle_city_status(city_id)
            toggle_time = time.time() - start_time
            toggle_times.append(toggle_time)
        
        stress_results['batch_status_toggle'] = {
            'avg_toggle_time': statistics.mean(toggle_times),
            'total_toggles': len(toggle_times),
            'min_time': min(toggle_times),
            'max_time': max(toggle_times)
        }
        
        print(f"  批量切换 {len(toggle_times)} 个城市状态，平均耗时 {statistics.mean(toggle_times):.4f}s")
        
        self.performance_results['stress_operations'] = stress_results
        return stress_results
    
    async def test_memory_usage(self):
        """测试内存使用情况"""
        print("\n=== 测试内存使用情况 ===")
        
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # 记录初始内存使用
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 执行大量操作
            city_ids = []
            for i in range(500):
                city_id = await RegionManagerV2.add_city(f'内存测试城市{i:04d}')
                if city_id:
                    city_ids.append(city_id)
            
            # 记录操作后内存使用
            after_insert_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # 执行大量查询
            for _ in range(100):
                await RegionManagerV2.get_all_cities_with_districts()
            
            # 记录查询后内存使用
            after_query_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            memory_results = {
                'initial_memory_mb': initial_memory,
                'after_insert_memory_mb': after_insert_memory,
                'after_query_memory_mb': after_query_memory,
                'insert_memory_increase_mb': after_insert_memory - initial_memory,
                'query_memory_increase_mb': after_query_memory - after_insert_memory
            }
            
            print(f"  初始内存: {initial_memory:.2f}MB")
            print(f"  插入后内存: {after_insert_memory:.2f}MB (+{after_insert_memory - initial_memory:.2f}MB)")
            print(f"  查询后内存: {after_query_memory:.2f}MB (+{after_query_memory - after_insert_memory:.2f}MB)")
            
            self.performance_results['memory_usage'] = memory_results
            
        except ImportError:
            print("  psutil 未安装，跳过内存测试")
            self.performance_results['memory_usage'] = {'error': 'psutil not available'}
    
    def generate_performance_report(self):
        """生成性能测试报告"""
        print("\n" + "="*60)
        print("RegionManagerV2 性能测试报告")
        print("="*60)
        
        for test_name, results in self.performance_results.items():
            print(f"\n{test_name.upper()}:")
            print("-" * 40)
            
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, dict):
                        print(f"  {key}:")
                        for subkey, subvalue in value.items():
                            if isinstance(subvalue, float):
                                print(f"    {subkey}: {subvalue:.4f}")
                            else:
                                print(f"    {subkey}: {subvalue}")
                    elif isinstance(value, float):
                        print(f"  {key}: {value:.4f}")
                    else:
                        print(f"  {key}: {value}")
        
        print("\n" + "="*60)
    
    async def run_all_performance_tests(self):
        """运行所有性能测试"""
        print("开始运行 RegionManagerV2 性能测试...")
        
        try:
            await self.setup_performance_database()
            
            # 批量插入性能测试
            await self.test_bulk_insert_performance()
            
            # 查询性能测试
            await self.test_query_performance()
            
            # 并发操作测试
            await self.test_concurrent_operations()
            
            # 压力测试
            await self.test_stress_operations()
            
            # 内存使用测试
            await self.test_memory_usage()
            
            # 生成报告
            self.generate_performance_report()
            
            print("\n🚀 性能测试完成！")
            
        except Exception as e:
            print(f"\n💥 性能测试失败: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await self.cleanup_performance_database()


# 直接运行性能测试
if __name__ == '__main__':
    async def main():
        performance_test = RegionPerformanceTest()
        await performance_test.run_all_performance_tests()
    
    asyncio.run(main())