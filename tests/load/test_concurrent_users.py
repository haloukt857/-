"""
并发用户负载测试
测试系统在高并发情况下的性能和稳定性
"""

import pytest
import asyncio
import time
import random
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from database.db_merchants import MerchantManager as MerchantsDatabase
from database.db_orders import OrderManagerV2
from database.db_binding_codes import BindingCodesManager as BindingsDatabase
from database.db_logs import ActivityLogsDatabase
from middleware.throttling import ThrottlingMiddleware
from utils.health_monitor import HealthMonitor
from utils.error_recovery import ErrorRecoveryService


class TestConcurrentUserLoad:
    """并发用户负载测试"""
    
    @pytest.fixture
    async def load_test_merchants(self, db_manager):
        """创建负载测试用的商家"""
        merchants_db = MerchantsDatabase()
        merchant_ids = []
        
        for i in range(10):  # 创建10个测试商家
            merchant_data = {
                "chat_id": 1000000 + i,
                "name": f"负载测试商家{i+1}",
                "region": random.choice(["北京", "上海", "广州", "深圳", "杭州"]),
                "category": random.choice(["教育培训", "美容美发", "餐饮服务", "维修服务", "健康医疗"]),
                "contact_info": f"微信：load_test_{i}",
                "profile_data": {
                    "description": f"专业服务{i+1}",
                    "services": [f"服务A{i}", f"服务B{i}"],
                    "price_range": f"{100+i*50}-{200+i*50}元"
                }
            }
            merchant_id = await merchants_db.create_merchant(merchant_data)
            merchant_ids.append(merchant_id)
        
        return merchant_ids
    
    @pytest.mark.asyncio
    @pytest.mark.slow  # 标记为慢速测试
    async def test_concurrent_user_registration(self, db_manager):
        """测试并发用户访问商家列表"""
        
        async def simulate_user_access(user_id):
            """模拟单个用户访问"""
            try:
                merchants_db = MerchantsDatabase()
                
                # 模拟用户操作：获取商家列表
                start_time = time.time()
                merchants = await merchants_db.get_all_merchants()
                response_time = time.time() - start_time
                
                # 模拟选择商家
                if merchants:
                    selected_merchant = random.choice(merchants)
                    merchant_detail = await merchants_db.get_merchant(selected_merchant["id"])
                    
                    # 记录访问日志
                    logs_db = ActivityLogsDatabase()
                    await logs_db.log_button_click(user_id, f"merchant_{selected_merchant['id']}")
                    
                    return {
                        "user_id": user_id,
                        "success": True,
                        "response_time": response_time,
                        "merchant_selected": selected_merchant["id"]
                    }
                
                return {"user_id": user_id, "success": False, "error": "No merchants found"}
                
            except Exception as e:
                return {"user_id": user_id, "success": False, "error": str(e)}
        
        # 创建100个并发用户任务
        concurrent_users = 100
        user_ids = range(2000000, 2000000 + concurrent_users)
        
        start_time = time.time()
        
        # 分批执行以避免过度负载
        batch_size = 20
        all_results = []
        
        for i in range(0, concurrent_users, batch_size):
            batch_user_ids = list(user_ids)[i:i+batch_size]
            batch_tasks = [simulate_user_access(user_id) for user_id in batch_user_ids]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            all_results.extend(batch_results)
            
            # 短暂延迟以模拟真实场景
            await asyncio.sleep(0.1)
        
        total_time = time.time() - start_time
        
        # 分析结果
        successful_requests = [r for r in all_results if isinstance(r, dict) and r.get("success")]
        failed_requests = [r for r in all_results if isinstance(r, dict) and not r.get("success")]
        exceptions = [r for r in all_results if isinstance(r, Exception)]
        
        # 性能指标
        if successful_requests:
            avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests)
            max_response_time = max(r["response_time"] for r in successful_requests)
            min_response_time = min(r["response_time"] for r in successful_requests)
        else:
            avg_response_time = max_response_time = min_response_time = 0
        
        success_rate = len(successful_requests) / concurrent_users * 100
        
        print(f"负载测试结果:")
        print(f"并发用户数: {concurrent_users}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"成功率: {success_rate:.1f}%")
        print(f"平均响应时间: {avg_response_time:.3f}秒")
        print(f"最大响应时间: {max_response_time:.3f}秒")
        print(f"最小响应时间: {min_response_time:.3f}秒")
        print(f"失败请求数: {len(failed_requests)}")
        print(f"异常数: {len(exceptions)}")
        
        # 性能断言
        assert success_rate >= 95.0, f"成功率过低: {success_rate}%"
        assert avg_response_time < 2.0, f"平均响应时间过长: {avg_response_time}秒"
        assert max_response_time < 5.0, f"最大响应时间过长: {max_response_time}秒"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_order_creation(self, load_test_merchants, db_manager):
        """测试并发订单创建"""
        
        async def create_order_task(user_id, merchant_id):
            """创建订单任务"""
            try:
                order_manager_v2 = OrderManagerV2()
                
                start_time = time.time()
                order_data = {
                    "user_id": user_id,
                    "username": f"@load_user_{user_id}",
                    "merchant_id": merchant_id,
                    "order_type": random.choice(["appointment", "follow"]),
                    "price": random.uniform(100, 500) if random.choice([True, False]) else 0.00,
                    "status": "pending"
                }
                
                order_id = await order_manager_v2.create_order(order_data)
                response_time = time.time() - start_time
                
                return {
                    "user_id": user_id,
                    "merchant_id": merchant_id,
                    "order_id": order_id,
                    "success": True,
                    "response_time": response_time
                }
                
            except Exception as e:
                return {
                    "user_id": user_id,
                    "merchant_id": merchant_id,
                    "success": False,
                    "error": str(e)
                }
        
        # 创建200个并发订单
        concurrent_orders = 200
        tasks = []
        
        for i in range(concurrent_orders):
            user_id = 3000000 + i
            merchant_id = random.choice(load_test_merchants)
            task = create_order_task(user_id, merchant_id)
            tasks.append(task)
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # 分析结果
        successful_orders = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_orders = [r for r in results if isinstance(r, dict) and not r.get("success")]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_orders) / concurrent_orders * 100
        
        if successful_orders:
            avg_response_time = sum(r["response_time"] for r in successful_orders) / len(successful_orders)
            max_response_time = max(r["response_time"] for r in successful_orders)
        else:
            avg_response_time = max_response_time = 0
        
        print(f"并发订单创建测试结果:")
        print(f"并发订单数: {concurrent_orders}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"成功率: {success_rate:.1f}%")
        print(f"平均响应时间: {avg_response_time:.3f}秒")
        print(f"最大响应时间: {max_response_time:.3f}秒")
        print(f"失败订单数: {len(failed_orders)}")
        print(f"异常数: {len(exceptions)}")
        
        # 性能断言
        assert success_rate >= 90.0, f"订单创建成功率过低: {success_rate}%"
        assert avg_response_time < 1.0, f"平均订单创建时间过长: {avg_response_time}秒"
        
        # 验证数据完整性
        order_manager_v2 = OrderManagerV2()
        total_orders = 0
        for merchant_id in load_test_merchants:
            merchant_orders = await order_manager_v2.get_orders_by_merchant(merchant_id)
            total_orders += len(merchant_orders)
        
        assert total_orders >= len(successful_orders), "数据库中的订单数量与成功创建的不符"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_merchant_registration(self, db_manager):
        """测试并发商家注册"""
        
        # 先创建足够的绑定码
        bindings_db = BindingsDatabase()
        binding_codes = []
        for i in range(50):
            code = await bindings_db.generate_binding_code()
            binding_codes.append(code)
        
        async def merchant_registration_task(merchant_index, binding_code):
            """商家注册任务"""
            try:
                merchants_db = MerchantsDatabase()
                
                start_time = time.time()
                
                # 验证绑定码
                is_valid = await bindings_db.validate_binding_code(binding_code)
                if not is_valid:
                    return {
                        "merchant_index": merchant_index,
                        "success": False,
                        "error": "Invalid binding code"
                    }
                
                # 创建商家
                merchant_data = {
                    "chat_id": 4000000 + merchant_index,
                    "name": f"并发注册商家{merchant_index}",
                    "region": random.choice(["北京", "上海", "广州", "深圳"]),
                    "category": random.choice(["教育培训", "美容美发", "餐饮服务"]),
                    "contact_info": f"微信：concurrent_reg_{merchant_index}",
                    "profile_data": {
                        "description": f"并发注册测试商家{merchant_index}",
                        "services": [f"服务{merchant_index}"],
                        "price_range": "100-300元"
                    }
                }
                
                merchant_id = await merchants_db.create_merchant(merchant_data)
                
                # 使用绑定码
                await bindings_db.use_binding_code(binding_code, merchant_id)
                
                response_time = time.time() - start_time
                
                return {
                    "merchant_index": merchant_index,
                    "merchant_id": merchant_id,
                    "binding_code": binding_code,
                    "success": True,
                    "response_time": response_time
                }
                
            except Exception as e:
                return {
                    "merchant_index": merchant_index,
                    "success": False,
                    "error": str(e)
                }
        
        # 创建50个并发注册任务
        tasks = []
        for i, code in enumerate(binding_codes):
            task = merchant_registration_task(i, code)
            tasks.append(task)
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # 分析结果
        successful_registrations = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_registrations = [r for r in results if isinstance(r, dict) and not r.get("success")]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_registrations) / len(binding_codes) * 100
        
        if successful_registrations:
            avg_response_time = sum(r["response_time"] for r in successful_registrations) / len(successful_registrations)
        else:
            avg_response_time = 0
        
        print(f"并发商家注册测试结果:")
        print(f"并发注册数: {len(binding_codes)}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"成功率: {success_rate:.1f}%")
        print(f"平均响应时间: {avg_response_time:.3f}秒")
        print(f"失败注册数: {len(failed_registrations)}")
        print(f"异常数: {len(exceptions)}")
        
        # 性能断言
        assert success_rate >= 85.0, f"商家注册成功率过低: {success_rate}%"
        assert avg_response_time < 2.0, f"平均注册时间过长: {avg_response_time}秒"
        
        # 验证所有成功注册的绑定码都被使用
        for reg in successful_registrations:
            is_valid = await bindings_db.validate_binding_code(reg["binding_code"])
            assert not is_valid, f"绑定码 {reg['binding_code']} 应该已被使用"


class TestThrottlingUnderLoad:
    """限流中间件负载测试"""
    
    @pytest.mark.asyncio
    async def test_throttling_middleware_performance(self):
        """测试限流中间件性能"""
        
        throttling = ThrottlingMiddleware(
            default_rate=10,  # 每秒10个请求
            default_burst=5,  # 突发5个
            admin_rate=100,   # 管理员每秒100个
            cleanup_interval=30
        )
        
        async def mock_handler(event, data):
            # 模拟处理延迟
            await asyncio.sleep(random.uniform(0.001, 0.01))
            return "processed"
        
        async def simulate_user_requests(user_id, request_count):
            """模拟用户请求"""
            results = []
            
            for i in range(request_count):
                mock_event = MagicMock()
                mock_event.from_user.id = user_id
                
                try:
                    start_time = time.time()
                    result = await throttling(mock_handler, mock_event, {})
                    response_time = time.time() - start_time
                    
                    results.append({
                        "success": True,
                        "response_time": response_time,
                        "result": result
                    })
                    
                except Exception as e:
                    results.append({
                        "success": False,
                        "error": str(e)
                    })
                
                # 模拟请求间隔
                await asyncio.sleep(random.uniform(0.05, 0.2))
            
            return results
        
        # 模拟20个用户，每人发送15个请求
        user_count = 20
        requests_per_user = 15
        
        start_time = time.time()
        
        tasks = []
        for user_id in range(5000000, 5000000 + user_count):
            task = simulate_user_requests(user_id, requests_per_user)
            tasks.append(task)
        
        user_results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # 汇总结果
        all_results = []
        for user_result in user_results:
            all_results.extend(user_result)
        
        successful_requests = [r for r in all_results if r["success"]]
        failed_requests = [r for r in all_results if not r["success"]]
        
        success_rate = len(successful_requests) / len(all_results) * 100
        
        if successful_requests:
            avg_response_time = sum(r["response_time"] for r in successful_requests) / len(successful_requests)
        else:
            avg_response_time = 0
        
        total_requests = user_count * requests_per_user
        
        print(f"限流中间件负载测试结果:")
        print(f"用户数: {user_count}")
        print(f"每用户请求数: {requests_per_user}")
        print(f"总请求数: {total_requests}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"成功率: {success_rate:.1f}%")
        print(f"平均响应时间: {avg_response_time:.3f}秒")
        print(f"失败请求数: {len(failed_requests)}")
        
        # 限流应该起作用，不是所有请求都能成功
        # 但成功率应该合理（考虑到限流策略）
        assert 30 <= success_rate <= 80, f"限流效果异常，成功率: {success_rate}%"
        assert avg_response_time < 0.5, f"响应时间过长: {avg_response_time}秒"


class TestDatabasePerformance:
    """数据库性能负载测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_database_concurrent_operations(self, db_manager):
        """测试数据库并发操作性能"""
        
        async def concurrent_database_operations():
            """并发数据库操作"""
            operations = []
            
            # 模拟各种数据库操作
            merchants_db = MerchantsDatabase()
            order_manager_v2 = OrderManagerV2()
            logs_db = ActivityLogsDatabase()
            
            # 创建商家操作
            for i in range(20):
                merchant_data = {
                    "chat_id": 6000000 + i,
                    "name": f"DB性能测试商家{i}",
                    "region": "测试地区",
                    "category": "测试类别",
                    "contact_info": f"微信：db_perf_{i}"
                }
                operations.append(merchants_db.create_merchant(merchant_data))
            
            # 查询操作
            for i in range(30):
                operations.append(merchants_db.get_all_merchants())
            
            # 日志记录操作
            for i in range(50):
                operations.append(logs_db.log_button_click(6000000 + i, f"test_button_{i}"))
            
            return await asyncio.gather(*operations, return_exceptions=True)
        
        start_time = time.time()
        results = await concurrent_database_operations()
        total_time = time.time() - start_time
        
        # 分析结果
        successful_operations = [r for r in results if not isinstance(r, Exception)]
        failed_operations = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_operations) / len(results) * 100
        
        print(f"数据库并发操作测试结果:")
        print(f"总操作数: {len(results)}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"成功率: {success_rate:.1f}%")
        print(f"失败操作数: {len(failed_operations)}")
        print(f"平均每操作时间: {total_time/len(results):.3f}秒")
        
        # 性能断言
        assert success_rate >= 95.0, f"数据库操作成功率过低: {success_rate}%"
        assert total_time < 10.0, f"总执行时间过长: {total_time}秒"
        assert total_time / len(results) < 0.1, "平均每操作时间过长"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_database_connection_pool_stress(self, db_manager):
        """测试数据库连接池压力"""
        
        async def connection_stress_task(task_id):
            """连接压力测试任务"""
            try:
                # 执行多个快速查询
                queries = []
                for i in range(10):
                    query = f"SELECT {i} as test_value"
                    queries.append(db_manager.fetch_one(query))
                
                results = await asyncio.gather(*queries)
                return {"task_id": task_id, "success": True, "query_count": len(results)}
                
            except Exception as e:
                return {"task_id": task_id, "success": False, "error": str(e)}
        
        # 创建100个并发连接压力任务
        concurrent_tasks = 100
        tasks = [connection_stress_task(i) for i in range(concurrent_tasks)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        successful_tasks = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_tasks = [r for r in results if isinstance(r, dict) and not r.get("success")]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_tasks) / concurrent_tasks * 100
        
        print(f"数据库连接池压力测试结果:")
        print(f"并发任务数: {concurrent_tasks}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"成功率: {success_rate:.1f}%")
        print(f"失败任务数: {len(failed_tasks)}")
        print(f"异常数: {len(exceptions)}")
        
        # 连接池应该能处理合理的并发
        assert success_rate >= 90.0, f"连接池成功率过低: {success_rate}%"
        assert total_time < 15.0, f"总执行时间过长: {total_time}秒"


class TestSystemStabilityUnderLoad:
    """系统负载稳定性测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_memory_usage_under_load(self):
        """测试负载下的内存使用情况"""
        
        # 导入psutil（如果可用）
        try:
            import psutil
            process = psutil.Process()
            initial_memory = process.memory_info().rss
        except ImportError:
            pytest.skip("psutil not available for memory monitoring")
        
        async def memory_intensive_task(task_id):
            """内存密集型任务"""
            # 创建一些内存数据结构
            data = []
            for i in range(1000):
                data.append({
                    "id": f"{task_id}_{i}",
                    "data": "x" * 100,  # 100字符的字符串
                    "timestamp": datetime.now(),
                    "metadata": {"key": f"value_{i}"}
                })
            
            # 模拟数据处理
            processed = []
            for item in data:
                if item["id"].endswith("5"):  # 处理ID以5结尾的项目
                    processed.append(item)
            
            return len(processed)
        
        # 执行50个内存密集型任务
        tasks = [memory_intensive_task(i) for i in range(50)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        memory_increase_mb = memory_increase / 1024 / 1024
        
        print(f"内存使用负载测试结果:")
        print(f"任务数: {len(tasks)}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"初始内存: {initial_memory / 1024 / 1024:.2f} MB")
        print(f"最终内存: {final_memory / 1024 / 1024:.2f} MB")
        print(f"内存增长: {memory_increase_mb:.2f} MB")
        print(f"成功任务数: {len([r for r in results if isinstance(r, int)])}")
        
        # 内存使用应该在合理范围内
        assert memory_increase_mb < 100, f"内存增长过多: {memory_increase_mb:.2f} MB"
        assert len(results) == 50, "部分任务执行失败"
    
    @pytest.mark.asyncio
    async def test_error_recovery_under_load(self, mock_bot):
        """测试负载下的错误恢复"""
        
        error_service = ErrorRecoveryService(mock_bot)
        
        async def error_prone_task(task_id):
            """容易出错的任务"""
            # 30%的概率抛出错误
            if random.random() < 0.3:
                error_types = [
                    Exception("Database connection timeout"),
                    Exception("API rate limit exceeded"),
                    Exception("Network connection failed"),
                    Exception("Invalid input data")
                ]
                error = random.choice(error_types)
                await error_service.handle_error(error, {"task_id": task_id})
                raise error
            
            # 模拟正常处理
            await asyncio.sleep(random.uniform(0.01, 0.05))
            return f"success_{task_id}"
        
        # 执行100个容易出错的任务
        tasks = [error_prone_task(i) for i in range(100)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        successful_tasks = [r for r in results if isinstance(r, str) and r.startswith("success")]
        failed_tasks = [r for r in results if isinstance(r, Exception)]
        
        success_rate = len(successful_tasks) / len(tasks) * 100
        
        # 获取错误恢复统计
        error_stats = error_service.get_error_stats()
        
        print(f"错误恢复负载测试结果:")
        print(f"总任务数: {len(tasks)}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"成功率: {success_rate:.1f}%")
        print(f"失败任务数: {len(failed_tasks)}")
        print(f"错误恢复统计: {error_stats['total_errors']}个错误")
        
        # 错误恢复应该正常工作
        assert 60 <= success_rate <= 80, f"成功率异常: {success_rate}%"
        assert error_stats["total_errors"] > 0, "应该有错误被记录"
        assert total_time < 20.0, f"执行时间过长: {total_time}秒"
    
    @pytest.mark.asyncio
    async def test_health_monitoring_under_load(self, mock_bot):
        """测试负载下的健康监控"""
        
        health_monitor = HealthMonitor(mock_bot, check_interval=1)
        
        # 记录大量请求指标
        for i in range(1000):
            response_time = random.uniform(0.1, 2.0)
            success = random.random() > 0.1  # 90%成功率
            health_monitor.record_request_metric(response_time, success)
        
        # 获取健康摘要
        health_summary = health_monitor.get_health_summary()
        
        print(f"健康监控负载测试结果:")
        print(f"记录的请求数: {health_summary['metrics']['total_requests']}")
        print(f"失败请求数: {health_summary['metrics']['failed_requests']}")
        print(f"成功率: {health_summary['metrics']['success_rate']:.1f}%")
        print(f"平均响应时间: {health_summary['metrics']['avg_response_time']:.3f}秒")
        
        # 健康监控应该正确记录指标
        assert health_summary["metrics"]["total_requests"] == 1000
        assert 85 <= health_summary["metrics"]["success_rate"] <= 95
        assert 0.1 <= health_summary["metrics"]["avg_response_time"] <= 2.0


@pytest.mark.slow
class TestEndToEndLoadScenarios:
    """端到端负载场景测试"""
    
    @pytest.mark.asyncio
    async def test_peak_traffic_simulation(self, db_manager, mock_bot):
        """模拟高峰流量场景"""
        
        # 创建基础数据
        merchants_db = MerchantsDatabase()
        merchant_ids = []
        
        for i in range(5):
            merchant_data = {
                "chat_id": 7000000 + i,
                "name": f"高峰测试商家{i}",
                "region": "北京",
                "category": "教育培训",
                "contact_info": f"微信：peak_test_{i}"
            }
            merchant_id = await merchants_db.create_merchant(merchant_data)
            merchant_ids.append(merchant_id)
        
        async def peak_user_session(user_id):
            """模拟高峰期用户会话"""
            session_actions = []
            
            try:
                # 1. 获取商家列表
                merchants = await merchants_db.get_all_merchants()
                session_actions.append("list_merchants")
                
                # 2. 选择商家
                if merchants:
                    selected_merchant = random.choice(merchants)
                    merchant_detail = await merchants_db.get_merchant(selected_merchant["id"])
                    session_actions.append("view_merchant")
                    
                    # 3. 记录点击
                    logs_db = ActivityLogsDatabase()
                    await logs_db.log_button_click(user_id, f"merchant_{selected_merchant['id']}")
                    session_actions.append("log_click")
                    
                    # 4. 创建订单（50%概率）
                    if random.random() < 0.5:
                        order_manager_v2 = OrderManagerV2()
                        order_data = {
                            "user_id": user_id,
                            "username": f"@peak_user_{user_id}",
                            "merchant_id": selected_merchant["id"],
                            "order_type": random.choice(["appointment", "follow"]),
                            "price": random.uniform(100, 400) if random.random() > 0.3 else 0.00
                        }
                        await order_manager_v2.create_order(order_data)
                        session_actions.append("create_order")
                
                return {"user_id": user_id, "success": True, "actions": session_actions}
                
            except Exception as e:
                return {"user_id": user_id, "success": False, "error": str(e), "actions": session_actions}
        
        # 模拟500个并发用户的高峰流量
        peak_users = 500
        user_ids = range(8000000, 8000000 + peak_users)
        
        print(f"开始高峰流量模拟测试 ({peak_users}个并发用户)...")
        
        start_time = time.time()
        
        # 分批处理以避免系统过载
        batch_size = 50
        all_results = []
        
        for i in range(0, peak_users, batch_size):
            batch_user_ids = list(user_ids)[i:i+batch_size]
            batch_tasks = [peak_user_session(user_id) for user_id in batch_user_ids]
            
            batch_start = time.time()
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            batch_time = time.time() - batch_start
            
            all_results.extend(batch_results)
            
            print(f"批次 {i//batch_size + 1}/{(peak_users-1)//batch_size + 1} 完成，耗时: {batch_time:.2f}秒")
            
            # 批次间短暂延迟
            await asyncio.sleep(0.5)
        
        total_time = time.time() - start_time
        
        # 分析结果
        successful_sessions = [r for r in all_results if isinstance(r, dict) and r.get("success")]
        failed_sessions = [r for r in all_results if isinstance(r, dict) and not r.get("success")]
        exceptions = [r for r in all_results if isinstance(r, Exception)]
        
        success_rate = len(successful_sessions) / peak_users * 100
        
        # 统计行为
        action_counts = {}
        for session in successful_sessions:
            for action in session.get("actions", []):
                action_counts[action] = action_counts.get(action, 0) + 1
        
        print(f"\n高峰流量模拟测试结果:")
        print(f"总用户数: {peak_users}")
        print(f"总执行时间: {total_time:.2f}秒")
        print(f"成功率: {success_rate:.1f}%")
        print(f"失败会话数: {len(failed_sessions)}")
        print(f"异常数: {len(exceptions)}")
        print(f"平均会话处理时间: {total_time/peak_users:.3f}秒")
        print(f"用户行为统计:")
        for action, count in action_counts.items():
            print(f"  {action}: {count}次")
        
        # 高峰流量性能要求
        assert success_rate >= 80.0, f"高峰流量成功率过低: {success_rate}%"
        assert total_time < 120.0, f"总处理时间过长: {total_time}秒"
        assert total_time / peak_users < 0.5, "平均会话处理时间过长"
        
        # 验证数据完整性
        final_merchants = await merchants_db.get_all_merchants()
        assert len(final_merchants) >= 5, "商家数据完整性检查失败"
        
        # 检查订单创建情况
        total_orders = 0
        for merchant_id in merchant_ids:
            order_manager_v2 = OrderManagerV2()
            orders = await order_manager_v2.get_orders_by_merchant(merchant_id)
            total_orders += len(orders)
        
        expected_orders = action_counts.get("create_order", 0)
        assert total_orders >= expected_orders * 0.9, f"订单数据不一致: 期望>={expected_orders * 0.9}, 实际={total_orders}"
        
        print(f"数据完整性验证通过 - 总订单数: {total_orders}")


# 标记慢速测试的装饰器
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")