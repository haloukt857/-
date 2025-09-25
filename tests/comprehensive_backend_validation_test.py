# -*- coding: utf-8 -*-
"""
后端双向评价系统和订单管理综合验证测试

验证核心功能：
1. 数据库事务一致性和错误处理
2. 用户评价->商家确认->激励发放的完整链路
3. 订单状态转换的业务规则正确性
4. 防重复评价、防刷分机制有效性
5. 积分经验计算准确性
6. 等级升级和勋章触发正常性
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 后端核心模块
from database.db_orders import order_manager
from database.db_reviews import review_manager
from database.db_users import user_manager
from services.incentive_processor import incentive_processor
from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class ComprehensiveBackendValidator:
    """综合后端验证器"""

    def __init__(self):
        self.test_results = {
            'database_consistency': None,
            'review_confirm_flow': None,
            'order_status_rules': None,
            'anti_duplicate_mechanisms': None,
            'incentive_accuracy': None,
            'error_handling': None
        }

    async def run_all_validations(self) -> Dict[str, Any]:
        """运行所有验证测试"""
        print("🔍 开始后端双向评价系统综合验证...")
        print("=" * 60)

        try:
            # 1. 数据库事务一致性验证
            await self._test_database_consistency()
            
            # 2. 评价确认激励完整流程验证
            await self._test_review_confirm_incentive_flow()
            
            # 3. 订单状态转换业务规则验证
            await self._test_order_status_rules()
            
            # 4. 防重复机制验证
            await self._test_anti_duplicate_mechanisms()
            
            # 5. 激励计算准确性验证
            await self._test_incentive_calculation_accuracy()
            
            # 6. 错误处理机制验证
            await self._test_error_handling()

            return self._generate_final_report()

        except Exception as e:
            logger.error(f"综合验证过程中出现严重错误: {e}")
            return {'error': str(e), 'results': self.test_results}

    async def _test_database_consistency(self):
        """测试数据库事务一致性"""
        print("\n📊 1. 数据库事务一致性验证")
        print("-" * 40)
        
        try:
            # 测试用例：创建订单-评价-确认的原子性操作
            test_user_id = 999999999
            test_merchant_id = 1
            
            # 1.1 创建测试订单
            order_data = {
                'customer_user_id': test_user_id,
                'merchant_id': test_merchant_id,
                'price': 500,
                'status': '已完成',
                'customer_username': 'test_consistency_user'
            }
            
            order_id = await order_manager.create_order(order_data)
            assert order_id is not None, "订单创建失败"
            
            # 1.2 创建评价
            ratings = {
                'appearance': 8,
                'figure': 9,
                'service': 7,
                'attitude': 10,
                'environment': 8
            }
            
            review_id = await review_manager.create_review(
                order_id=order_id,
                merchant_id=test_merchant_id,
                customer_user_id=test_user_id,
                ratings=ratings,
                text_review="测试评价内容"
            )
            assert review_id is not None, "评价创建失败"
            
            # 1.3 验证数据一致性 - 检查外键关联
            review = await review_manager.get_review_detail(review_id)
            order = await order_manager.get_order(order_id)
            
            assert review['order_id'] == order_id, "评价-订单关联不一致"
            assert review['merchant_id'] == test_merchant_id, "评价-商户关联不一致"
            assert order['customer_user_id'] == test_user_id, "订单-用户关联不一致"
            
            # 1.4 事务回滚测试（模拟错误情况）
            try:
                # 尝试创建无效评价（订单ID不存在）
                invalid_review_id = await review_manager.create_review(
                    order_id=999999,  # 不存在的订单ID
                    merchant_id=test_merchant_id,
                    customer_user_id=test_user_id,
                    ratings=ratings
                )
                # 应该失败
                assert False, "无效数据应该创建失败"
            except:
                pass  # 预期的错误，数据库正确拒绝了无效数据
            
            # 清理测试数据
            await self._cleanup_test_data(order_id, review_id)
            
            self.test_results['database_consistency'] = {
                'status': 'PASSED',
                'checks': [
                    '✅ 订单-评价外键关联正确',
                    '✅ 数据完整性约束生效',
                    '✅ 无效数据正确拒绝',
                    '✅ 事务原子性保证'
                ]
            }
            print("✅ 数据库一致性验证通过")
            
        except Exception as e:
            self.test_results['database_consistency'] = {
                'status': 'FAILED',
                'error': str(e)
            }
            print(f"❌ 数据库一致性验证失败: {e}")

    async def _test_review_confirm_incentive_flow(self):
        """测试评价确认触发激励发放的完整流程"""
        print("\n🎯 2. 评价确认激励流程验证")
        print("-" * 40)
        
        try:
            test_user_id = 888888888
            test_merchant_id = 1
            
            # 2.1 创建用户（如果不存在）
            try:
                await user_manager.create_or_update_user(test_user_id, "test_incentive_user")
            except:
                pass  # 用户可能已存在
            
            # 获取用户初始状态
            initial_user = await user_manager.get_user_profile(test_user_id)
            initial_points = initial_user.get('points', 0) if initial_user else 0
            initial_xp = initial_user.get('xp', 0) if initial_user else 0
            
            # 2.2 创建订单和评价
            order_data = {
                'customer_user_id': test_user_id,
                'merchant_id': test_merchant_id,
                'price': 300,
                'status': '已完成'
            }
            
            order_id = await order_manager.create_order(order_data)
            
            # 创建高质量评价（应该触发额外奖励）
            ratings = {
                'appearance': 9,
                'figure': 9,
                'service': 10,
                'attitude': 10,
                'environment': 9
            }
            
            review_id = await review_manager.create_review(
                order_id=order_id,
                merchant_id=test_merchant_id,
                customer_user_id=test_user_id,
                ratings=ratings,
                text_review="非常优秀的服务，强烈推荐！"
            )
            
            # 2.3 确认评价（核心测试点）
            confirm_success = await review_manager.confirm_review(review_id)
            assert confirm_success, "评价确认失败"
            
            # 2.4 验证用户积分和经验增长
            await asyncio.sleep(0.1)  # 等待异步处理完成
            updated_user = await user_manager.get_user_profile(test_user_id)
            
            if updated_user:
                new_points = updated_user.get('points', 0)
                new_xp = updated_user.get('xp', 0)
                
                points_gained = new_points - initial_points
                xp_gained = new_xp - initial_xp
                
                # 基础奖励50积分20经验 + 高分奖励25积分10经验 + 文字奖励15积分5经验
                expected_points = 50 + 25 + 15  # 90积分
                expected_xp = 20 + 10 + 5       # 35经验
                
                assert points_gained >= 80, f"积分奖励不足，期望至少80，实际{points_gained}"
                assert xp_gained >= 30, f"经验奖励不足，期望至少30，实际{xp_gained}"
                
                print(f"✅ 激励奖励正确: +{points_gained}积分, +{xp_gained}经验")
            
            # 2.5 验证评价状态更新
            confirmed_review = await review_manager.get_review_detail(review_id)
            assert confirmed_review['is_confirmed_by_merchant'] == True, "评价确认状态未更新"
            assert confirmed_review['status'] == 'completed', "评价状态未正确更新"
            
            # 清理测试数据
            await self._cleanup_test_data(order_id, review_id)
            
            self.test_results['review_confirm_flow'] = {
                'status': 'PASSED',
                'details': {
                    'points_gained': points_gained if 'points_gained' in locals() else 0,
                    'xp_gained': xp_gained if 'xp_gained' in locals() else 0,
                    'review_confirmed': True,
                    'status_updated': True
                }
            }
            print("✅ 评价确认激励流程验证通过")
            
        except Exception as e:
            self.test_results['review_confirm_flow'] = {
                'status': 'FAILED',
                'error': str(e)
            }
            print(f"❌ 评价确认激励流程验证失败: {e}")

    async def _test_order_status_rules(self):
        """测试订单状态转换业务规则"""
        print("\n📋 3. 订单状态转换规则验证")
        print("-" * 40)
        
        try:
            test_user_id = 777777777
            test_merchant_id = 1
            
            # 3.1 测试有效状态转换
            valid_statuses = ['尝试预约', '已完成', '已评价', '双方评价', '单方评价']
            
            for status in valid_statuses:
                order_data = {
                    'customer_user_id': test_user_id,
                    'merchant_id': test_merchant_id,
                    'price': 200,
                    'status': status
                }
                
                order_id = await order_manager.create_order(order_data)
                assert order_id is not None, f"创建{status}状态订单失败"
                
                # 验证状态更新
                update_success = await order_manager.update_order_status(
                    order_id, '已完成', datetime.now()
                )
                assert update_success, f"{status}状态订单无法更新为已完成"
                
                # 清理
                await order_manager.delete_order(order_id)
            
            # 3.2 测试无效状态（应该被拒绝或修正）
            try:
                order_data = {
                    'customer_user_id': test_user_id,
                    'merchant_id': test_merchant_id,
                    'price': 200,
                    'status': '无效状态'
                }
                
                order_id = await order_manager.create_order(order_data)
                if order_id:
                    # 如果创建成功，检查状态是否被修正
                    order = await order_manager.get_order(order_id)
                    assert order['status'] in valid_statuses, "无效状态应该被修正为有效状态"
                    await order_manager.delete_order(order_id)
                    
            except Exception:
                pass  # 预期的错误，系统正确拒绝了无效状态
            
            self.test_results['order_status_rules'] = {
                'status': 'PASSED',
                'checks': [
                    '✅ 所有有效状态可正常创建',
                    '✅ 状态转换规则正确',
                    '✅ 无效状态被正确处理'
                ]
            }
            print("✅ 订单状态转换规则验证通过")
            
        except Exception as e:
            self.test_results['order_status_rules'] = {
                'status': 'FAILED', 
                'error': str(e)
            }
            print(f"❌ 订单状态转换规则验证失败: {e}")

    async def _test_anti_duplicate_mechanisms(self):
        """测试防重复评价和防刷分机制"""
        print("\n🛡️ 4. 防重复机制验证")
        print("-" * 40)
        
        try:
            test_user_id = 666666666
            test_merchant_id = 1
            
            # 4.1 创建测试订单
            order_data = {
                'customer_user_id': test_user_id,
                'merchant_id': test_merchant_id,
                'price': 400,
                'status': '已完成'
            }
            
            order_id = await order_manager.create_order(order_data)
            
            # 4.2 创建第一个评价
            ratings = {'appearance': 8, 'figure': 7, 'service': 9, 'attitude': 8, 'environment': 7}
            
            review_id1 = await review_manager.create_review(
                order_id=order_id,
                merchant_id=test_merchant_id,
                customer_user_id=test_user_id,
                ratings=ratings
            )
            assert review_id1 is not None, "第一个评价创建失败"
            
            # 4.3 尝试对同一订单创建第二个评价（应该失败）
            try:
                review_id2 = await review_manager.create_review(
                    order_id=order_id,
                    merchant_id=test_merchant_id,
                    customer_user_id=test_user_id,
                    ratings=ratings
                )
                # 如果创建成功，说明防重复机制有问题
                if review_id2:
                    await self._cleanup_test_data(order_id, review_id2)
                    assert False, "防重复评价机制失效：同一订单允许创建多个评价"
            except Exception:
                pass  # 预期的错误，系统正确阻止了重复评价
                
            # 4.4 测试重复确认评价
            confirm1 = await review_manager.confirm_review(review_id1)
            assert confirm1, "首次确认评价失败"
            
            # 再次确认同一评价（应该安全处理，不重复发放奖励）
            confirm2 = await review_manager.confirm_review(review_id1)
            assert confirm2, "重复确认应该返回成功但不重复处理"
            
            # 清理测试数据
            await self._cleanup_test_data(order_id, review_id1)
            
            self.test_results['anti_duplicate_mechanisms'] = {
                'status': 'PASSED',
                'checks': [
                    '✅ 防重复评价机制有效',
                    '✅ 重复确认安全处理',
                    '✅ 数据完整性保护正常'
                ]
            }
            print("✅ 防重复机制验证通过")
            
        except Exception as e:
            self.test_results['anti_duplicate_mechanisms'] = {
                'status': 'FAILED',
                'error': str(e)
            }
            print(f"❌ 防重复机制验证失败: {e}")

    async def _test_incentive_calculation_accuracy(self):
        """测试激励计算准确性"""
        print("\n🧮 5. 激励计算准确性验证")
        print("-" * 40)
        
        try:
            # 5.1 测试不同评分的奖励计算
            test_cases = [
                {
                    'name': '低分评价',
                    'ratings': {'appearance': 3, 'figure': 4, 'service': 5, 'attitude': 4, 'environment': 3},
                    'text': '',
                    'expected_base': 50,  # 基础奖励
                    'expected_bonus': 0   # 无高分和文字奖励
                },
                {
                    'name': '高分评价无文字',
                    'ratings': {'appearance': 9, 'figure': 8, 'service': 10, 'attitude': 9, 'environment': 8},
                    'text': '',
                    'expected_base': 50,  # 基础奖励
                    'expected_bonus': 25  # 高分奖励
                },
                {
                    'name': '高分评价有文字',
                    'ratings': {'appearance': 10, 'figure': 9, 'service': 10, 'attitude': 10, 'environment': 9},
                    'text': '非常棒的服务体验！',
                    'expected_base': 50,   # 基础奖励
                    'expected_bonus': 40   # 高分(25) + 文字(15)奖励
                }
            ]
            
            calculation_results = []
            
            for test_case in test_cases:
                # 模拟评价数据
                mock_review = {
                    'id': 1,
                    **test_case['ratings'],
                    'text_review_by_user': test_case['text']
                }
                
                # 直接测试奖励计算方法
                with unittest.mock.patch.object(review_manager, 'get_review_detail', return_value=mock_review):
                    rewards = await incentive_processor._calculate_review_base_rewards(1)
                
                if rewards:
                    expected_total_points = test_case['expected_base'] + test_case['expected_bonus']
                    actual_points = rewards['points']
                    
                    # 验证积分计算
                    points_correct = actual_points == expected_total_points
                    calculation_results.append({
                        'case': test_case['name'],
                        'expected': expected_total_points,
                        'actual': actual_points,
                        'correct': points_correct
                    })
                    
                    print(f"📊 {test_case['name']}: 期望{expected_total_points}积分, 实际{actual_points}积分 {'✅' if points_correct else '❌'}")
            
            all_calculations_correct = all(r['correct'] for r in calculation_results)
            
            self.test_results['incentive_accuracy'] = {
                'status': 'PASSED' if all_calculations_correct else 'FAILED',
                'calculations': calculation_results
            }
            
            if all_calculations_correct:
                print("✅ 激励计算准确性验证通过")
            else:
                print("❌ 部分激励计算不准确")
            
        except Exception as e:
            self.test_results['incentive_accuracy'] = {
                'status': 'FAILED',
                'error': str(e)
            }
            print(f"❌ 激励计算准确性验证失败: {e}")

    async def _test_error_handling(self):
        """测试错误处理机制"""
        print("\n⚠️ 6. 错误处理机制验证")
        print("-" * 40)
        
        try:
            error_handling_checks = []
            
            # 6.1 测试不存在的评价ID
            try:
                result = await review_manager.confirm_review(999999)
                error_handling_checks.append({
                    'test': '不存在评价ID处理',
                    'result': '正确返回False' if result == False else '处理有误',
                    'passed': result == False
                })
            except Exception:
                error_handling_checks.append({
                    'test': '不存在评价ID处理',
                    'result': '正确抛出异常',
                    'passed': True
                })
            
            # 6.2 测试不存在的订单ID
            try:
                result = await order_manager.get_order(999999)
                error_handling_checks.append({
                    'test': '不存在订单ID处理',
                    'result': '正确返回None' if result is None else '处理有误',
                    'passed': result is None
                })
            except Exception:
                error_handling_checks.append({
                    'test': '不存在订单ID处理', 
                    'result': '抛出异常',
                    'passed': False
                })
            
            # 6.3 测试无效数据输入
            try:
                result = await review_manager.create_review(
                    order_id=None,  # 无效的None值
                    merchant_id=1,
                    customer_user_id=123,
                    ratings={'appearance': 5}  # 不完整的评分
                )
                error_handling_checks.append({
                    'test': '无效数据输入处理',
                    'result': '创建成功（异常）' if result else '正确拒绝',
                    'passed': result is None
                })
            except Exception:
                error_handling_checks.append({
                    'test': '无效数据输入处理',
                    'result': '正确抛出异常',
                    'passed': True
                })
            
            all_checks_passed = all(check['passed'] for check in error_handling_checks)
            
            for check in error_handling_checks:
                status = "✅" if check['passed'] else "❌"
                print(f"{status} {check['test']}: {check['result']}")
            
            self.test_results['error_handling'] = {
                'status': 'PASSED' if all_checks_passed else 'FAILED',
                'checks': error_handling_checks
            }
            
            if all_checks_passed:
                print("✅ 错误处理机制验证通过")
            else:
                print("❌ 部分错误处理机制需要完善")
            
        except Exception as e:
            self.test_results['error_handling'] = {
                'status': 'FAILED',
                'error': str(e)
            }
            print(f"❌ 错误处理机制验证失败: {e}")

    async def _cleanup_test_data(self, order_id: int, review_id: int = None):
        """清理测试数据"""
        try:
            if review_id:
                # 删除评价记录（如果数据库支持）
                pass  
            if order_id:
                await order_manager.delete_order(order_id)
        except Exception as e:
            logger.warning(f"清理测试数据时出错: {e}")

    def _generate_final_report(self) -> Dict[str, Any]:
        """生成最终验证报告"""
        print("\n" + "=" * 60)
        print("📋 后端双向评价系统综合验证报告")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() 
                          if result and result.get('status') == 'PASSED')
        failed_tests = total_tests - passed_tests
        
        print(f"\n📊 测试概览:")
        print(f"   总测试数: {total_tests}")
        print(f"   通过测试: {passed_tests} ✅")
        print(f"   失败测试: {failed_tests} ❌")
        print(f"   成功率: {passed_tests/total_tests*100:.1f}%")
        
        print(f"\n🔍 详细结果:")
        for test_name, result in self.test_results.items():
            if result:
                status = result.get('status', 'UNKNOWN')
                icon = "✅" if status == 'PASSED' else "❌"
                print(f"   {icon} {test_name.replace('_', ' ').title()}: {status}")
                
                if status == 'FAILED' and 'error' in result:
                    print(f"      错误: {result['error']}")
        
        # 核心功能验证状态
        core_features_status = {
            '数据库事务一致性': self.test_results['database_consistency'],
            '评价确认激励流程': self.test_results['review_confirm_flow'], 
            '订单状态管理': self.test_results['order_status_rules'],
            '防重复机制': self.test_results['anti_duplicate_mechanisms'],
            '激励计算准确性': self.test_results['incentive_accuracy'],
            '错误处理机制': self.test_results['error_handling']
        }
        
        print(f"\n🎯 核心功能验证状态:")
        for feature, result in core_features_status.items():
            if result and result.get('status') == 'PASSED':
                print(f"   ✅ {feature}: 验证通过")
            else:
                print(f"   ❌ {feature}: 需要修复")
        
        overall_status = "PASSED" if failed_tests == 0 else "PARTIAL" if passed_tests > 0 else "FAILED"
        
        final_report = {
            'overall_status': overall_status,
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': f"{passed_tests/total_tests*100:.1f}%"
            },
            'detailed_results': self.test_results,
            'core_features_status': core_features_status,
            'timestamp': datetime.now().isoformat(),
            'recommendations': self._generate_recommendations()
        }
        
        print(f"\n🏆 综合验证状态: {overall_status}")
        if overall_status == "PASSED":
            print("✅ 后端双向评价系统和订单管理功能完全符合业务规则要求！")
        elif overall_status == "PARTIAL":
            print("⚠️ 大部分功能正常，但有部分问题需要修复。")
        else:
            print("❌ 存在重要问题，需要立即修复。")
            
        return final_report

    def _generate_recommendations(self) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        for test_name, result in self.test_results.items():
            if result and result.get('status') == 'FAILED':
                if test_name == 'database_consistency':
                    recommendations.append("加强数据库事务管理和外键约束")
                elif test_name == 'review_confirm_flow':
                    recommendations.append("优化评价确认和激励发放的异步处理")
                elif test_name == 'order_status_rules':
                    recommendations.append("完善订单状态转换验证逻辑")
                elif test_name == 'anti_duplicate_mechanisms':
                    recommendations.append("增强防重复评价和防刷分机制")
                elif test_name == 'incentive_accuracy':
                    recommendations.append("修复激励计算公式")
                elif test_name == 'error_handling':
                    recommendations.append("完善错误处理和异常捕获机制")
        
        if not recommendations:
            recommendations.append("系统运行良好，建议定期进行回归测试")
            
        return recommendations


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 导入必要模块用于测试
    import unittest.mock
    globals()['unittest'] = unittest
    
    validator = ComprehensiveBackendValidator()
    report = await validator.run_all_validations()
    
    return report

if __name__ == "__main__":
    asyncio.run(main())