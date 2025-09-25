# -*- coding: utf-8 -*-
"""
用户管理服务
从users_v2.py.old中提取的用户管理业务逻辑
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# 导入数据库管理器
from database.db_users import user_manager
from database.db_incentives import incentive_manager

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class UserMgmtService:
    """用户管理服务类"""
    
    CACHE_NAMESPACE = "user_mgmt"
    
    @staticmethod
    async def get_users_list(
        level_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        获取用户列表
        
        Args:
            level_filter: 等级筛选
            search_query: 搜索关键词
            page: 页码
            per_page: 每页数量
            
        Returns:
            dict: 用户列表数据
        """
        try:
            # 获取用户数据
            users = await user_manager.get_users_with_pagination(
                level_filter=level_filter,
                search=search_query,
                limit=per_page,
                offset=(page - 1) * per_page
            )
            
            # 获取总数
            total_users = await user_manager.count_users(
                level_filter=level_filter,
                search=search_query
            )
            
            # 获取等级列表用于筛选
            levels = await incentive_manager.get_all_levels()
            
            # 获取用户统计
            user_stats = await UserMgmtService._get_user_statistics()
            
            return {
                'users': users,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_users,
                    'pages': (total_users + per_page - 1) // per_page
                },
                'filters': {
                    'level_filter': level_filter,
                    'search_query': search_query
                },
                'levels': levels,
                'statistics': user_stats,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return {
                'users': [],
                'pagination': {'page': page, 'per_page': per_page, 'total': 0, 'pages': 0},
                'filters': {'level_filter': level_filter, 'search_query': search_query},
                'levels': [],
                'statistics': {},
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_user_detail(user_id: int) -> Dict[str, Any]:
        """
        获取用户详情
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 用户详情数据
        """
        try:
            user = await user_manager.get_user_profile(user_id)
            if not user:
                return {'success': False, 'error': '用户不存在'}
            
            # 获取用户的活动历史
            activity_history = await UserMgmtService._get_user_activity_history(user_id)
            
            # 获取用户的订单统计
            order_stats = await UserMgmtService._get_user_order_stats(user_id)
            
            # 获取用户的评价统计
            review_stats = await UserMgmtService._get_user_review_stats(user_id)
            
            # 获取用户的勋章
            badges = await incentive_manager.get_user_badges(user_id)
            
            return {
                'user': user,
                'activity_history': activity_history,
                'order_stats': order_stats,
                'review_stats': review_stats,
                'badges': badges,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取用户详情失败: user_id={user_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_user_info(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新用户信息
        
        Args:
            user_id: 用户ID
            data: 更新数据
            
        Returns:
            dict: 更新结果
        """
        try:
            result = await user_manager.update_user(user_id, data)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(UserMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"用户信息更新成功: user_id={user_id}")
                return {'success': True, 'message': '用户信息更新成功'}
            else:
                return {'success': False, 'error': '用户信息更新失败'}
                
        except Exception as e:
            logger.error(f"更新用户信息失败: user_id={user_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def adjust_user_points(user_id: int, points_change: int, reason: str) -> Dict[str, Any]:
        """
        调整用户积分
        
        Args:
            user_id: 用户ID
            points_change: 积分变化（正数增加，负数减少）
            reason: 调整原因
            
        Returns:
            dict: 调整结果
        """
        try:
            result = await user_manager.adjust_user_points(user_id, points_change, reason)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(UserMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                
                logger.info(f"用户积分调整成功: user_id={user_id}, change={points_change}, reason={reason}")
                return {'success': True, 'message': '积分调整成功'}
            else:
                return {'success': False, 'error': '积分调整失败'}
                
        except Exception as e:
            logger.error(f"调整用户积分失败: user_id={user_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def get_user_analytics() -> Dict[str, Any]:
        """
        获取用户分析数据
        
        Returns:
            dict: 用户分析数据
        """
        try:
            cache_key = "user_analytics"
            cached_data = CacheService.get(UserMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取用户分析数据
            analytics_data = {
                'total_users': await user_manager.count_users(),
                'active_users': await UserMgmtService._count_active_users(),
                'users_by_level': await UserMgmtService._get_users_by_level(),
                'users_by_registration_time': await UserMgmtService._get_users_by_registration_time(),
                'top_users': await UserMgmtService._get_top_users(),
                'subscription_stats': await UserMgmtService._get_subscription_stats(),
                'activity_trends': await UserMgmtService._get_activity_trends()
            }
            
            # 缓存10分钟
            CacheService.set(UserMgmtService.CACHE_NAMESPACE, cache_key, analytics_data, 600)
            return analytics_data
            
        except Exception as e:
            logger.error(f"获取用户分析数据失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def _get_user_statistics() -> Dict[str, Any]:
        """获取用户统计"""
        try:
            cache_key = "user_stats"
            cached_stats = CacheService.get(UserMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_stats is not None:
                return cached_stats
            
            # 按旧版字段命名统计（对齐web/app.py.old）
            stats = {
                'total_users': await user_manager.count_users(),
                'week_active_users': await UserMgmtService._count_active_users(7),  # 本周活跃
                'weekly_active': await UserMgmtService._count_active_users(7),      # 兼容旧版
                'avg_points': await UserMgmtService._get_average_points(),
                'high_level_users': await UserMgmtService._count_high_level_users() # 高等级用户
            }
            
            # 缓存5分钟
            CacheService.set(UserMgmtService.CACHE_NAMESPACE, cache_key, stats, 300)
            return stats
            
        except Exception as e:
            logger.error(f"获取用户统计失败: {e}")
            return {}
    
    @staticmethod
    async def _count_active_users(days: int = 30) -> int:
        """计算活跃用户数"""
        try:
            # 修正传参类型：传字符串日期给单日方法
            target_date = (datetime.now() - timedelta(days=days)).date().isoformat()
            return await user_manager.count_active_users_on_date(target_date)
        except Exception as e:
            logger.error(f"计算活跃用户数失败: {e}")
            return 0
    
    @staticmethod
    async def _count_subscribed_users() -> int:
        """计算已订阅用户数"""
        try:
            # TODO: 实现订阅用户统计逻辑
            return 0
        except Exception as e:
            logger.error(f"计算已订阅用户数失败: {e}")
            return 0
    
    @staticmethod
    async def _get_average_points() -> float:
        """获取平均积分"""
        try:
            # 使用用户统计方法获取平均积分
            stats = await user_manager.get_user_statistics()
            return stats.get('avg_points', 0.0)
        except Exception as e:
            logger.error(f"获取平均积分失败: {e}")
            return 0.0
    
    @staticmethod
    async def _get_average_experience() -> float:
        """获取平均经验值"""
        try:
            # 使用现有方法获取平均XP
            return await user_manager.get_average_xp()
        except Exception as e:
            logger.error(f"获取平均经验值失败: {e}")
            return 0.0
    
    @staticmethod
    async def _get_users_by_level() -> Dict[str, int]:
        """按等级统计用户"""
        try:
            # 使用现有方法获取等级分布
            return await user_manager.get_level_distribution()
        except Exception as e:
            logger.error(f"按等级统计用户失败: {e}")
            return {}
    
    @staticmethod
    async def _get_users_by_registration_time() -> Dict[str, int]:
        """按注册时间统计用户"""
        try:
            # TODO: 实现按注册时间统计用户
            return {}
        except Exception as e:
            logger.error(f"按注册时间统计用户失败: {e}")
            return {}
    
    @staticmethod
    async def _get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
        """获取顶级用户"""
        try:
            # 使用分页方法获取积分最高的用户
            users = await user_manager.get_users_with_pagination(
                limit=limit, 
                offset=0
            )
            # 按积分排序
            return sorted(users, key=lambda x: x.get('points', 0), reverse=True)[:limit]
        except Exception as e:
            logger.error(f"获取顶级用户失败: {e}")
            return []
    
    @staticmethod
    async def _get_subscription_stats() -> Dict[str, Any]:
        """获取订阅统计"""
        try:
            total_users = await user_manager.count_users()
            subscribed_users = await UserMgmtService._count_subscribed_users()
            subscription_rate = (subscribed_users / total_users * 100) if total_users > 0 else 0
            
            return {
                'total_users': total_users,
                'subscribed_users': subscribed_users,
                'unsubscribed_users': total_users - subscribed_users,
                'subscription_rate': round(subscription_rate, 2)
            }
        except Exception as e:
            logger.error(f"获取订阅统计失败: {e}")
            return {}
    
    @staticmethod
    async def _get_activity_trends() -> Dict[str, Any]:
        """获取活动趋势"""
        try:
            # 获取最近7天、30天的活跃用户数据
            return {
                'last_7_days': await UserMgmtService._count_active_users(7),
                'last_30_days': await UserMgmtService._count_active_users(30),
                'last_90_days': await UserMgmtService._count_active_users(90)
            }
        except Exception as e:
            logger.error(f"获取活动趋势失败: {e}")
            return {}
    
    @staticmethod
    async def _get_user_activity_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户活动历史"""
        try:
            # TODO: 实现用户活动历史获取逻辑
            return []
        except Exception as e:
            logger.error(f"获取用户活动历史失败: user_id={user_id}, error={e}")
            return []
    
    @staticmethod
    async def _get_user_order_stats(user_id: int) -> Dict[str, Any]:
        """获取用户订单统计"""
        try:
            # TODO: 实现用户订单统计逻辑
            return {
                'total_orders': 0,
                'completed_orders': 0,
                'pending_orders': 0
            }
        except Exception as e:
            logger.error(f"获取用户订单统计失败: user_id={user_id}, error={e}")
            return {}
    
    @staticmethod
    async def _get_user_review_stats(user_id: int) -> Dict[str, Any]:
        """获取用户评价统计"""
        try:
            # TODO: 实现用户评价统计逻辑
            return {
                'total_reviews': 0,
                'average_given_rating': 0.0,
                'average_received_rating': 0.0
            }
        except Exception as e:
            logger.error(f"获取用户评价统计失败: user_id={user_id}, error={e}")
            return {}
    
    @staticmethod
    async def _count_high_level_users() -> int:
        """计算高等级用户数（对齐旧版需求）"""
        try:
            # 使用XP范围统计高等级用户（XP > 1000为高等级）
            return await user_manager.count_users_by_xp_range(min_xp=1000, max_xp=999999)
        except Exception as e:
            logger.error(f"计算高等级用户数失败: {e}")
            return 0
    
    @staticmethod
    async def export_users_csv(
        level_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """导出用户CSV数据"""
        try:
            # 获取符合条件的所有用户
            users = await user_manager.get_users_with_pagination(
                level_filter=level_filter,
                search=search_query,
                limit=limit,
                offset=0
            )
            
            # 处理用户数据，计算勋章数等
            processed_users = []
            for user in users:
                # 解析勋章JSON
                import json
                badges_count = 0
                try:
                    badges = json.loads(user.get('badges', '[]')) if user.get('badges') else []
                    badges_count = len(badges)
                except:
                    badges_count = 0
                
                processed_user = {
                    'user_id': user.get('user_id', ''),
                    'username': user.get('username', ''),
                    'level_name': user.get('level_name', '新手'),
                    'xp': user.get('xp', 0),
                    'points': user.get('points', 0),
                    'order_count': user.get('order_count', 0),
                    'badges_count': badges_count,
                    'created_at': user.get('created_at', '')
                }
                processed_users.append(processed_user)
            
            return processed_users
            
        except Exception as e:
            logger.error(f"导出用户CSV数据失败: {e}")
            return []
    
    @staticmethod
    async def get_user_charts_dataset() -> Dict[str, Any]:
        """
        唯一数据方法：输出图表所需全部数据
        
        Returns:
            dict: 图表数据集，键与前端图表严格一一对应
        """
        try:
            from database.db_connection import db_manager
            
            # 1. 等级分布数据
            level_distribution = await user_manager.get_level_distribution()
            level_names = list(level_distribution.keys())
            level_counts = list(level_distribution.values())
            
            # 2. 用户活跃趋势（近30天，按天）
            activity_dates = []
            activity_counts = []
            for i in range(29, -1, -1):  # 30天倒序
                date = (datetime.now() - timedelta(days=i)).date().isoformat()
                count = await user_manager.count_active_users_on_date(date)
                activity_dates.append(date)
                activity_counts.append(count)
            
            # 3. 热门勋章（Top 10）
            popular_badges = await user_manager.get_popular_badges(limit=10)
            badge_names = [badge.get('badge_name', 'Unknown') for badge in popular_badges]
            badge_counts = [badge.get('user_count', 0) for badge in popular_badges]
            
            # 4. 积分分布（按区间统计）
            points_ranges = ['0-100', '101-500', '501-1000', '1001-5000', '5000+']
            points_counts = []
            points_counts.append(await user_manager.count_users_by_points_range(min_points=0, max_points=100))
            points_counts.append(await user_manager.count_users_by_points_range(min_points=101, max_points=500))
            points_counts.append(await user_manager.count_users_by_points_range(min_points=501, max_points=1000))
            points_counts.append(await user_manager.count_users_by_points_range(min_points=1001, max_points=5000))
            points_counts.append(await user_manager.count_users_by_points_range(min_points=5001))
            
            # 5. 评价活跃度（近7天，按天）
            review_activity_dates = []
            review_activity_counts = []
            for i in range(6, -1, -1):  # 7天倒序
                date = (datetime.now() - timedelta(days=i)).date().isoformat()
                # 直接使用db_manager统计当日评价数
                count = await db_manager.fetch_one(
                    "SELECT COUNT(*) as count FROM reviews WHERE date(created_at) = ?",
                    (date,)
                )
                review_activity_dates.append(date)
                review_activity_counts.append(count['count'] if count else 0)
            
            # 6. 经验值分布（按区间统计）
            xp_ranges = ['0-100', '101-500', '501-1000', '1001-5000', '5000+']
            xp_counts = []
            xp_counts.append(await user_manager.count_users_by_xp_range(min_xp=0, max_xp=100))
            xp_counts.append(await user_manager.count_users_by_xp_range(min_xp=101, max_xp=500))
            xp_counts.append(await user_manager.count_users_by_xp_range(min_xp=501, max_xp=1000))
            xp_counts.append(await user_manager.count_users_by_xp_range(min_xp=1001, max_xp=5000))
            xp_counts.append(await user_manager.count_users_by_xp_range(min_xp=5001))
            
            # 构造与前端图表严格对应的数据结构
            return {
                # 图表1: 等级分布
                'level_names': level_names,
                'level_counts': level_counts,
                
                # 图表2: 活跃趋势
                'activity_dates': activity_dates,
                'activity_counts': activity_counts,
                
                # 图表3: 热门勋章
                'badge_names': badge_names,
                'badge_counts': badge_counts,
                
                # 图表4: 积分分布
                'points_ranges': points_ranges,
                'points_counts': points_counts,
                
                # 图表5: 评价活跃度
                'review_activity_dates': review_activity_dates,
                'review_activity_counts': review_activity_counts,
                
                # 图表6: 经验值分布
                'xp_ranges': xp_ranges,
                'xp_counts': xp_counts
            }
            
        except Exception as e:
            logger.error(f"获取图表数据集失败: {e}")
            # 失败时抛出异常，由路由返回500
            raise Exception(f"图表数据获取失败: {e}")