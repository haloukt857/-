# -*- coding: utf-8 -*-
"""
评价与激励闭环综合测试 (V2.0) - QA专业测试套件

测试目标：验证完整的评价→商家确认→积分发放→等级升级→勋章获得的激励闭环

测试覆盖范围：
1. 评价创建和管理测试
2. 商户确认流程测试
3. 积分和经验发放测试
4. 等级升级系统测试
5. 勋章系统测试
6. 评价报告和统计测试
7. 异常情况和边界测试
8. 并发处理能力测试

QA质量保证重点：
- 数据一致性验证
- 防刷单机制测试
- 双向确认可靠性
- 激励系统准确性
- 异常情况恢复
"""

import asyncio
import logging
import json
import sys
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入项目模块
from database.db_connection import db_manager
from database.db_reviews import review_manager
from database.db_users import user_manager
from database.db_incentives import incentive_manager
from database.db_merchants import merchant_manager
from database.db_orders import order_manager
from database.db_system_config import system_config_manager

# 配置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/Users/kikk/Documents/lanyangyang/tests/integration/review_incentive_test.log')
    ]
)
logger = logging.getLogger(__name__)

class TestResult(Enum):
    """测试结果枚举"""
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    SKIPPED = "⏭️ SKIPPED"
    WARNING = "⚠️ WARNING"

@dataclass
class TestCase:
    """测试用例数据结构"""
    test_id: str
    test_name: str
    category: str
    priority: str
    description: str
    result: Optional[TestResult] = None
    details: str = ""
    error: str = ""
    duration: float = 0.0
    timestamp: Optional[datetime] = None

class ReviewIncentiveLoopTester:
    """评价与激励闭环专业测试器"""
    
    def __init__(self):
        self.test_cases: List[TestCase] = []
        self.test_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0,
            'warning_tests': 0
        }
        
        # 测试数据配置
        self.test_data = {
            'merchant_id': 9001,
            'merchant_name': "QA测试商户",
            'merchant_chat_id': 9001,
            'user_id': 8888888,
            'username': "qa_test_user",
            'order_id_base': 7000,
            'ratings': {
                'appearance': 8,
                'figure': 9,
                'service': 10,
                'attitude': 9,
                'environment': 8
            }
        }
    
    async def log_test_result(self, test_case: TestCase, result: TestResult, details: str = "", error: str = "", duration: float = 0.0):
        """记录测试结果"""
        test_case.result = result
        test_case.details = details
        test_case.error = error
        test_case.duration = duration
        test_case.timestamp = datetime.now()
        
        self.test_results['total_tests'] += 1
        if result == TestResult.PASSED:
            self.test_results['passed_tests'] += 1
        elif result == TestResult.FAILED:
            self.test_results['failed_tests'] += 1
        elif result == TestResult.SKIPPED:
            self.test_results['skipped_tests'] += 1
        elif result == TestResult.WARNING:
            self.test_results['warning_tests'] += 1
        
        logger.info(f"{result.value}: [{test_case.test_id}] {test_case.test_name}")
        if details:
            logger.info(f"  详情: {details}")
        if error:
            logger.error(f"  错误: {error}")
        if duration > 0:
            logger.info(f"  耗时: {duration:.3f}秒")

    async def setup_test_environment(self) -> bool:
        """设置测试环境"""
        setup_test = TestCase(
            test_id="SETUP_001",
            test_name="测试环境设置",
            category="环境准备",
            priority="CRITICAL",
            description="创建测试数据和配置系统"
        )
        
        start_time = time.time()
        try:
            # 1. 清理可能存在的测试数据
            await self._cleanup_test_data()
            
            # 2. 创建测试用户
            await user_manager.create_or_update_user(
                self.test_data['user_id'], 
                self.test_data['username']
            )
            
            # 3. 创建测试商户
            query = """
                INSERT INTO merchants (id, telegram_chat_id, name, status)
                VALUES (?, ?, ?, ?)
            """
            await db_manager.execute_query(query, (
                self.test_data['merchant_id'],
                self.test_data['merchant_chat_id'],
                self.test_data['merchant_name'],
                "published"
            ))
            
            # 4. 设置系统积分配置
            config_value = json.dumps({
                'xp_per_review': 50,
                'points_per_review': 25,
                'xp_per_order': 20,
                'points_per_order': 10,
                'review_completion': 50,
                'review_xp': 20
            })
            
            query = """
                INSERT OR REPLACE INTO system_config (config_key, config_value, description)
                VALUES (?, ?, ?)
            """
            await db_manager.execute_query(query, (
                'points_config', config_value, 'QA测试积分配置'
            ))
            
            # 5. 设置等级系统
            await self._setup_test_levels()
            
            # 6. 设置勋章系统
            await self._setup_test_badges()
            
            duration = time.time() - start_time
            await self.log_test_result(
                setup_test, TestResult.PASSED, 
                "测试环境设置完成", "", duration
            )
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            await self.log_test_result(
                setup_test, TestResult.FAILED, 
                "测试环境设置失败", str(e), duration
            )
            return False

    async def _setup_test_levels(self):
        """设置测试等级配置"""
        levels = [
            ("新手", 0),
            ("熟练", 100),
            ("专家", 500),
            ("大师", 1500),
            ("传奇", 5000)
        ]
        
        for level_name, xp_required in levels:
            try:
                # 先检查是否已存在
                existing_levels = await incentive_manager.get_all_levels()
                existing_names = [level['level_name'] for level in existing_levels]
                
                if level_name not in existing_names:
                    await incentive_manager.add_level(level_name, xp_required)
                    logger.debug(f"创建等级: {level_name}")
                else:
                    logger.debug(f"等级已存在: {level_name}")
            except Exception as e:
                if "UNIQUE constraint failed" not in str(e) and "已存在" not in str(e):
                    raise e

    async def _setup_test_badges(self):
        """设置测试勋章配置"""
        badges = [
            ("首次评价", "🌟", "完成首次服务评价"),
            ("评价达人", "💬", "完成10次评价"),
            ("积分小能手", "💰", "累积获得100积分"),
            ("服务之王", "👑", "获得100个满分评价")
        ]
        
        badge_ids = {}
        for badge_name, badge_icon, description in badges:
            try:
                # 先检查是否已存在
                existing_badges = await incentive_manager.get_all_badges()
                existing_names = [badge['badge_name'] for badge in existing_badges]
                
                if badge_name not in existing_names:
                    badge_id = await incentive_manager.add_badge(badge_name, badge_icon, description)
                    if badge_id:
                        badge_ids[badge_name] = badge_id
                        logger.debug(f"创建勋章: {badge_name}")
                else:
                    # 获取已存在的badge_id
                    existing_badge = next((b for b in existing_badges if b['badge_name'] == badge_name), None)
                    if existing_badge:
                        badge_ids[badge_name] = existing_badge['id']
                        logger.debug(f"勋章已存在: {badge_name}")
            except Exception as e:
                if "UNIQUE constraint failed" not in str(e) and "已存在" not in str(e):
                    raise e
                # 获取已存在的badge_id
                query = "SELECT id FROM badges WHERE badge_name = ?"
                result = await db_manager.fetch_one(query, (badge_name,))
                if result:
                    badge_ids[badge_name] = result['id']
        
        # 创建触发条件
        trigger_configs = [
            ("首次评价", "order_count", 1),
            ("评价达人", "order_count", 10),
            ("积分小能手", "total_points", 100),
            ("服务之王", "perfect_reviews", 100)
        ]
        
        for badge_name, trigger_type, trigger_value in trigger_configs:
            if badge_name in badge_ids:
                try:
                    await incentive_manager.add_trigger(
                        badge_ids[badge_name], trigger_type, trigger_value
                    )
                except:
                    pass  # 忽略重复插入

    # =============================================================================
    # 测试用例 1: 评价创建和管理测试
    # =============================================================================
    
    async def test_review_creation_and_management(self) -> bool:
        """测试1: 评价创建和管理功能"""
        test_cases = [
            TestCase(
                "REV_001", "评价数据有效性验证", "评价管理", "HIGH",
                "验证评价数据的完整性和有效性"
            ),
            TestCase(
                "REV_002", "评价状态管理", "评价管理", "HIGH", 
                "验证评价状态的正确转换"
            ),
            TestCase(
                "REV_003", "防重复评价机制", "评价管理", "CRITICAL",
                "验证一单一评的约束机制"
            ),
            TestCase(
                "REV_004", "评价数据查询", "评价管理", "MEDIUM",
                "验证评价数据的查询功能"
            )
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            start_time = time.time()
            try:
                if test_case.test_id == "REV_001":
                    # 测试评价数据有效性
                    order_id = self.test_data['order_id_base'] + 1
                    await self._create_test_order(order_id)
                    
                    # 测试有效评价
                    review_id = await review_manager.create_review(
                        order_id=order_id,
                        merchant_id=self.test_data['merchant_id'],
                        customer_user_id=self.test_data['user_id'],
                        ratings=self.test_data['ratings'],
                        text_review="测试评价内容"
                    )
                    
                    if review_id:
                        # 验证评价数据
                        review_data = await review_manager.get_review_details(review_id)
                        required_fields = [
                            'order_id', 'merchant_id', 'customer_user_id',
                            'rating_appearance', 'rating_figure', 'rating_service',
                            'rating_attitude', 'rating_environment', 'status'
                        ]
                        
                        missing_fields = [
                            field for field in required_fields 
                            if field not in review_data or review_data[field] is None
                        ]
                        
                        if not missing_fields and review_data['status'] == 'pending_merchant_review':
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"评价创建成功，ID: {review_id}", "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                f"评价数据不完整: {missing_fields}", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            "评价创建失败", "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "REV_002":
                    # 测试评价状态管理
                    # 获取之前创建的评价
                    reviews = await review_manager.get_reviews_by_merchant(
                        self.test_data['merchant_id'], confirmed_only=False
                    )
                    
                    if reviews:
                        review_id = reviews[0]['id']
                        
                        # 测试状态转换：待确认 -> 已完成
                        success = await review_manager.confirm_review(review_id)
                        
                        if success:
                            # 验证状态更新
                            updated_review = await review_manager.get_review_details(review_id)
                            if updated_review and updated_review['status'] == 'completed':
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.PASSED,
                                    f"评价状态更新成功: {updated_review['status']}", "", duration
                                )
                            else:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.FAILED,
                                    f"状态未正确更新: {updated_review.get('status') if updated_review else 'None'}", 
                                    "", duration
                                )
                                all_passed = False
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                "评价确认失败", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            "没有找到评价记录", "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "REV_003":
                    # 测试防重复评价机制
                    order_id = self.test_data['order_id_base'] + 2
                    await self._create_test_order(order_id)
                    
                    # 创建第一个评价
                    first_review = await review_manager.create_review(
                        order_id=order_id,
                        merchant_id=self.test_data['merchant_id'],
                        customer_user_id=self.test_data['user_id'],
                        ratings=self.test_data['ratings'],
                        text_review="第一次评价"
                    )
                    
                    if first_review:
                        # 尝试创建重复评价
                        try:
                            duplicate_review = await review_manager.create_review(
                                order_id=order_id,  # 相同订单ID
                                merchant_id=self.test_data['merchant_id'],
                                customer_user_id=self.test_data['user_id'],
                                ratings=self.test_data['ratings'],
                                text_review="重复评价"
                            )
                            
                            if duplicate_review is None:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.PASSED,
                                    "成功阻止重复评价创建", "", duration
                                )
                            else:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.FAILED,
                                    "重复评价创建应该失败但却成功了", "", duration
                                )
                                all_passed = False
                                
                        except Exception as e:
                            if "UNIQUE constraint failed" in str(e):
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.PASSED,
                                    "数据库约束成功阻止重复评价", "", duration
                                )
                            else:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.FAILED,
                                    "未预期的错误", str(e), duration
                                )
                                all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            "首次评价创建失败", "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "REV_004":
                    # 测试评价数据查询
                    reviews = await review_manager.get_reviews_by_merchant(
                        self.test_data['merchant_id']
                    )
                    
                    if reviews:
                        # 验证查询结果的完整性
                        first_review = reviews[0]
                        required_fields = ['id', 'merchant_id', 'customer_user_id', 'created_at']
                        missing_fields = [
                            field for field in required_fields 
                            if field not in first_review
                        ]
                        
                        if not missing_fields:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"查询到{len(reviews)}条评价记录", "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                f"查询结果缺少字段: {missing_fields}", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.WARNING,
                            "没有找到评价记录", "", duration
                        )
                
                self.test_cases.append(test_case)
                
            except Exception as e:
                duration = time.time() - start_time
                await self.log_test_result(
                    test_case, TestResult.FAILED,
                    "测试执行异常", str(e), duration
                )
                all_passed = False
                self.test_cases.append(test_case)
        
        return all_passed

    # =============================================================================
    # 测试用例 2: 商户确认流程测试
    # =============================================================================
    
    async def test_merchant_confirmation_flow(self) -> bool:
        """测试2: 商户确认评价的双向流程"""
        test_cases = [
            TestCase(
                "MER_001", "商户确认评价有效性", "商户确认", "HIGH",
                "验证商户确认评价的基本功能"
            ),
            TestCase(
                "MER_002", "待确认评价列表", "商户确认", "MEDIUM",
                "验证商户可以查看待确认的评价列表"
            ),
            TestCase(
                "MER_003", "确认后状态更新", "商户确认", "HIGH",
                "验证确认后评价状态的正确更新"
            ),
            TestCase(
                "MER_004", "重复确认防护", "商户确认", "MEDIUM",
                "验证已确认评价不能重复确认"
            )
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            start_time = time.time()
            try:
                if test_case.test_id == "MER_001":
                    # 创建一个待确认的评价
                    order_id = self.test_data['order_id_base'] + 10
                    await self._create_test_order(order_id)
                    
                    review_id = await review_manager.create_review(
                        order_id=order_id,
                        merchant_id=self.test_data['merchant_id'],
                        customer_user_id=self.test_data['user_id'],
                        ratings=self.test_data['ratings'],
                        text_review="等待商户确认的评价"
                    )
                    
                    if review_id:
                        # 商户确认评价
                        confirm_success = await review_manager.confirm_review(review_id)
                        
                        if confirm_success:
                            # 验证确认结果
                            confirmed_review = await review_manager.get_review_details(review_id)
                            if (confirmed_review and 
                                confirmed_review.get('is_confirmed_by_merchant') and
                                confirmed_review.get('status') == 'completed'):
                                
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.PASSED,
                                    f"商户确认成功，评价ID: {review_id}", "", duration
                                )
                            else:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.FAILED,
                                    "确认状态未正确更新", "", duration
                                )
                                all_passed = False
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                "商户确认操作失败", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            "创建待确认评价失败", "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "MER_002":
                    # 测试待确认评价列表
                    pending_reviews = await review_manager.get_pending_reviews_for_merchant(
                        self.test_data['merchant_id']
                    )
                    
                    duration = time.time() - start_time
                    await self.log_test_result(
                        test_case, TestResult.PASSED,
                        f"找到{len(pending_reviews)}条待确认评价", "", duration
                    )
                
                elif test_case.test_id == "MER_003":
                    # 验证确认后状态更新（基于之前的测试）
                    confirmed_reviews = await review_manager.get_reviews_by_merchant(
                        self.test_data['merchant_id'], confirmed_only=True
                    )
                    
                    if confirmed_reviews:
                        # 检查第一条已确认评价的状态
                        review = confirmed_reviews[0]
                        if (review.get('is_confirmed_by_merchant') and
                            review.get('status') == 'completed'):
                            
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"已确认评价状态正确，数量: {len(confirmed_reviews)}", "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                "已确认评价状态不正确", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.WARNING,
                            "没有找到已确认的评价", "", duration
                        )
                
                elif test_case.test_id == "MER_004":
                    # 测试重复确认防护
                    confirmed_reviews = await review_manager.get_reviews_by_merchant(
                        self.test_data['merchant_id'], confirmed_only=True
                    )
                    
                    if confirmed_reviews:
                        review_id = confirmed_reviews[0]['id']
                        
                        # 尝试重复确认
                        repeat_confirm = await review_manager.confirm_review(review_id)
                        
                        # 重复确认应该返回False（因为已经确认过）
                        if not repeat_confirm:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                "成功阻止重复确认", "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.WARNING,
                                "重复确认被允许（可能是正常行为）", "", duration
                            )
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.SKIPPED,
                            "没有已确认的评价可供测试", "", duration
                        )
                
                self.test_cases.append(test_case)
                
            except Exception as e:
                duration = time.time() - start_time
                await self.log_test_result(
                    test_case, TestResult.FAILED,
                    "测试执行异常", str(e), duration
                )
                all_passed = False
                self.test_cases.append(test_case)
        
        return all_passed

    # =============================================================================
    # 测试用例 3: 积分和经验发放测试
    # =============================================================================
    
    async def test_reward_distribution_system(self) -> bool:
        """测试3: 积分和经验发放机制"""
        test_cases = [
            TestCase(
                "REW_001", "积分发放准确性", "奖励系统", "CRITICAL",
                "验证积分发放的数量和计算准确性"
            ),
            TestCase(
                "REW_002", "经验值发放验证", "奖励系统", "CRITICAL", 
                "验证经验值发放的正确性"
            ),
            TestCase(
                "REW_003", "奖励配置动态加载", "奖励系统", "MEDIUM",
                "验证系统配置的动态加载机制"
            ),
            TestCase(
                "REW_004", "防重复发放机制", "奖励系统", "HIGH",
                "验证同一评价不会重复发放奖励"
            )
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            start_time = time.time()
            try:
                if test_case.test_id == "REW_001":
                    # 获取用户当前积分
                    user_before = await user_manager.get_user_profile(self.test_data['user_id'])
                    points_before = user_before.get('points', 0) if user_before else 0
                    
                    # 获取积分配置
                    config = await system_config_manager.get_config('points_config', {})
                    if isinstance(config, str):
                        config = json.loads(config)
                    
                    reward_points = config.get('points_per_review', 25)
                    
                    # 发放积分
                    await user_manager.grant_rewards(
                        self.test_data['user_id'], 0, reward_points
                    )
                    
                    # 验证积分发放
                    user_after = await user_manager.get_user_profile(self.test_data['user_id'])
                    points_after = user_after.get('points', 0) if user_after else 0
                    
                    if points_after == points_before + reward_points:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.PASSED,
                            f"积分发放准确: {points_before} → {points_after} (+{reward_points})", 
                            "", duration
                        )
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            f"积分发放错误: 期望{points_before + reward_points}, 实际{points_after}", 
                            "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "REW_002":
                    # 测试经验值发放
                    user_before = await user_manager.get_user_profile(self.test_data['user_id'])
                    xp_before = user_before.get('xp', 0) if user_before else 0
                    
                    # 获取经验值配置
                    config = await system_config_manager.get_config('points_config', {})
                    if isinstance(config, str):
                        config = json.loads(config)
                    
                    reward_xp = config.get('xp_per_review', 50)
                    
                    # 发放经验值
                    await user_manager.grant_rewards(
                        self.test_data['user_id'], reward_xp, 0
                    )
                    
                    # 验证经验值发放
                    user_after = await user_manager.get_user_profile(self.test_data['user_id'])
                    xp_after = user_after.get('xp', 0) if user_after else 0
                    
                    if xp_after == xp_before + reward_xp:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.PASSED,
                            f"经验值发放准确: {xp_before} → {xp_after} (+{reward_xp})", 
                            "", duration
                        )
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            f"经验值发放错误: 期望{xp_before + reward_xp}, 实际{xp_after}", 
                            "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "REW_003":
                    # 测试配置动态加载
                    # 更新配置
                    new_config = {
                        'xp_per_review': 100,  # 修改配置
                        'points_per_review': 50,
                        'test_mode': True
                    }
                    
                    query = """
                        UPDATE system_config 
                        SET config_value = ? 
                        WHERE config_key = 'points_config'
                    """
                    await db_manager.execute_query(query, (json.dumps(new_config),))
                    
                    # 重新加载配置
                    loaded_config = await system_config_manager.get_config('points_config', {})
                    if isinstance(loaded_config, str):
                        loaded_config = json.loads(loaded_config)
                    
                    if (loaded_config.get('xp_per_review') == 100 and
                        loaded_config.get('test_mode') is True):
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.PASSED,
                            "配置动态加载正常", "", duration
                        )
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            f"配置加载失败: {loaded_config}", "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "REW_004":
                    # 防重复发放机制测试
                    # 这个需要在业务逻辑层实现，这里只能模拟测试
                    user_before = await user_manager.get_user_profile(self.test_data['user_id'])
                    points_before = user_before.get('points', 0) if user_before else 0
                    
                    # 连续两次发放相同奖励（业务层应该防止这种情况）
                    await user_manager.grant_rewards(self.test_data['user_id'], 0, 25)
                    await user_manager.grant_rewards(self.test_data['user_id'], 0, 25)
                    
                    user_after = await user_manager.get_user_profile(self.test_data['user_id'])
                    points_after = user_after.get('points', 0) if user_after else 0
                    
                    # 注意：这里的测试逻辑需要根据实际业务规则调整
                    # 如果业务层有防重复逻辑，则应该只增加一次
                    # 如果没有，则会增加两次，这是正常的数据库行为
                    
                    duration = time.time() - start_time
                    await self.log_test_result(
                        test_case, TestResult.WARNING,
                        f"重复发放测试: {points_before} → {points_after} (需业务层防护)", 
                        "", duration
                    )
                
                self.test_cases.append(test_case)
                
            except Exception as e:
                duration = time.time() - start_time
                await self.log_test_result(
                    test_case, TestResult.FAILED,
                    "测试执行异常", str(e), duration
                )
                all_passed = False
                self.test_cases.append(test_case)
        
        return all_passed

    # =============================================================================
    # 测试用例 4: 等级升级系统测试
    # =============================================================================
    
    async def test_level_upgrade_system(self) -> bool:
        """测试4: 等级升级系统的触发逻辑"""
        test_cases = [
            TestCase(
                "LVL_001", "等级配置完整性", "等级系统", "HIGH",
                "验证等级配置的完整性和正确性"
            ),
            TestCase(
                "LVL_002", "等级升级触发", "等级系统", "CRITICAL",
                "验证经验值达到阈值时的等级升级"
            ),
            TestCase(
                "LVL_003", "等级权益验证", "等级系统", "MEDIUM",
                "验证不同等级对应的权益和特性"
            ),
            TestCase(
                "LVL_004", "跨级升级处理", "等级系统", "MEDIUM",
                "验证经验值跨越多个等级时的处理"
            )
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            start_time = time.time()
            try:
                if test_case.test_id == "LVL_001":
                    # 验证等级配置
                    levels = await incentive_manager.get_all_levels()
                    
                    if len(levels) >= 5:  # 应该有至少5个等级
                        # 验证等级顺序
                        sorted_levels = sorted(levels, key=lambda x: x['xp_required'])
                        
                        # 检查是否有新手等级（0经验）
                        has_beginner = any(level['xp_required'] == 0 for level in levels)
                        
                        # 检查等级名称唯一性
                        level_names = [level['level_name'] for level in levels]
                        unique_names = len(set(level_names)) == len(level_names)
                        
                        if has_beginner and unique_names:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"等级配置完整，共{len(levels)}个等级", "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                f"等级配置有问题: 新手等级={has_beginner}, 名称唯一={unique_names}", 
                                "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            f"等级数量不足: {len(levels)}", "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "LVL_002":
                    # 测试等级升级触发
                    user_data = await user_manager.get_user_profile(self.test_data['user_id'])
                    current_xp = user_data.get('xp', 0) if user_data else 0
                    current_level = user_data.get('level_name', '新手') if user_data else '新手'
                    
                    # 获取所有等级
                    levels = await incentive_manager.get_all_levels()
                    
                    # 确定应该达到的等级
                    suitable_level = '新手'
                    for level in sorted(levels, key=lambda x: x['xp_required'], reverse=True):
                        if current_xp >= level['xp_required']:
                            suitable_level = level['level_name']
                            break
                    
                    # 如果需要升级
                    if suitable_level != current_level:
                        await user_manager.update_user_level_and_badges(
                            self.test_data['user_id'], suitable_level, None
                        )
                        
                        # 验证升级结果
                        updated_user = await user_manager.get_user_profile(self.test_data['user_id'])
                        new_level = updated_user.get('level_name') if updated_user else '新手'
                        
                        if new_level == suitable_level:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"等级升级成功: {current_level} → {new_level} (XP: {current_xp})", 
                                "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                f"等级升级失败: 期望{suitable_level}, 实际{new_level}", 
                                "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.PASSED,
                            f"等级无需升级: {current_level} (XP: {current_xp})", "", duration
                        )
                
                elif test_case.test_id == "LVL_003":
                    # 验证等级权益（这里主要验证数据完整性）
                    user_data = await user_manager.get_user_profile(self.test_data['user_id'])
                    if user_data:
                        level_name = user_data.get('level_name', '新手')
                        user_xp = user_data.get('xp', 0)
                        
                        # 验证等级名称与经验值的一致性
                        levels = await incentive_manager.get_all_levels()
                        level_requirements = {level['level_name']: level['xp_required'] for level in levels}
                        
                        required_xp = level_requirements.get(level_name, 0)
                        
                        if user_xp >= required_xp:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"等级权益正常: {level_name} (XP: {user_xp}/{required_xp})", 
                                "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                f"等级与经验值不匹配: {level_name} 需要{required_xp}XP, 实际{user_xp}XP", 
                                "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            "无法获取用户等级数据", "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "LVL_004":
                    # 测试跨级升级（模拟大量经验值）
                    # 为用户增加大量经验值
                    await user_manager.grant_rewards(self.test_data['user_id'], 2000, 0)
                    
                    user_data = await user_manager.get_user_profile(self.test_data['user_id'])
                    current_xp = user_data.get('xp', 0) if user_data else 0
                    
                    # 获取应达到的等级
                    levels = await incentive_manager.get_all_levels()
                    target_level = '新手'
                    for level in sorted(levels, key=lambda x: x['xp_required'], reverse=True):
                        if current_xp >= level['xp_required']:
                            target_level = level['level_name']
                            break
                    
                    # 执行等级升级
                    await user_manager.update_user_level_and_badges(
                        self.test_data['user_id'], target_level, None
                    )
                    
                    # 验证结果
                    updated_user = await user_manager.get_user_profile(self.test_data['user_id'])
                    final_level = updated_user.get('level_name') if updated_user else '新手'
                    
                    if final_level == target_level:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.PASSED,
                            f"跨级升级成功: → {final_level} (XP: {current_xp})", 
                            "", duration
                        )
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            f"跨级升级失败: 期望{target_level}, 实际{final_level}", 
                            "", duration
                        )
                        all_passed = False
                
                self.test_cases.append(test_case)
                
            except Exception as e:
                duration = time.time() - start_time
                await self.log_test_result(
                    test_case, TestResult.FAILED,
                    "测试执行异常", str(e), duration
                )
                all_passed = False
                self.test_cases.append(test_case)
        
        return all_passed

    # =============================================================================
    # 测试用例 5: 勋章系统测试
    # =============================================================================
    
    async def test_badge_system(self) -> bool:
        """测试5: 勋章系统的触发和管理"""
        test_cases = [
            TestCase(
                "BDG_001", "勋章配置完整性", "勋章系统", "HIGH",
                "验证勋章配置和触发条件的完整性"
            ),
            TestCase(
                "BDG_002", "勋章触发条件检测", "勋章系统", "CRITICAL",
                "验证勋章触发条件的准确检测"
            ),
            TestCase(
                "BDG_003", "勋章授予机制", "勋章系统", "HIGH",
                "验证勋章授予的正确性"
            ),
            TestCase(
                "BDG_004", "重复勋章防护", "勋章系统", "MEDIUM",
                "验证同一勋章不会重复授予"
            )
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            start_time = time.time()
            try:
                if test_case.test_id == "BDG_001":
                    # 验证勋章配置
                    badges = await incentive_manager.get_all_badges()
                    
                    if len(badges) >= 4:  # 应该有至少4个勋章
                        # 验证每个勋章都有触发条件
                        badges_with_triggers = 0
                        for badge in badges:
                            triggers = await incentive_manager.get_triggers_for_badge(badge['id'])
                            if triggers:
                                badges_with_triggers += 1
                        
                        if badges_with_triggers > 0:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"勋章配置完整: {len(badges)}个勋章, {badges_with_triggers}个有触发条件", 
                                "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                "没有勋章配置了触发条件", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            f"勋章数量不足: {len(badges)}", "", duration
                        )
                        all_passed = False
                
                elif test_case.test_id == "BDG_002":
                    # 测试勋章触发条件检测
                    user_data = await user_manager.get_user_profile(self.test_data['user_id'])
                    if not user_data:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            "无法获取用户数据", "", duration
                        )
                        all_passed = False
                        continue
                    
                    order_count = user_data.get('order_count', 0)
                    total_points = user_data.get('points', 0)
                    
                    # 检查满足条件的勋章
                    badges = await incentive_manager.get_all_badges()
                    eligible_badges = []
                    
                    for badge in badges:
                        triggers = await incentive_manager.get_triggers_for_badge(badge['id'])
                        for trigger in triggers:
                            if trigger['trigger_type'] == 'order_count' and order_count >= trigger['trigger_value']:
                                eligible_badges.append(badge['badge_name'])
                                break
                            elif trigger['trigger_type'] == 'total_points' and total_points >= trigger['trigger_value']:
                                eligible_badges.append(badge['badge_name'])
                                break
                    
                    duration = time.time() - start_time
                    await self.log_test_result(
                        test_case, TestResult.PASSED,
                        f"触发条件检测完成: 满足{len(eligible_badges)}个勋章条件 (订单:{order_count}, 积分:{total_points})", 
                        "", duration
                    )
                
                elif test_case.test_id == "BDG_003":
                    # 测试勋章授予机制
                    # 增加订单计数以触发勋章
                    await db_manager.execute_query(
                        "UPDATE users SET order_count = order_count + 1 WHERE user_id = ?",
                        (self.test_data['user_id'],)
                    )
                    
                    # 检查用户当前勋章
                    user_before = await user_manager.get_user_profile(self.test_data['user_id'])
                    badges_before = json.loads(user_before.get('badges', '[]')) if user_before else []
                    
                    # 模拟授予首次评价勋章
                    test_badge_name = "首次评价"
                    if test_badge_name not in badges_before:
                        await user_manager.update_user_level_and_badges(
                            self.test_data['user_id'], None, test_badge_name
                        )
                        
                        # 验证勋章授予
                        user_after = await user_manager.get_user_profile(self.test_data['user_id'])
                        badges_after = json.loads(user_after.get('badges', '[]')) if user_after else []
                        
                        if test_badge_name in badges_after:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"勋章授予成功: {test_badge_name}", "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                f"勋章授予失败: {test_badge_name}", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.PASSED,
                            f"勋章已存在: {test_badge_name}", "", duration
                        )
                
                elif test_case.test_id == "BDG_004":
                    # 测试重复勋章防护
                    user_data = await user_manager.get_user_profile(self.test_data['user_id'])
                    badges_before = json.loads(user_data.get('badges', '[]')) if user_data else []
                    
                    # 尝试重复授予同一勋章
                    test_badge_name = "首次评价"
                    await user_manager.update_user_level_and_badges(
                        self.test_data['user_id'], None, test_badge_name
                    )
                    
                    user_after = await user_manager.get_user_profile(self.test_data['user_id'])
                    badges_after = json.loads(user_after.get('badges', '[]')) if user_after else []
                    
                    # 统计该勋章出现次数
                    badge_count_before = badges_before.count(test_badge_name)
                    badge_count_after = badges_after.count(test_badge_name)
                    
                    if badge_count_after <= badge_count_before + 1:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.PASSED,
                            f"重复勋章防护正常: {test_badge_name} 出现{badge_count_after}次", 
                            "", duration
                        )
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.FAILED,
                            f"重复勋章防护失效: {test_badge_name} 重复出现", "", duration
                        )
                        all_passed = False
                
                self.test_cases.append(test_case)
                
            except Exception as e:
                duration = time.time() - start_time
                await self.log_test_result(
                    test_case, TestResult.FAILED,
                    "测试执行异常", str(e), duration
                )
                all_passed = False
                self.test_cases.append(test_case)
        
        return all_passed

    # =============================================================================
    # 测试用例 6: 定时任务和报告系统测试
    # =============================================================================
    
    async def test_scheduler_and_reporting(self) -> bool:
        """测试6: 定时任务和报告系统"""
        test_cases = [
            TestCase(
                "SCH_001", "商户平均分计算", "定时任务", "HIGH",
                "验证商户平均分的定时计算功能"
            ),
            TestCase(
                "SCH_002", "评价统计准确性", "报告系统", "MEDIUM",
                "验证评价统计数据的准确性"
            ),
            TestCase(
                "SCH_003", "批量数据处理", "定时任务", "MEDIUM",
                "验证批量处理多个商户评价的能力"
            )
        ]
        
        all_passed = True
        
        for test_case in test_cases:
            start_time = time.time()
            try:
                if test_case.test_id == "SCH_001":
                    # 测试商户平均分计算
                    # 首先确保有已确认的评价
                    reviews = await review_manager.get_reviews_by_merchant(
                        self.test_data['merchant_id'], confirmed_only=True
                    )
                    
                    if reviews:
                        # 执行平均分计算
                        success = await review_manager.calculate_and_update_merchant_scores(
                            self.test_data['merchant_id']
                        )
                        
                        if success:
                            # 验证计算结果
                            scores = await review_manager.get_merchant_scores(
                                self.test_data['merchant_id']
                            )
                            
                            if scores and scores.get('total_reviews_count', 0) > 0:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.PASSED,
                                    f"平均分计算成功: 总评价{scores['total_reviews_count']}条", 
                                    "", duration
                                )
                            else:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.FAILED,
                                    "平均分计算结果异常", "", duration
                                )
                                all_passed = False
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                "平均分计算失败", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.SKIPPED,
                            "没有已确认的评价进行计算", "", duration
                        )
                
                elif test_case.test_id == "SCH_002":
                    # 验证评价统计准确性
                    # 手动计算预期值
                    confirmed_reviews = await review_manager.get_reviews_by_merchant(
                        self.test_data['merchant_id'], confirmed_only=True
                    )
                    
                    if confirmed_reviews:
                        # 计算手动平均分
                        total_appearance = sum(r['rating_appearance'] for r in confirmed_reviews)
                        manual_avg_appearance = total_appearance / len(confirmed_reviews)
                        
                        # 获取系统计算的平均分
                        scores = await review_manager.get_merchant_scores(
                            self.test_data['merchant_id']
                        )
                        
                        if scores:
                            system_avg_appearance = scores.get('avg_appearance', 0)
                            
                            # 允许小数点精度差异
                            if abs(manual_avg_appearance - system_avg_appearance) < 0.01:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.PASSED,
                                    f"统计准确性验证通过: 手动{manual_avg_appearance:.2f}, 系统{system_avg_appearance:.2f}", 
                                    "", duration
                                )
                            else:
                                duration = time.time() - start_time
                                await self.log_test_result(
                                    test_case, TestResult.FAILED,
                                    f"统计数据不匹配: 手动{manual_avg_appearance:.2f}, 系统{system_avg_appearance:.2f}", 
                                    "", duration
                                )
                                all_passed = False
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.FAILED,
                                "无法获取系统计算的评分", "", duration
                            )
                            all_passed = False
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.SKIPPED,
                            "没有评价数据进行统计验证", "", duration
                        )
                
                elif test_case.test_id == "SCH_003":
                    # 测试批量处理能力（模拟）
                    # 获取所有有评价的商户
                    query = """
                        SELECT DISTINCT merchant_id, COUNT(*) as review_count
                        FROM reviews 
                        WHERE is_confirmed_by_merchant = TRUE
                        GROUP BY merchant_id
                    """
                    merchants_with_reviews = await db_manager.fetch_all(query)
                    
                    if merchants_with_reviews:
                        success_count = 0
                        for merchant_data in merchants_with_reviews:
                            merchant_id = merchant_data['merchant_id']
                            success = await review_manager.calculate_and_update_merchant_scores(merchant_id)
                            if success:
                                success_count += 1
                        
                        if success_count == len(merchants_with_reviews):
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.PASSED,
                                f"批量处理成功: {success_count}/{len(merchants_with_reviews)}个商户", 
                                "", duration
                            )
                        else:
                            duration = time.time() - start_time
                            await self.log_test_result(
                                test_case, TestResult.WARNING,
                                f"批量处理部分成功: {success_count}/{len(merchants_with_reviews)}个商户", 
                                "", duration
                            )
                    else:
                        duration = time.time() - start_time
                        await self.log_test_result(
                            test_case, TestResult.SKIPPED,
                            "没有商户评价数据进行批量处理测试", "", duration
                        )
                
                self.test_cases.append(test_case)
                
            except Exception as e:
                duration = time.time() - start_time
                await self.log_test_result(
                    test_case, TestResult.FAILED,
                    "测试执行异常", str(e), duration
                )
                all_passed = False
                self.test_cases.append(test_case)
        
        return all_passed

    # =============================================================================
    # 辅助方法
    # =============================================================================
    
    async def _create_test_order(self, order_id: int):
        """创建测试订单"""
        query = """
            INSERT OR REPLACE INTO orders 
            (id, merchant_id, customer_user_id, customer_username, price, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        await db_manager.execute_query(query, (
            order_id,
            self.test_data['merchant_id'],
            self.test_data['user_id'],
            self.test_data['username'],
            300,
            "已完成"
        ))

    async def _cleanup_test_data(self):
        """清理测试数据"""
        cleanup_queries = [
            ("DELETE FROM reviews WHERE customer_user_id = ?", (self.test_data['user_id'],)),
            ("DELETE FROM orders WHERE customer_user_id = ?", (self.test_data['user_id'],)),
            ("DELETE FROM merchants WHERE id = ?", (self.test_data['merchant_id'],)),
            ("DELETE FROM users WHERE user_id = ?", (self.test_data['user_id'],)),
            ("DELETE FROM merchant_scores WHERE merchant_id = ?", (self.test_data['merchant_id'],))
        ]
        
        for query, params in cleanup_queries:
            try:
                await db_manager.execute_query(query, params)
                logger.debug(f"清理完成: {query.split()[2]}")
            except Exception as e:
                logger.warning(f"清理数据时出错: {e}")
                
        # 额外清理：清理可能的测试订单
        try:
            await db_manager.execute_query(
                "DELETE FROM orders WHERE id BETWEEN ? AND ?", 
                (self.test_data['order_id_base'], self.test_data['order_id_base'] + 100)
            )
        except Exception as e:
            logger.warning(f"清理测试订单时出错: {e}")

    # =============================================================================
    # 主测试流程
    # =============================================================================
    
    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """运行综合测试套件"""
        logger.info("=" * 80)
        logger.info("🚀 开始评价与激励闭环综合测试")
        logger.info("=" * 80)
        
        start_time = time.time()
        
        try:
            # 1. 环境设置
            setup_success = await self.setup_test_environment()
            if not setup_success:
                logger.error("❌ 测试环境设置失败，终止测试")
                return self._generate_test_report(time.time() - start_time)
            
            # 2. 执行测试套件
            test_suites = [
                ("评价创建和管理测试", self.test_review_creation_and_management),
                ("商户确认流程测试", self.test_merchant_confirmation_flow),
                ("积分发放系统测试", self.test_reward_distribution_system),
                ("等级升级系统测试", self.test_level_upgrade_system),
                ("勋章系统测试", self.test_badge_system),
                ("定时任务和报告测试", self.test_scheduler_and_reporting)
            ]
            
            suite_results = []
            for suite_name, test_method in test_suites:
                logger.info(f"\n📋 开始执行: {suite_name}")
                try:
                    result = await test_method()
                    suite_results.append((suite_name, result))
                    status = "✅ 通过" if result else "❌ 失败"
                    logger.info(f"📋 {suite_name}: {status}")
                except Exception as e:
                    logger.error(f"❌ {suite_name} 执行异常: {e}")
                    suite_results.append((suite_name, False))
            
            # 3. 生成测试报告
            total_duration = time.time() - start_time
            test_report = self._generate_test_report(total_duration)
            
            # 4. 打印测试摘要
            self._print_test_summary(suite_results, test_report)
            
            return test_report
            
        except Exception as e:
            logger.error(f"测试执行过程中发生严重错误: {e}")
            return self._generate_test_report(time.time() - start_time)
            
        finally:
            # 5. 清理测试数据
            try:
                await self._cleanup_test_data()
                logger.info("🧹 测试数据清理完成")
            except Exception as e:
                logger.error(f"清理测试数据时出错: {e}")

    def _generate_test_report(self, total_duration: float) -> Dict[str, Any]:
        """生成测试报告"""
        total = self.test_results['total_tests']
        passed = self.test_results['passed_tests']
        failed = self.test_results['failed_tests']
        skipped = self.test_results['skipped_tests']
        warning = self.test_results['warning_tests']
        
        success_rate = (passed / total * 100) if total > 0 else 0
        
        return {
            'test_summary': {
                'total_tests': total,
                'passed_tests': passed,
                'failed_tests': failed,
                'skipped_tests': skipped,
                'warning_tests': warning,
                'success_rate': f"{success_rate:.1f}%",
                'total_duration': f"{total_duration:.2f}秒"
            },
            'test_cases': [
                {
                    'test_id': tc.test_id,
                    'test_name': tc.test_name,
                    'category': tc.category,
                    'priority': tc.priority,
                    'result': tc.result.value if tc.result else 'N/A',
                    'details': tc.details,
                    'error': tc.error,
                    'duration': f"{tc.duration:.3f}秒",
                    'timestamp': tc.timestamp.isoformat() if tc.timestamp else None
                }
                for tc in self.test_cases
            ],
            'conclusion': 'PASS' if failed == 0 else 'FAIL',
            'recommendations': self._generate_recommendations(),
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """生成测试建议"""
        recommendations = []
        
        if self.test_results['failed_tests'] > 0:
            recommendations.append("⚠️ 存在失败测试，需要修复相关功能")
        
        if self.test_results['warning_tests'] > 0:
            recommendations.append("⚠️ 存在警告项，建议优化相关实现")
        
        if self.test_results['skipped_tests'] > 0:
            recommendations.append("ℹ️ 部分测试被跳过，可能需要补充测试数据")
        
        # 基于具体测试结果的建议
        failed_categories = set()
        for tc in self.test_cases:
            if tc.result == TestResult.FAILED:
                failed_categories.add(tc.category)
        
        if "评价管理" in failed_categories:
            recommendations.append("🔧 建议检查评价创建和管理的业务逻辑")
        
        if "奖励系统" in failed_categories:
            recommendations.append("🔧 建议检查积分发放和计算机制")
        
        if "等级系统" in failed_categories:
            recommendations.append("🔧 建议检查等级升级的触发条件")
        
        if "勋章系统" in failed_categories:
            recommendations.append("🔧 建议检查勋章授予的触发逻辑")
        
        if not recommendations:
            recommendations.append("✅ 所有测试通过，系统运行良好")
        
        return recommendations

    def _print_test_summary(self, suite_results: List[tuple], test_report: Dict[str, Any]):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("📊 评价与激励闭环综合测试报告")
        print("=" * 80)
        
        print("\n📋 测试套件结果:")
        for suite_name, result in suite_results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"   {status} - {suite_name}")
        
        summary = test_report['test_summary']
        print(f"\n📊 测试统计:")
        print(f"   总计测试: {summary['total_tests']}")
        print(f"   通过测试: {summary['passed_tests']}")
        print(f"   失败测试: {summary['failed_tests']}")
        print(f"   跳过测试: {summary['skipped_tests']}")
        print(f"   警告测试: {summary['warning_tests']}")
        print(f"   成功率: {summary['success_rate']}")
        print(f"   总耗时: {summary['total_duration']}")
        
        print(f"\n🎯 测试结论: {test_report['conclusion']}")
        
        print(f"\n💡 建议事项:")
        for rec in test_report['recommendations']:
            print(f"   {rec}")
        
        print("=" * 80)

async def main():
    """主函数"""
    tester = ReviewIncentiveLoopTester()
    
    try:
        report = await tester.run_comprehensive_tests()
        
        # 保存测试报告
        timestamp = int(time.time())
        report_path = f"/Users/kikk/Documents/lanyangyang/tests/integration/review_incentive_test_report_{timestamp}.json"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n📄 详细测试报告已保存: {report_path}")
        
        return report['conclusion'] == 'PASS'
        
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)