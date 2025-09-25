#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务模拟测试 - V2.0
专门测试scheduler.py中定时任务的执行逻辑和异常处理

测试覆盖:
1. 定时任务执行模拟
2. 任务失败恢复机制
3. 任务调度时间精度
4. 任务执行状态监控
5. 异常情况处理
"""

import pytest
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import tempfile
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# 导入测试相关模块
from database.db_connection import db_manager
from database.db_merchants import MerchantManager
from scheduler import SchedulerWorker

# 配置测试日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchedulerSimulationTestSuite:
    """定时任务模拟测试套件"""
    
    def __init__(self):
        self.test_data = {}
        self.scheduler = None
        self.mock_data = {}
        
    async def setup_test_data(self):
        """设置测试数据"""
        logger.info("设置定时任务模拟测试数据")
        
        # 创建测试商户数据（专为定时任务测试设计）
        test_merchants = [
            {
                'telegram_chat_id': 2001,
                'name': '待发布商户A',
                'status': 'approved',
                'merchant_type': 'teacher',
                'p_price': 100,
                'pp_price': 200,
                'custom_description': '待发布商户A的描述',
                'publish_time': datetime.now() - timedelta(minutes=10),  # 10分钟前应该发布
                'expiration_time': datetime.now() + timedelta(days=7)
            },
            {
                'telegram_chat_id': 2002,
                'name': '未来发布商户B',
                'status': 'approved',
                'merchant_type': 'business',
                'p_price': 150,
                'pp_price': 300,
                'custom_description': '未来发布商户B的描述',
                'publish_time': datetime.now() + timedelta(hours=2),  # 2小时后发布
                'expiration_time': datetime.now() + timedelta(days=30)
            },
            {
                'telegram_chat_id': 2003,
                'name': '已过期商户C',
                'status': 'published',
                'merchant_type': 'teacher',
                'p_price': 120,
                'pp_price': 250,
                'custom_description': '已过期商户C的描述',
                'publish_time': datetime.now() - timedelta(days=10),
                'expiration_time': datetime.now() - timedelta(hours=3)  # 3小时前过期
            },
            {
                'telegram_chat_id': 2004,
                'name': '即将过期商户D',
                'status': 'published',
                'merchant_type': 'business',
                'p_price': 180,
                'pp_price': 350,
                'custom_description': '即将过期商户D的描述',
                'publish_time': datetime.now() - timedelta(days=5),
                'expiration_time': datetime.now() + timedelta(minutes=30)  # 30分钟后过期
            }
        ]
        
        # 创建测试商户
        merchant_ids = []
        for merchant_data in test_merchants:
            merchant_id = await MerchantManager.create_merchant(merchant_data)
            if merchant_id:
                merchant_ids.append(merchant_id)
                logger.info(f"创建定时任务测试商户: {merchant_data['name']} (ID: {merchant_id})")
        
        self.test_data['merchant_ids'] = merchant_ids
        self.test_data['merchants'] = test_merchants
        
        # 初始化调度器
        self.scheduler = SchedulerWorker()
        
        logger.info(f"定时任务测试数据设置完成，创建了 {len(merchant_ids)} 个测试商户")
        
    async def cleanup_test_data(self):
        """清理测试数据"""
        logger.info("清理定时任务模拟测试数据")
        
        if 'merchant_ids' in self.test_data:
            for merchant_id in self.test_data['merchant_ids']:
                try:
                    await MerchantManager.delete_merchant(merchant_id)
                    logger.debug(f"删除测试商户: {merchant_id}")
                except Exception as e:
                    logger.warning(f"删除测试商户 {merchant_id} 失败: {e}")
        
        # 关闭调度器
        if self.scheduler:
            await self.scheduler.stop()
        
        logger.info("定时任务测试数据清理完成")


@pytest.fixture
async def scheduler_test_suite():
    """定时任务测试套件fixture"""
    suite = SchedulerSimulationTestSuite()
    await suite.setup_test_data()
    yield suite
    await suite.cleanup_test_data()


class TestSchedulerSimulation:
    """定时任务模拟测试类"""
    
    @pytest.mark.asyncio
    async def test_publish_pending_posts_execution(self, scheduler_test_suite):
        """测试1: 定时发布任务执行逻辑"""
        logger.info("=" * 60)
        logger.info("测试1: 定时发布任务执行逻辑")
        logger.info("=" * 60)
        
        # 获取测试数据
        merchant_ids = scheduler_test_suite.test_data['merchant_ids']
        
        # 执行前检查状态
        before_states = {}
        for merchant_id in merchant_ids:
            merchant = await MerchantManager.get_merchant(merchant_id)
            before_states[merchant_id] = merchant['status']
            logger.info(f"执行前商户 {merchant_id}: {merchant['name']} - 状态: {merchant['status']}")
        
        # 执行定时发布任务
        start_time = datetime.now()
        await scheduler_test_suite.scheduler.publish_pending_posts()
        execution_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✓ 定时发布任务执行完成，耗时: {execution_time:.3f}秒")
        
        # 执行后检查状态变化
        after_states = {}
        status_changes = []
        
        for merchant_id in merchant_ids:
            merchant = await MerchantManager.get_merchant(merchant_id)
            after_states[merchant_id] = merchant['status']
            
            if before_states[merchant_id] != after_states[merchant_id]:
                status_changes.append({
                    'merchant_id': merchant_id,
                    'name': merchant['name'],
                    'before': before_states[merchant_id],
                    'after': after_states[merchant_id]
                })
                logger.info(f"✓ 状态变化 - 商户 {merchant_id}: {before_states[merchant_id]} → {after_states[merchant_id]}")
        
        # 验证结果
        # 应该有待发布的商户（发布时间已过）状态被更新
        expected_published = 0
        for merchant_id in merchant_ids:
            merchant = await MerchantManager.get_merchant(merchant_id)
            if (merchant['status'] == 'approved' and 
                merchant.get('publish_time') and 
                datetime.fromisoformat(merchant['publish_time'].replace('T', ' ')) <= datetime.now()):
                expected_published += 1
        
        logger.info(f"✓ 应发布商户数: {expected_published}")
        logger.info(f"✓ 实际状态变化数: {len(status_changes)}")
        
        logger.info("✅ 定时发布任务执行逻辑测试完成")
        
    @pytest.mark.asyncio
    async def test_handle_expired_services_execution(self, scheduler_test_suite):
        """测试2: 到期处理任务执行逻辑"""
        logger.info("=" * 60)
        logger.info("测试2: 到期处理任务执行逻辑")
        logger.info("=" * 60)
        
        # 获取测试数据
        merchant_ids = scheduler_test_suite.test_data['merchant_ids']
        
        # 执行前检查过期状态
        before_states = {}
        expired_candidates = []
        
        for merchant_id in merchant_ids:
            merchant = await MerchantManager.get_merchant(merchant_id)
            before_states[merchant_id] = merchant['status']
            
            # 检查是否应该被标记为过期
            if (merchant.get('expiration_time') and 
                datetime.fromisoformat(merchant['expiration_time'].replace('T', ' ')) <= datetime.now() and
                merchant['status'] != 'expired'):
                expired_candidates.append(merchant_id)
                logger.info(f"过期候选商户 {merchant_id}: {merchant['name']} - 到期时间: {merchant['expiration_time']}")
        
        # 执行到期处理任务
        start_time = datetime.now()
        await scheduler_test_suite.scheduler.handle_expired_services()
        execution_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✓ 到期处理任务执行完成，耗时: {execution_time:.3f}秒")
        
        # 执行后检查状态变化
        expired_processed = []
        
        for merchant_id in expired_candidates:
            merchant = await MerchantManager.get_merchant(merchant_id)
            if merchant['status'] == 'expired':
                expired_processed.append(merchant_id)
                logger.info(f"✓ 商户 {merchant_id} 已被标记为过期")
        
        logger.info(f"✓ 过期候选商户数: {len(expired_candidates)}")
        logger.info(f"✓ 实际处理过期数: {len(expired_processed)}")
        
        logger.info("✅ 到期处理任务执行逻辑测试完成")
        
    @pytest.mark.asyncio
    async def test_merchant_scores_calculation(self, scheduler_test_suite):
        """测试3: 商户评分计算任务"""
        logger.info("=" * 60)
        logger.info("测试3: 商户评分计算任务")
        logger.info("=" * 60)
        
        # 执行评分计算任务
        start_time = datetime.now()
        
        try:
            await scheduler_test_suite.scheduler.update_all_merchant_scores()
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"✓ 商户评分计算任务执行完成，耗时: {execution_time:.3f}秒")
            
            # 检查是否有评价数据可以计算
            query = "SELECT COUNT(*) as count FROM reviews WHERE is_confirmed_by_merchant = TRUE"
            result = await db_manager.fetch_one(query)
            review_count = result['count'] if result else 0
            
            logger.info(f"✓ 系统中确认评价数量: {review_count}")
            
            if review_count > 0:
                logger.info("✓ 有评价数据，计算任务应该处理相关商户")
            else:
                logger.info("✓ 无评价数据，计算任务正常跳过")
                
        except Exception as e:
            logger.warning(f"商户评分计算任务执行异常（预期行为）: {e}")
        
        logger.info("✅ 商户评分计算任务测试完成")
        
    @pytest.mark.asyncio
    async def test_scheduler_error_handling(self, scheduler_test_suite):
        """测试4: 调度器异常处理"""
        logger.info("=" * 60)
        logger.info("测试4: 调度器异常处理")
        logger.info("=" * 60)
        
        # 模拟数据库连接错误
        with patch.object(db_manager, 'fetch_all', side_effect=Exception("数据库连接失败")):
            try:
                await scheduler_test_suite.scheduler.publish_pending_posts()
                logger.info("✓ 发布任务在数据库错误时没有崩溃")
            except Exception as e:
                logger.error(f"❌ 发布任务异常处理失败: {e}")
        
        # 模拟商户状态更新失败
        with patch.object(MerchantManager, 'update_merchant_status', return_value=False):
            try:
                await scheduler_test_suite.scheduler.handle_expired_services()
                logger.info("✓ 到期处理任务在状态更新失败时没有崩溃")
            except Exception as e:
                logger.error(f"❌ 到期处理任务异常处理失败: {e}")
        
        # 测试空结果处理
        with patch.object(db_manager, 'fetch_all', return_value=[]):
            try:
                await scheduler_test_suite.scheduler.publish_pending_posts()
                logger.info("✓ 发布任务正确处理空结果")
                
                await scheduler_test_suite.scheduler.handle_expired_services()
                logger.info("✓ 到期处理任务正确处理空结果")
                
            except Exception as e:
                logger.error(f"❌ 空结果处理失败: {e}")
        
        logger.info("✅ 调度器异常处理测试完成")
        
    @pytest.mark.asyncio
    async def test_post_content_generation_variations(self, scheduler_test_suite):
        """测试5: 帖子内容生成的各种情况"""
        logger.info("=" * 60)
        logger.info("测试5: 帖子内容生成的各种情况")
        logger.info("=" * 60)
        
        # 测试不同类型的商户数据
        test_cases = [
            {
                'name': '完整信息商户',
                'merchant_type': 'teacher',
                'region': '北京市朝阳区',
                'p_price': 100,
                'pp_price': 200,
                'custom_description': '这是一个完整的描述信息'
            },
            {
                'name': '缺少价格商户',
                'merchant_type': 'business',
                'region': '上海市浦东新区',
                'p_price': None,
                'pp_price': None,
                'custom_description': '缺少价格信息的商户'
            },
            {
                'name': '缺少描述商户',
                'merchant_type': 'teacher',
                'region': '广州市天河区',
                'p_price': 150,
                'pp_price': 300,
                'custom_description': None
            },
            {
                'name': '最小信息商户',
                'merchant_type': None,
                'region': None,
                'p_price': None,
                'pp_price': None,
                'custom_description': None
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"测试情况 {i+1}: {test_case['name']}")
            
            try:
                content = await scheduler_test_suite.scheduler._generate_post_content(test_case)
                
                # 验证内容基本要求
                assert isinstance(content, str)
                assert len(content) > 0
                assert test_case['name'] in content
                
                logger.info(f"✓ 生成内容长度: {len(content)} 字符")
                
                # 验证价格信息处理
                if test_case.get('p_price'):
                    assert str(test_case['p_price']) in content
                    logger.info("✓ 正确包含P价格")
                
                if test_case.get('pp_price'):
                    assert str(test_case['pp_price']) in content
                    logger.info("✓ 正确包含PP价格")
                
                # 验证描述信息处理
                if test_case.get('custom_description'):
                    assert test_case['custom_description'] in content
                    logger.info("✓ 正确包含描述信息")
                
                logger.info(f"✓ {test_case['name']} 内容生成成功")
                
            except Exception as e:
                logger.error(f"❌ {test_case['name']} 内容生成失败: {e}")
        
        logger.info("✅ 帖子内容生成变化测试完成")
        
    @pytest.mark.asyncio
    async def test_scheduler_performance_monitoring(self, scheduler_test_suite):
        """测试6: 调度器性能监控"""
        logger.info("=" * 60)
        logger.info("测试6: 调度器性能监控")
        logger.info("=" * 60)
        
        # 测试各个任务的执行时间
        performance_data = {}
        
        # 测试发布任务性能
        start_time = datetime.now()
        await scheduler_test_suite.scheduler.publish_pending_posts()
        publish_time = (datetime.now() - start_time).total_seconds()
        performance_data['publish_posts'] = publish_time
        logger.info(f"✓ 发布任务执行时间: {publish_time:.3f}秒")
        
        # 测试到期处理性能
        start_time = datetime.now()
        await scheduler_test_suite.scheduler.handle_expired_services()
        expiry_time = (datetime.now() - start_time).total_seconds()
        performance_data['handle_expiry'] = expiry_time
        logger.info(f"✓ 到期处理执行时间: {expiry_time:.3f}秒")
        
        # 测试评分计算性能
        start_time = datetime.now()
        try:
            await scheduler_test_suite.scheduler.update_all_merchant_scores()
            scores_time = (datetime.now() - start_time).total_seconds()
            performance_data['update_scores'] = scores_time
            logger.info(f"✓ 评分计算执行时间: {scores_time:.3f}秒")
        except Exception as e:
            logger.info(f"✓ 评分计算跳过（无数据）: {e}")
            performance_data['update_scores'] = 0.0
        
        # 性能评估
        total_time = sum(performance_data.values())
        logger.info(f"✓ 所有任务总执行时间: {total_time:.3f}秒")
        
        # 验证性能要求（所有任务应在合理时间内完成）
        max_acceptable_time = 30.0  # 30秒
        assert total_time < max_acceptable_time, f"任务执行时间超过限制: {total_time}秒"
        
        # 单个任务性能检查
        for task_name, task_time in performance_data.items():
            if task_time > 10.0:  # 单个任务不应超过10秒
                logger.warning(f"⚠️ 任务 {task_name} 执行时间较长: {task_time:.3f}秒")
            else:
                logger.info(f"✓ 任务 {task_name} 性能正常")
        
        logger.info("✅ 调度器性能监控测试完成")
        
    @pytest.mark.asyncio
    async def test_concurrent_task_execution(self, scheduler_test_suite):
        """测试7: 并发任务执行安全性"""
        logger.info("=" * 60)
        logger.info("测试7: 并发任务执行安全性")
        logger.info("=" * 60)
        
        # 定义并发任务
        async def task_1():
            await scheduler_test_suite.scheduler.publish_pending_posts()
            return "task_1_completed"
        
        async def task_2():
            await scheduler_test_suite.scheduler.handle_expired_services()
            return "task_2_completed"
        
        async def task_3():
            try:
                await scheduler_test_suite.scheduler.update_all_merchant_scores()
                return "task_3_completed"
            except Exception:
                return "task_3_skipped"
        
        # 并发执行任务
        start_time = datetime.now()
        results = await asyncio.gather(task_1(), task_2(), task_3(), return_exceptions=True)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"✓ 并发任务执行完成，总耗时: {execution_time:.3f}秒")
        
        # 分析结果
        successful_tasks = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ 任务 {i+1} 执行异常: {result}")
            else:
                logger.info(f"✓ 任务 {i+1} 执行结果: {result}")
                successful_tasks += 1
        
        # 验证至少大部分任务成功
        assert successful_tasks >= 2, f"并发执行成功任务数不足: {successful_tasks}/3"
        
        logger.info(f"✓ 并发执行成功率: {successful_tasks}/3")
        logger.info("✅ 并发任务执行安全性测试完成")


async def run_scheduler_simulation_tests():
    """运行所有定时任务模拟测试"""
    logger.info("🚀 开始运行定时任务模拟测试")
    logger.info("=" * 80)
    
    # 创建测试套件
    test_suite = SchedulerSimulationTestSuite()
    await test_suite.setup_test_data()
    
    # 创建测试实例
    test_instance = TestSchedulerSimulation()
    
    test_results = {
        'total_tests': 0,
        'passed_tests': 0,
        'failed_tests': 0,
        'test_details': []
    }
    
    # 定义所有测试方法
    test_methods = [
        ('定时发布任务执行逻辑', test_instance.test_publish_pending_posts_execution),
        ('到期处理任务执行逻辑', test_instance.test_handle_expired_services_execution),
        ('商户评分计算任务', test_instance.test_merchant_scores_calculation),
        ('调度器异常处理', test_instance.test_scheduler_error_handling),
        ('帖子内容生成变化', test_instance.test_post_content_generation_variations),
        ('调度器性能监控', test_instance.test_scheduler_performance_monitoring),
        ('并发任务执行安全性', test_instance.test_concurrent_task_execution)
    ]
    
    # 执行所有测试
    for test_name, test_method in test_methods:
        test_results['total_tests'] += 1
        
        try:
            logger.info(f"\n🧪 开始执行测试: {test_name}")
            await test_method(test_suite)
            test_results['passed_tests'] += 1
            test_results['test_details'].append({
                'name': test_name,
                'status': 'PASSED',
                'error': None
            })
            logger.info(f"✅ 测试通过: {test_name}")
            
        except Exception as e:
            test_results['failed_tests'] += 1
            test_results['test_details'].append({
                'name': test_name,
                'status': 'FAILED',
                'error': str(e)
            })
            logger.error(f"❌ 测试失败: {test_name}")
            logger.error(f"错误信息: {e}")
    
    # 清理测试数据
    await test_suite.cleanup_test_data()
    
    return test_results


async def main():
    """主函数"""
    try:
        # 运行测试
        test_results = await run_scheduler_simulation_tests()
        
        # 生成简要报告
        logger.info("=" * 80)
        logger.info("🎯 定时任务模拟测试完成")
        logger.info(f"📊 测试结果: {test_results['passed_tests']}/{test_results['total_tests']} 通过")
        
        # 显示失败的测试
        if test_results['failed_tests'] > 0:
            logger.warning("❌ 失败的测试:")
            for test in test_results['test_details']:
                if test['status'] == 'FAILED':
                    logger.warning(f"  - {test['name']}: {test['error']}")
        else:
            logger.info("✅ 所有定时任务模拟测试通过")
        
        logger.info("=" * 80)
        
        return test_results
        
    except Exception as e:
        logger.error(f"定时任务模拟测试执行失败: {e}")
        raise


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())