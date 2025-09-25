# -*- coding: utf-8 -*-
"""
激励处理器 V2.0
实现完整的用户激励逻辑：积分奖励 -> 等级升级检查 -> 勋章触发检查

核心功能：
1. 处理用户获得积分和经验的完整流程
2. 自动检查用户是否达到升级条件
3. 自动检查用户是否触发勋章获得条件
4. 与双向评价系统紧密集成

符合文档要求：
- 只有在商家确认评价有效后才发放激励奖励
- 支持多种勋章触发条件（订单数、完美评价、总积分等）
- 完整的等级升级机制
"""

import logging
import json
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

from database.db_users import user_manager
from database.db_incentives import incentive_manager
from database.db_orders import order_manager
from database.db_reviews import review_manager

logger = logging.getLogger(__name__)

class IncentiveProcessor:
    """激励处理器 - 处理用户激励的核心业务逻辑"""

    @staticmethod
    async def process_confirmed_review_rewards(user_id: int, review_id: int, order_id: int) -> Dict[str, Any]:
        """
        处理商家确认评价后的完整激励流程
        
        这是双向评价系统的核心触发点：
        1. 为用户发放评价奖励（积分+经验）
        2. 检查用户是否达到升级条件
        3. 检查用户是否触发新勋章
        
        Args:
            user_id: 用户ID
            review_id: 评价ID
            order_id: 订单ID
            
        Returns:
            Dict: 处理结果，包含奖励详情、升级信息、新获得勋章等
        """
        try:
            logger.info(f"开始处理评价奖励: user_id={user_id}, review_id={review_id}, order_id={order_id}")
            
            # 初始化结果
            result = {
                'success': False,
                'rewards_granted': False,
                'level_upgraded': False,
                'new_badges': [],
                'error': None,
                'points_earned': 0,
                'xp_earned': 0,
                'old_level': None,
                'new_level': None
            }
            
            # 1. 发放评价基础奖励
            base_rewards = await IncentiveProcessor._calculate_review_base_rewards(review_id)
            if not base_rewards:
                result['error'] = "计算基础奖励失败"
                return result
            
            # 发放积分和经验
            reward_success = await user_manager.grant_rewards(
                user_id, base_rewards['xp'], base_rewards['points']
            )
            
            if not reward_success:
                result['error'] = "发放奖励失败"
                return result
            
            result['rewards_granted'] = True
            result['points_earned'] = base_rewards['points']
            result['xp_earned'] = base_rewards['xp']
            
            # 2. 检查等级升级
            level_result = await IncentiveProcessor._check_and_process_level_upgrade(user_id)
            if level_result['upgraded']:
                result['level_upgraded'] = True
                result['old_level'] = level_result['old_level']
                result['new_level'] = level_result['new_level']
                logger.info(f"用户等级升级: user_id={user_id}, {level_result['old_level']} -> {level_result['new_level']}")
            
            # 3. 检查勋章触发
            badge_result = await IncentiveProcessor._check_and_grant_badges(user_id)
            if badge_result['new_badges']:
                result['new_badges'] = badge_result['new_badges']
                logger.info(f"用户获得新勋章: user_id={user_id}, badges={[b['badge_name'] for b in badge_result['new_badges']]}")
            
            # 4. 更新用户订单统计
            await IncentiveProcessor._update_user_order_stats(user_id)
            
            result['success'] = True
            logger.info(f"评价奖励处理完成: user_id={user_id}, 积分+{base_rewards['points']}, 经验+{base_rewards['xp']}")
            
            return result
            
        except Exception as e:
            logger.error(f"处理评价奖励失败: user_id={user_id}, error={e}")
            result['error'] = str(e)
            return result

    @staticmethod
    async def _calculate_review_base_rewards(review_id: int) -> Optional[Dict[str, int]]:
        """
        计算评价基础奖励
        
        根据评价质量和完整度计算积分和经验奖励：
        - 基础奖励：完成评价 = 50积分 + 20经验
        - 质量奖励：高分评价额外奖励
        - 完整度奖励：有文字评价额外奖励
        """
        try:
            # 获取评价详情
            review = await review_manager.get_review_detail(review_id)
            if not review:
                logger.error(f"评价不存在: review_id={review_id}")
                return None
            
            # 基础奖励
            base_points = 50
            base_xp = 20
            
            # 计算评价平均分
            ratings = [
                review['rating_appearance'], review['rating_figure'], 
                review['rating_service'], review['rating_attitude'], review['rating_environment']
            ]
            valid_ratings = [r for r in ratings if r is not None and r > 0]
            
            if valid_ratings:
                avg_rating = sum(valid_ratings) / len(valid_ratings)
                
                # 高分评价奖励 (8分以上)
                if avg_rating >= 8.0:
                    base_points += 25  # 额外25积分
                    base_xp += 10      # 额外10经验
                    logger.debug(f"高分评价奖励: avg_rating={avg_rating:.1f}")
            
            # 文字评价奖励
            if review.get('text_review_by_user') and len(review['text_review_by_user'].strip()) >= 10:
                base_points += 15  # 额外15积分
                base_xp += 5       # 额外5经验
                logger.debug("文字评价奖励已加成")
            
            return {
                'points': base_points,
                'xp': base_xp
            }
            
        except Exception as e:
            logger.error(f"计算评价奖励失败: {e}")
            return None

    @staticmethod
    async def _check_and_process_level_upgrade(user_id: int) -> Dict[str, Any]:
        """
        检查并处理用户等级升级
        
        Returns:
            Dict: 升级结果，包含是否升级、旧等级、新等级
        """
        result = {'upgraded': False, 'old_level': None, 'new_level': None}
        
        try:
            # 获取用户当前状态
            user = await user_manager.get_user_profile(user_id)
            if not user:
                logger.error(f"用户不存在: user_id={user_id}")
                return result
            
            current_xp = user.get('xp', 0)
            current_level = user.get('level_name', '新手')
            result['old_level'] = current_level
            
            # 获取所有等级配置
            levels = await incentive_manager.get_all_levels()
            if not levels:
                logger.warning("没有配置等级，跳过升级检查")
                return result
            
            # 按经验值升序排序
            levels.sort(key=lambda x: x['xp_required'])
            
            # 找到用户应该达到的等级
            target_level = None
            for level in levels:
                if current_xp >= level['xp_required']:
                    target_level = level
                else:
                    break
            
            # 检查是否需要升级
            if target_level and target_level['level_name'] != current_level:
                # 执行升级
                await user_manager.update_user_level_and_badges(
                    user_id=user_id,
                    new_level_name=target_level['level_name']
                )
                
                result['upgraded'] = True
                result['new_level'] = target_level['level_name']
                
                logger.info(f"用户等级升级成功: user_id={user_id}, {current_level} -> {target_level['level_name']} (XP: {current_xp})")
            
            return result
            
        except Exception as e:
            logger.error(f"检查等级升级失败: user_id={user_id}, error={e}")
            return result

    @staticmethod
    async def _check_and_grant_badges(user_id: int) -> Dict[str, Any]:
        """
        检查并授予用户勋章
        
        支持的触发类型：
        - order_count: 完成订单数量
        - perfect_reviews: 完美评价数量 (5星评价)
        - total_points: 总积分数量
        - consecutive_reviews: 连续评价天数
        
        Returns:
            Dict: 勋章授予结果，包含新获得的勋章列表
        """
        result = {'new_badges': []}
        
        try:
            # 获取用户当前勋章
            user = await user_manager.get_user_profile(user_id)
            if not user:
                return result
            
            # 解析当前勋章列表
            current_badges_json = user.get('badges', '[]')
            if isinstance(current_badges_json, str):
                current_badge_names = set(json.loads(current_badges_json))
            else:
                current_badge_names = set(current_badges_json)  # 如果已经是列表
            
            # 获取所有勋章配置
            badges_with_triggers = await incentive_manager.get_all_badges_with_triggers()
            if not badges_with_triggers:
                return result
            
            # 收集用户统计数据（一次查询，多次使用）
            user_stats = await IncentiveProcessor._collect_user_statistics(user_id)
            
            # 检查每个勋章的触发条件
            for badge in badges_with_triggers:
                badge_name = badge['badge_name']
                
                # 跳过已获得的勋章
                if badge_name in current_badge_names:
                    continue
                
                # 检查所有触发条件
                badge_earned = False
                triggers = badge.get('triggers', [])
                
                if not triggers:
                    continue  # 没有触发条件的勋章跳过
                
                # 检查是否满足所有触发条件 (AND逻辑)
                for trigger in triggers:
                    trigger_type = trigger['trigger_type']
                    trigger_value = trigger['trigger_value']
                    
                    user_value = user_stats.get(trigger_type, 0)
                    if user_value >= trigger_value:
                        badge_earned = True
                    else:
                        badge_earned = False
                        break  # 任何一个条件不满足就停止检查
                
                # 如果满足条件，授予勋章
                if badge_earned:
                    await user_manager.update_user_level_and_badges(
                        user_id=user_id,
                        new_badge=badge_name
                    )
                    
                    result['new_badges'].append({
                        'badge_name': badge_name,
                        'badge_icon': badge.get('badge_icon', '🏆'),
                        'description': badge.get('description', ''),
                        'earned_at': datetime.now().isoformat()
                    })
                    
                    logger.info(f"用户获得新勋章: user_id={user_id}, badge={badge_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"检查勋章触发失败: user_id={user_id}, error={e}")
            return result

    @staticmethod
    async def _collect_user_statistics(user_id: int) -> Dict[str, int]:
        """
        收集用户统计数据用于勋章触发检查
        
        Returns:
            Dict: 用户统计数据
        """
        stats = {}
        
        try:
            # 获取用户基本信息
            user = await user_manager.get_user_profile(user_id)
            if user:
                stats['total_points'] = user.get('points', 0)
                stats['total_xp'] = user.get('xp', 0)
                stats['order_count'] = user.get('order_count', 0)
            
            # 获取订单统计
            user_orders = await order_manager.get_orders_by_user(user_id, status=None, limit=1000)
            completed_orders = [o for o in user_orders if o['status'] in ['已完成', '已评价', '双方评价', '单方评价']]
            stats['order_count'] = len(completed_orders)
            
            # 获取评价统计
            user_reviews = []  # 需要实现获取用户评价的方法
            perfect_reviews = 0
            for review in user_reviews:
                # 计算平均评分
                ratings = [
                    review.get('rating_appearance', 0), review.get('rating_figure', 0),
                    review.get('rating_service', 0), review.get('rating_attitude', 0), 
                    review.get('rating_environment', 0)
                ]
                valid_ratings = [r for r in ratings if r > 0]
                if valid_ratings:
                    avg_rating = sum(valid_ratings) / len(valid_ratings)
                    if avg_rating >= 9.5:  # 定义完美评价为9.5分以上
                        perfect_reviews += 1
            
            stats['perfect_reviews'] = perfect_reviews
            
            # 连续评价天数（简化实现，实际项目中需要更复杂的逻辑）
            stats['consecutive_reviews'] = 0  # TODO: 实现连续评价天数计算
            
            return stats
            
        except Exception as e:
            logger.error(f"收集用户统计数据失败: user_id={user_id}, error={e}")
            return {}

    @staticmethod
    async def _update_user_order_stats(user_id: int):
        """更新用户订单统计"""
        try:
            # 重新计算用户完成订单数
            user_orders = await order_manager.get_orders_by_user(user_id, status=None, limit=1000)
            completed_count = len([o for o in user_orders if o['status'] in ['已完成', '已评价', '双方评价', '单方评价']])
            
            # TODO: 需要在user_manager中添加更新order_count的方法
            # await user_manager.update_order_count(user_id, completed_count)
            
        except Exception as e:
            logger.error(f"更新用户订单统计失败: user_id={user_id}, error={e}")

    # ==================== 其他激励触发点 ==================== #

    @staticmethod
    async def process_order_completion_rewards(user_id: int, order_id: int) -> Dict[str, Any]:
        """
        处理订单完成奖励
        
        订单完成时的激励奖励（不依赖评价）：
        - 基础完成奖励
        - 首单奖励
        - 连续订单奖励
        """
        try:
            result = {
                'success': False,
                'points_earned': 0,
                'xp_earned': 0,
                'new_badges': []
            }
            
            # 基础订单完成奖励
            base_points = 10
            base_xp = 5
            
            # 检查是否是首单
            user_orders = await order_manager.get_orders_by_user(user_id)
            completed_orders = [o for o in user_orders if o['status'] in ['已完成', '已评价', '双方评价', '单方评价']]
            
            if len(completed_orders) == 1:  # 首单
                base_points += 50
                base_xp += 20
                logger.info(f"首单奖励: user_id={user_id}")
            
            # 发放奖励
            await user_manager.grant_rewards(user_id, base_xp, base_points)
            result['points_earned'] = base_points
            result['xp_earned'] = base_xp
            
            # 检查勋章触发
            badge_result = await IncentiveProcessor._check_and_grant_badges(user_id)
            result['new_badges'] = badge_result['new_badges']
            
            result['success'] = True
            return result
            
        except Exception as e:
            logger.error(f"处理订单完成奖励失败: user_id={user_id}, error={e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    async def process_merchant_review_rewards(merchant_id: int, review_id: int) -> Dict[str, Any]:
        """
        处理商家获得评价后的奖励
        
        商家收到好评时的激励：
        - 好评奖励积分
        - 服务质量勋章
        - 客户满意度等级提升
        """
        # TODO: 实现商家激励系统（如果需要）
        pass

# 创建全局实例
incentive_processor = IncentiveProcessor()