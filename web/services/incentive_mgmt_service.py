# -*- coding: utf-8 -*-
"""
激励系统管理服务
从incentives.py.old中提取的激励系统管理业务逻辑
"""

import logging
import json
from typing import Dict, Any, List, Optional

# 导入数据库管理器
from database.db_incentives import incentive_manager
from database.db_users import user_manager
from database.db_connection import db_manager

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class IncentiveMgmtService:
    """激励系统管理服务类"""
    
    CACHE_NAMESPACE = "incentive_mgmt"
    
    @staticmethod
    async def get_incentives_analytics() -> Dict[str, Any]:
        """
        获取激励系统数据分析
        
        Returns:
            dict: 激励系统数据分析结果
        """
        try:
            # 获取统计数据
            stats = await IncentiveMgmtService._get_detailed_statistics()
            
            # 获取趋势数据
            trends = await IncentiveMgmtService._get_trends_data()
            
            # 获取等级分布
            level_distribution = await IncentiveMgmtService._get_detailed_level_distribution()
            
            # 获取勋章分布
            badge_distribution = await IncentiveMgmtService._get_detailed_badge_distribution()
            
            return {
                'success': True,
                'statistics': stats,
                'trends': trends,
                'level_distribution': level_distribution,
                'badge_distribution': badge_distribution
            }
            
        except Exception as e:
            logger.error(f"获取激励系统数据分析失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'statistics': {},
                'trends': {},
                'level_distribution': {},
                'badge_distribution': {}
            }
    
    @staticmethod
    async def get_incentives_dashboard() -> Dict[str, Any]:
        """
        获取激励系统仪表板数据
        
        Returns:
            dict: 激励系统仪表板数据
        """
        try:
            # 获取基础数据
            levels = await incentive_manager.get_all_levels()
            badges = await incentive_manager.get_all_badges_with_triggers()
            
            # 获取统计数据
            stats = await IncentiveMgmtService._get_incentive_statistics()
            
            # 获取用户等级分布
            level_distribution = await IncentiveMgmtService._get_level_distribution()
            
            # 获取勋章获得统计
            badge_stats = await IncentiveMgmtService._get_badge_statistics()
            
            return {
                'levels': levels,
                'badges': badges,
                'statistics': stats,
                'level_distribution': level_distribution,
                'badge_stats': badge_stats,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取激励系统仪表板数据失败: {e}")
            return {
                'levels': [],
                'badges': [],
                'statistics': {},
                'level_distribution': {},
                'badge_stats': {},
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_all_levels() -> Dict[str, Any]:
        """
        获取所有等级配置
        
        Returns:
            dict: 等级配置列表
        """
        try:
            levels = await incentive_manager.get_all_levels()
            return {
                'levels': levels,
                'total_levels': len(levels),
                'success': True
            }
        except Exception as e:
            logger.error(f"获取等级配置失败: {e}")
            return {
                'levels': [],
                'total_levels': 0,
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def create_level(name: str, required_experience: int, description: Optional[str] = None) -> Dict[str, Any]:
        """
        创建新等级
        
        Args:
            name: 等级名称
            required_experience: 所需经验值
            description: 等级描述（暂不使用，保持API兼容性）
            
        Returns:
            dict: 创建结果
        """
        try:
            # 调用数据库管理器的add_level方法（不支持description参数）
            level_id = await incentive_manager.add_level(name, required_experience)
            
            if level_id:
                # 清除相关缓存
                CacheService.clear_namespace(IncentiveMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"等级创建成功: name={name}, level_id={level_id}")
                return {
                    'success': True,
                    'message': '等级创建成功',
                    'level_id': level_id
                }
            else:
                return {'success': False, 'error': '等级创建失败'}
                
        except ValueError as e:
            logger.error(f"创建等级验证失败: name={name}, error={e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"创建等级失败: name={name}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_level(level_id: int, name: str, required_experience: int, description: Optional[str] = None) -> Dict[str, Any]:
        """
        更新等级
        
        Args:
            level_id: 等级ID
            name: 等级名称
            required_experience: 所需经验值
            description: 等级描述（暂不使用，保持API兼容性）
            
        Returns:
            dict: 更新结果
        """
        try:
            # 调用数据库管理器的update_level方法（参数名为new_name, new_xp）
            result = await incentive_manager.update_level(level_id, name, required_experience)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(IncentiveMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"等级更新成功: level_id={level_id}, name={name}")
                return {'success': True, 'message': '等级更新成功'}
            else:
                return {'success': False, 'error': '等级更新失败'}
                
        except ValueError as e:
            logger.error(f"更新等级验证失败: level_id={level_id}, error={e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"更新等级失败: level_id={level_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def delete_level(level_id: int) -> Dict[str, Any]:
        """
        删除等级
        
        Args:
            level_id: 等级ID
            
        Returns:
            dict: 删除结果
        """
        try:
            # 检查是否有用户使用该等级（先获取等级名称）
            level_query = "SELECT level_name FROM user_levels WHERE id = ?"
            level_result = await db_manager.fetch_one(level_query, (level_id,))
            if level_result:
                level_name = level_result['level_name']
                count_query = "SELECT COUNT(*) as count FROM users WHERE level_name = ?"
                count_result = await db_manager.fetch_one(count_query, (level_name,))
                users_with_level = count_result['count'] if count_result else 0
                if users_with_level > 0:
                    return {'success': False, 'error': f'该等级被 {users_with_level} 个用户使用，无法删除'}
            
            result = await incentive_manager.delete_level(level_id)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(IncentiveMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"等级删除成功: level_id={level_id}")
                return {'success': True, 'message': '等级删除成功'}
            else:
                return {'success': False, 'error': '等级删除失败'}
                
        except Exception as e:
            logger.error(f"删除等级失败: level_id={level_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def get_all_badges_with_triggers() -> Dict[str, Any]:
        """
        获取所有勋章及其触发器
        
        Returns:
            dict: 勋章及触发器列表
        """
        try:
            badges = await incentive_manager.get_all_badges_with_triggers()
            return {
                'badges': badges,
                'total_badges': len(badges),
                'success': True
            }
        except Exception as e:
            logger.error(f"获取勋章配置失败: {e}")
            return {
                'badges': [],
                'total_badges': 0,
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def create_badge(name: str, description: str, icon: str, rarity: str = 'common') -> Dict[str, Any]:
        """
        创建新勋章
        
        Args:
            name: 勋章名称
            description: 勋章描述
            icon: 勋章图标
            rarity: 稀有度（暂不使用，保持API兼容性）
            
        Returns:
            dict: 创建结果
        """
        try:
            # 调用数据库管理器的add_badge方法（参数为badge_name, badge_icon, description）
            badge_id = await incentive_manager.add_badge(name, icon, description)
            
            if badge_id:
                # 清除相关缓存
                CacheService.clear_namespace(IncentiveMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"勋章创建成功: name={name}, badge_id={badge_id}")
                return {
                    'success': True,
                    'message': '勋章创建成功',
                    'badge_id': badge_id
                }
            else:
                return {'success': False, 'error': '勋章创建失败'}
                
        except ValueError as e:
            logger.error(f"创建勋章验证失败: name={name}, error={e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"创建勋章失败: name={name}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def create_badge_trigger(badge_id: int, trigger_type: str, trigger_condition: str, points_reward: int) -> Dict[str, Any]:
        """
        创建勋章触发器
        
        Args:
            badge_id: 勋章ID
            trigger_type: 触发类型
            trigger_condition: 触发条件（需要转换为数值）
            points_reward: 积分奖励（暂不使用，保持API兼容性）
            
        Returns:
            dict: 创建结果
        """
        try:
            # 将trigger_condition转换为数值（假设是字符串形式的数字）
            try:
                trigger_value = int(trigger_condition)
            except (ValueError, TypeError):
                return {'success': False, 'error': '触发条件必须是有效的数字'}
            
            # 调用数据库管理器的add_trigger方法（参数为badge_id, trigger_type, trigger_value）
            trigger_id = await incentive_manager.add_trigger(badge_id, trigger_type, trigger_value)
            
            if trigger_id:
                # 清除相关缓存
                CacheService.clear_namespace(IncentiveMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"勋章触发器创建成功: badge_id={badge_id}, trigger_id={trigger_id}")
                return {
                    'success': True,
                    'message': '勋章触发器创建成功',
                    'trigger_id': trigger_id
                }
            else:
                return {'success': False, 'error': '勋章触发器创建失败'}
                
        except ValueError as e:
            logger.error(f"创建勋章触发器验证失败: badge_id={badge_id}, error={e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"创建勋章触发器失败: badge_id={badge_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def get_user_incentive_info(user_id: int) -> Dict[str, Any]:
        """
        获取用户激励信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 用户激励信息
        """
        try:
            # 获取用户基本信息
            user = await user_manager.get_user_profile(user_id)
            if not user:
                return {'success': False, 'error': '用户不存在'}
            
            # 获取用户勋章（从users表的badges JSON字段解析）
            user_badges = []
            if user.get('badges'):
                try:
                    pass  # json已在文件顶部导入
                    user_badges = json.loads(user['badges'])
                except (json.JSONDecodeError, TypeError):
                    user_badges = []
            
            # 获取用户等级进度
            level_progress = await IncentiveMgmtService._calculate_level_progress(user)
            
            # 获取积分历史
            points_history = await IncentiveMgmtService._get_user_points_history(user_id)
            
            return {
                'user': user,
                'badges': user_badges,
                'level_progress': level_progress,
                'points_history': points_history,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取用户激励信息失败: user_id={user_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def award_badge_to_user(user_id: int, badge_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        授予用户勋章
        
        Args:
            user_id: 用户ID
            badge_id: 勋章ID
            reason: 授予原因
            
        Returns:
            dict: 授予结果
        """
        try:
            # 获取勋章信息
            badge_query = "SELECT badge_name FROM badges WHERE id = ?"
            badge_result = await db_manager.fetch_one(badge_query, (badge_id,))
            if not badge_result:
                return {'success': False, 'error': '勋章不存在'}
            
            badge_name = badge_result['badge_name']
            
            # 使用用户管理器的方法添加勋章
            await user_manager.update_user_level_and_badges(user_id, new_badge=badge_name)
            
            # 清除相关缓存
            CacheService.clear_namespace(IncentiveMgmtService.CACHE_NAMESPACE)
            
            logger.info(f"勋章授予成功: user_id={user_id}, badge_id={badge_id}")
            return {'success': True, 'message': '勋章授予成功'}
                
        except Exception as e:
            logger.error(f"授予勋章失败: user_id={user_id}, badge_id={badge_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def get_incentive_analytics() -> Dict[str, Any]:
        """
        获取激励系统分析数据（保持向后兼容）
        
        Returns:
            dict: 激励系统分析数据
        """
        try:
            cache_key = "incentive_analytics"
            cached_data = CacheService.get(IncentiveMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取激励系统分析数据
            analytics_data = {
                'level_distribution': await IncentiveMgmtService._get_level_distribution(),
                'badge_statistics': await IncentiveMgmtService._get_badge_statistics(),
                'points_distribution': await IncentiveMgmtService._get_points_distribution(),
                'activity_trends': await IncentiveMgmtService._get_activity_trends(),
                'top_achievers': await IncentiveMgmtService._get_top_achievers()
            }
            
            # 缓存15分钟
            CacheService.set(IncentiveMgmtService.CACHE_NAMESPACE, cache_key, analytics_data, 900)
            return analytics_data
            
        except Exception as e:
            logger.error(f"获取激励系统分析数据失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def _get_detailed_statistics() -> Dict[str, Any]:
        """获取详细统计数据"""
        try:
            # 获取用户总数
            user_count_query = "SELECT COUNT(*) as total FROM users"
            user_count_result = await db_manager.fetch_one(user_count_query)
            total_users = user_count_result['total'] if user_count_result else 0
            
            # 获取活跃用户数（有积分的用户）
            active_users_query = "SELECT COUNT(*) as active FROM users WHERE points > 0"
            active_users_result = await db_manager.fetch_one(active_users_query)
            active_users = active_users_result['active'] if active_users_result else 0
            
            # 获取平均等级
            avg_level_query = "SELECT AVG(level) as avg_level FROM users"
            avg_level_result = await db_manager.fetch_one(avg_level_query)
            avg_level = round(avg_level_result['avg_level'], 1) if avg_level_result and avg_level_result['avg_level'] else 0
            
            # 获取勋章总发放数
            badge_count_query = "SELECT COUNT(*) as total_badges FROM user_badges"
            badge_count_result = await db_manager.fetch_one(badge_count_query)
            total_badges_awarded = badge_count_result['total_badges'] if badge_count_result else 0
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'active_rate': round((active_users / total_users * 100), 1) if total_users > 0 else 0,
                'avg_level': avg_level,
                'total_badges_awarded': total_badges_awarded,
                'badge_award_rate': round((total_badges_awarded / total_users * 100), 1) if total_users > 0 else 0,
                'new_users_this_month': 0,  # 需要实现时间范围查询
                'level_growth': 0  # 需要实现时间序列查询
            }
            
        except Exception as e:
            logger.error(f"获取详细统计数据失败: {e}")
            return {}
    
    @staticmethod
    async def _get_trends_data() -> Dict[str, Any]:
        """获取趋势数据"""
        try:
            # 模拟7天的趋势数据
            dates = ['9-15', '9-16', '9-17', '9-18', '9-19', '9-20', '9-21']
            avg_points = [150, 155, 148, 162, 170, 165, 172]
            
            return {
                'dates': dates,
                'avg_points': avg_points
            }
            
        except Exception as e:
            logger.error(f"获取趋势数据失败: {e}")
            return {'dates': [], 'avg_points': []}
    
    @staticmethod
    async def _get_detailed_level_distribution() -> Dict[str, Any]:
        """获取详细等级分布（按 user_levels.xp_required 排序并编号）。"""
        try:
            levels_query = """
                SELECT 
                    COALESCE(u.level_name, '未设置') as level_name,
                    ul.xp_required as xp_required,
                    COUNT(*) as user_count,
                    AVG(u.points) as avg_points,
                    AVG(CASE WHEN u.badges IS NULL OR u.badges = '[]' THEN 0 
                             ELSE (LENGTH(u.badges) - LENGTH(REPLACE(u.badges, ',', '')) + 1) END) as avg_badges
                FROM users u
                LEFT JOIN user_levels ul ON u.level_name = ul.level_name
                GROUP BY level_name, xp_required
            """
            rows = await db_manager.fetch_all(levels_query)
            data = [dict(r) for r in rows] if rows else []
            # 按 xp_required（空视为极大）排序并编号
            def sort_key(x):
                xr = x.get('xp_required')
                return (xr if isinstance(xr, int) else 10**9, x.get('level_name') or '')
            data.sort(key=sort_key)
            total_users = sum(d.get('user_count', 0) for d in data) or 1
            levels = []
            for idx, d in enumerate(data, start=1):
                levels.append({
                    'level': idx,  # 按经验门槛顺序编号
                    'name': d.get('level_name') or f"等级{idx}",
                    'user_count': d.get('user_count', 0),
                    'percentage': round((d.get('user_count', 0) / total_users * 100), 1),
                    'avg_points': int(d.get('avg_points') or 0),
                    'avg_badges': round(d.get('avg_badges') or 0, 1)
                })
            return {'levels': levels}
        except Exception as e:
            logger.error(f"获取详细等级分布失败: {e}")
            return {'levels': []}
    
    @staticmethod
    async def _get_detailed_badge_distribution() -> Dict[str, Any]:
        """获取详细勋章分布"""
        try:
            badges_query = """
                SELECT 
                    b.badge_name,
                    COUNT(ub.id) as count
                FROM badges b
                LEFT JOIN user_badges ub ON b.id = ub.badge_id
                GROUP BY b.id, b.badge_name
                ORDER BY count DESC
            """
            
            badge_data = await db_manager.fetch_all(badges_query)
            
            badges = []
            for row in badge_data:
                badges.append({
                    'name': row['badge_name'],
                    'count': row['count']
                })
            
            return {'badges': badges}
            
        except Exception as e:
            logger.error(f"获取详细勋章分布失败: {e}")
            return {'badges': []}
    
    @staticmethod
    async def _get_incentive_statistics() -> Dict[str, Any]:
        """获取激励系统统计"""
        try:
            cache_key = "incentive_stats"
            cached_stats = CacheService.get(IncentiveMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_stats is not None:
                return cached_stats
            
            levels = await incentive_manager.get_all_levels()
            badges = await incentive_manager.get_all_badges_with_triggers()
            
            stats = {
                'total_levels': len(levels),
                'total_badges': len(badges),
                'total_users_with_badges': await IncentiveMgmtService._count_users_with_badges(),
                'average_user_level': await IncentiveMgmtService._get_average_user_level(),
                'most_common_level': await IncentiveMgmtService._get_most_common_level()
            }
            
            # 缓存10分钟
            CacheService.set(IncentiveMgmtService.CACHE_NAMESPACE, cache_key, stats, 600)
            return stats
            
        except Exception as e:
            logger.error(f"获取激励系统统计失败: {e}")
            return {}
    
    @staticmethod
    async def _get_level_distribution() -> Dict[str, int]:
        """获取等级分布"""
        try:
            # 使用用户管理器中已存在的方法
            return await user_manager.get_level_distribution()
        except Exception as e:
            logger.error(f"获取等级分布失败: {e}")
            return {}
    
    @staticmethod
    async def _get_badge_statistics() -> Dict[str, Any]:
        """获取勋章统计"""
        try:
            badges = await incentive_manager.get_all_badges_with_triggers()
            badge_stats = {}
            
            for badge in badges:
                user_count = await incentive_manager.count_users_with_badge(badge['id'])
                badge_stats[badge.get('badge_name') or str(badge.get('id'))] = user_count
            
            return badge_stats
        except Exception as e:
            logger.error(f"获取勋章统计失败: {e}")
            return {}
    
    @staticmethod
    async def _calculate_level_progress(user: Dict[str, Any]) -> Dict[str, Any]:
        """计算用户等级进度（基于 user_levels.level_name/xp_required）。"""
        try:
            current_xp = int(user.get('experience') or user.get('xp') or 0)
            current_level_name = user.get('level_name') or ''
            # 获取全部等级（按 xp_required 升序）
            levels = await incentive_manager.get_all_levels()  # [{'id','level_name','xp_required'}]
            if not levels:
                return {}
            # 找到当前等级索引
            idx = next((i for i, l in enumerate(levels) if l.get('level_name') == current_level_name), None)
            if idx is None:
                # 未匹配，视为第一个等级前
                idx = 0
            current_info = levels[idx]
            next_info = levels[idx + 1] if idx + 1 < len(levels) else None
            cur_req = int(current_info.get('xp_required') or 0)
            if next_info:
                next_req = int(next_info.get('xp_required') or 0)
                denom = max(1, next_req - cur_req)
                progress = ((current_xp - cur_req) / denom) * 100.0
                need = max(0, next_req - current_xp)
            else:
                progress = 100.0
                need = 0
            return {
                'current_level': current_info,
                'next_level': next_info,
                'current_experience': current_xp,
                'progress_percentage': float(min(100.0, max(0.0, progress))),
                'needed_experience': int(need)
            }
        except Exception as e:
            logger.error(f"计算用户等级进度失败: {e}")
            return {}
    
    @staticmethod
    async def _count_users_with_badges() -> int:
        """计算拥有勋章的用户数"""
        try:
            return await incentive_manager.count_users_with_any_badge()
        except Exception as e:
            logger.error(f"计算拥有勋章的用户数失败: {e}")
            return 0
    
    @staticmethod
    async def _get_average_user_level() -> float:
        """获取用户平均等级"""
        try:
            return await user_manager.get_average_level()
        except Exception as e:
            logger.error(f"获取用户平均等级失败: {e}")
            return 0.0
    
    @staticmethod
    async def _get_most_common_level() -> str:
        """获取最常见的等级"""
        try:
            level_distribution = await IncentiveMgmtService._get_level_distribution()
            if level_distribution:
                return max(level_distribution, key=level_distribution.get)
            return ''
        except Exception as e:
            logger.error(f"获取最常见的等级失败: {e}")
            return ''
    
    @staticmethod
    async def _get_points_distribution() -> Dict[str, Any]:
        """获取积分分布"""
        try:
            # TODO: 实现积分分布统计逻辑
            return {}
        except Exception as e:
            logger.error(f"获取积分分布失败: {e}")
            return {}
    
    @staticmethod
    async def _get_activity_trends() -> Dict[str, Any]:
        """获取活动趋势"""
        try:
            # TODO: 实现活动趋势统计逻辑
            return {}
        except Exception as e:
            logger.error(f"获取活动趋势失败: {e}")
            return {}
    
    @staticmethod
    async def _get_top_achievers(limit: int = 10) -> List[Dict[str, Any]]:
        """获取顶级成就者"""
        try:
            # 获取积分排行榜用户
            query = """
                SELECT user_id, username, points, xp, level_name
                FROM users 
                ORDER BY points DESC, xp DESC 
                LIMIT ?
            """
            results = await db_manager.fetch_all(query, (limit,))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取顶级成就者失败: {e}")
            return []
    
    @staticmethod
    async def _get_user_points_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户积分历史"""
        try:
            # TODO: 实现用户积分历史获取逻辑
            return []
        except Exception as e:
            logger.error(f"获取用户积分历史失败: user_id={user_id}, error={e}")
            return []
