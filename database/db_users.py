# -*- coding: utf-8 -*-
"""
用户数据管理器 V2.0
负责与 `users` 表的交互，支持完整的用户管理、分析和激励系统。
"""

import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class UserManager:
    @staticmethod
    async def get_users_with_incentives() -> List[Dict[str, Any]]:
        """获取带有激励信息的用户列表"""
        query = """
            SELECT 
                user_id as id,
                first_name,
                last_name,
                username,
                level,
                points,
                xp as experience,
                badges
            FROM users 
            ORDER BY points DESC, level DESC
        """
        try:
            results = await db_manager.fetch_all(query)
            users = []
            for result in results:
                user_dict = dict(result)
                # 解析badges JSON字段
                try:
                    if user_dict.get('badges'):
                        user_dict['badges'] = json.loads(user_dict['badges'])
                    else:
                        user_dict['badges'] = []
                except (json.JSONDecodeError, TypeError):
                    user_dict['badges'] = []
                users.append(user_dict)
            return users
        except Exception as e:
            logger.error(f"获取用户激励列表时出错: {e}")
            return []
    
    @staticmethod
    async def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
        """高效获取单个用户的资料"""
        query = "SELECT * FROM users WHERE user_id = ?"
        try:
            result = await db_manager.fetch_one(query, (user_id,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取用户 {user_id} 资料时出错: {e}")
            return None

    @staticmethod
    async def create_or_update_user(user_id: int, username: str):
        """创建或更新用户信息，主要用于订单创建时确保用户存在"""
        query = """
            INSERT INTO users (user_id, username) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        """
        try:
            await db_manager.execute_query(query, (user_id, username))
        except Exception as e:
            logger.error(f"创建或更新用户 {user_id} 时出错: {e}")
            raise

    @staticmethod
    async def grant_rewards(user_id: int, xp_to_add: int, points_to_add: int) -> bool:
        """为用户增加经验和积分（成功返回True）。"""
        query = """
            UPDATE users SET xp = xp + ?, points = points + ? WHERE user_id = ?
        """
        try:
            await db_manager.execute_query(query, (xp_to_add, points_to_add, user_id))
            return True
        except Exception as e:
            logger.error(f"为用户 {user_id} 发放奖励时出错: {e}")
            raise

    @staticmethod
    async def update_user_level_and_badges(user_id: int, new_level_name: str = None, new_badge: str = None):
        """更新用户的等级名称或为其添加新勋章"""
        try:
            # 等级更新
            if new_level_name is not None:
                query = "UPDATE users SET level_name = ? WHERE user_id = ?"
                await db_manager.execute_query(query, (new_level_name, user_id))
            
            # 勋章更新：读-改-写事务
            if new_badge is not None:
                # 1. 读取当前勋章
                query = "SELECT badges FROM users WHERE user_id = ?"
                result = await db_manager.fetch_one(query, (user_id,))
                
                if result:
                    # 2. 在Python代码中解析JSON并添加新勋章
                    current_badges_json = result['badges'] or '[]'
                    current_badges = json.loads(current_badges_json)
                    
                    # 检查是否已存在，避免重复添加
                    if new_badge not in current_badges:
                        current_badges.append(new_badge)
                        # 3. 序列化为新的JSON字符串
                        new_badges_json = json.dumps(current_badges, ensure_ascii=False)
                        
                        # 4. 写回数据库
                        query = "UPDATE users SET badges = ? WHERE user_id = ?"
                        await db_manager.execute_query(query, (new_badges_json, user_id))
                        
        except Exception as e:
            logger.error(f"更新用户 {user_id} 等级和勋章时出错: {e}")
            raise

    # ==================== V2.0 扩展方法 - 用户管理界面支持 ==================== #
    
    @staticmethod
    async def get_users_with_pagination(limit: int = 20, offset: int = 0, 
                                      level_filter: str = None, search: str = None, 
                                      user_id_filter: int = None) -> List[Dict[str, Any]]:
        """分页获取用户列表，支持筛选和搜索"""
        try:
            where_conditions = []
            params = []
            
            # 构建WHERE条件
            if level_filter:
                where_conditions.append("u.level_name = ?")
                params.append(level_filter)
            
            if search:
                where_conditions.append("(u.username LIKE ? OR CAST(u.user_id AS TEXT) LIKE ?)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param])
                
            if user_id_filter:
                where_conditions.append("u.user_id = ?")
                params.append(user_id_filter)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    u.user_id, u.username, u.xp, u.points, u.level_name, u.badges,
                    u.created_at, u.updated_at,
                    COUNT(o.id) as order_count,
                    COUNT(r.id) as review_count
                FROM users u
                LEFT JOIN orders o ON u.user_id = o.customer_user_id
                LEFT JOIN reviews r ON u.user_id = r.customer_user_id
                {where_clause}
                GROUP BY u.user_id
                ORDER BY u.created_at DESC
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            results = await db_manager.fetch_all(query, tuple(params))
            
            users = []
            for row in results:
                user = dict(row)
                # 解析badges JSON
                try:
                    user['badges'] = json.loads(user['badges'] or '[]')
                except (json.JSONDecodeError, TypeError):
                    user['badges'] = []
                users.append(user)
            
            logger.debug(f"获取用户分页数据成功，返回 {len(users)} 条记录")
            return users
            
        except Exception as e:
            logger.error(f"获取用户分页数据失败: {e}")
            return []
    
    @staticmethod
    async def count_users(level_filter: str = None, search: str = None, user_id_filter: int = None) -> int:
        """统计用户总数，支持筛选"""
        try:
            where_conditions = []
            params = []
            
            if level_filter:
                where_conditions.append("level_name = ?")
                params.append(level_filter)
            
            if search:
                where_conditions.append("(username LIKE ? OR CAST(user_id AS TEXT) LIKE ?)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param])
                
            if user_id_filter:
                where_conditions.append("user_id = ?")
                params.append(user_id_filter)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"SELECT COUNT(*) as count FROM users {where_clause}"
            result = await db_manager.fetch_one(query, tuple(params))
            
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"统计用户总数失败: {e}")
            return 0
    
    @staticmethod
    async def get_user_with_details(user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户详细信息，包括订单和评价统计"""
        try:
            query = """
                SELECT 
                    u.*,
                    COUNT(DISTINCT o.id) as total_orders,
                    COUNT(DISTINCT r.id) as total_reviews,
                    AVG(CASE WHEN r.rating_appearance > 0 THEN (
                        r.rating_appearance + r.rating_figure + r.rating_service + 
                        r.rating_attitude + r.rating_environment
                    ) / 5.0 END) as avg_rating_given
                FROM users u
                LEFT JOIN orders o ON u.user_id = o.customer_user_id
                LEFT JOIN reviews r ON u.user_id = r.customer_user_id
                WHERE u.user_id = ?
                GROUP BY u.user_id
            """
            
            result = await db_manager.fetch_one(query, (user_id,))
            if not result:
                return None
            
            user = dict(result)
            # 解析badges JSON
            try:
                user['badges'] = json.loads(user['badges'] or '[]')
            except (json.JSONDecodeError, TypeError):
                user['badges'] = []
            
            return user
            
        except Exception as e:
            logger.error(f"获取用户 {user_id} 详细信息失败: {e}")
            return None
    
    @staticmethod
    async def get_user_statistics() -> Dict[str, Any]:
        """获取用户统计数据"""
        try:
            # 总用户数
            total_query = "SELECT COUNT(*) as total FROM users"
            total_result = await db_manager.fetch_one(total_query)
            total_users = total_result['total'] if total_result else 0
            
            # 活跃用户数（本周有活动的）
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            active_query = """
                SELECT COUNT(DISTINCT u.user_id) as active 
                FROM users u 
                LEFT JOIN orders o ON u.user_id = o.customer_user_id 
                LEFT JOIN reviews r ON u.user_id = r.customer_user_id
                WHERE o.created_at >= ? OR r.created_at >= ?
            """
            active_result = await db_manager.fetch_one(active_query, (week_ago, week_ago))
            weekly_active = active_result['active'] if active_result else 0
            
            # 平均积分
            points_query = "SELECT AVG(points) as avg_points FROM users WHERE points > 0"
            points_result = await db_manager.fetch_one(points_query)
            avg_points = points_result['avg_points'] or 0
            
            # 高等级用户数
            high_level_query = """
                SELECT COUNT(*) as high_level 
                FROM users u 
                JOIN user_levels ul ON u.level_name = ul.level_name 
                WHERE ul.xp_required >= 500
            """
            high_level_result = await db_manager.fetch_one(high_level_query)
            high_level_users = high_level_result['high_level'] if high_level_result else 0
            
            return {
                'total_users': total_users,
                'weekly_active': weekly_active,
                'avg_points': round(avg_points, 1),
                'high_level_users': high_level_users
            }
            
        except Exception as e:
            logger.error(f"获取用户统计数据失败: {e}")
            return {
                'total_users': 0,
                'weekly_active': 0, 
                'avg_points': 0,
                'high_level_users': 0
            }
    
    # ==================== V2.0 分析数据方法 ==================== #
    
    @staticmethod
    async def get_level_distribution() -> Dict[str, int]:
        """获取用户等级分布（映射：level_name -> count）"""
        try:
            query = """
                SELECT COALESCE(level_name, '未设置') as level_name, COUNT(*) as user_count
                FROM users
                GROUP BY level_name
            """
            results = await db_manager.fetch_all(query)
            return {row['level_name']: row['user_count'] for row in results}
            
        except Exception as e:
            logger.error(f"获取等级分布数据失败: {e}")
            return {}
    
    @staticmethod
    async def count_active_users_on_date(date_str: str) -> int:
        """统计指定日期的活跃用户数"""
        try:
            next_date = (datetime.fromisoformat(date_str) + timedelta(days=1)).isoformat()
            
            query = """
                SELECT COUNT(DISTINCT u.user_id) as active_count
                FROM users u
                LEFT JOIN orders o ON u.user_id = o.customer_user_id
                LEFT JOIN reviews r ON u.user_id = r.customer_user_id  
                WHERE (o.created_at >= ? AND o.created_at < ?) OR 
                      (r.created_at >= ? AND r.created_at < ?)
            """
            
            result = await db_manager.fetch_one(query, (date_str, next_date, date_str, next_date))
            return result['active_count'] if result else 0
            
        except Exception as e:
            logger.error(f"统计活跃用户数失败: {e}")
            return 0
    
    @staticmethod
    async def get_popular_badges(limit: int = 10) -> List[Dict[str, Any]]:
        """获取热门勋章排行"""
        try:
            # 从用户badges JSON字段中统计
            query = "SELECT user_id, badges FROM users WHERE badges IS NOT NULL AND badges != '[]'"
            results = await db_manager.fetch_all(query)
            
            badge_counts = {}
            for row in results:
                try:
                    badges = json.loads(row['badges'] or '[]')
                    for badge in badges:
                        if badge:
                            badge_counts[badge] = badge_counts.get(badge, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    continue
            
            # 排序并限制数量
            sorted_badges = sorted(badge_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            
            # 获取勋章详细信息
            popular_badges = []
            for badge_name, count in sorted_badges:
                # 从badges表获取勋章图标
                badge_query = "SELECT badge_icon FROM badges WHERE badge_name = ?"
                badge_result = await db_manager.fetch_one(badge_query, (badge_name,))
                
                popular_badges.append({
                    'badge_name': badge_name,
                    'badge_icon': badge_result['badge_icon'] if badge_result else '🏆',
                    'user_count': count
                })
            
            return popular_badges
            
        except Exception as e:
            logger.error(f"获取热门勋章失败: {e}")
            return []
    
    @staticmethod
    async def count_users_by_points_range(min_points: int, max_points: Optional[int] = None) -> int:
        """按积分范围统计用户数"""
        try:
            if max_points is None:
                query = "SELECT COUNT(*) as count FROM users WHERE points >= ?"
                params = (min_points,)
            else:
                query = "SELECT COUNT(*) as count FROM users WHERE points >= ? AND points <= ?"
                params = (min_points, max_points)
            
            result = await db_manager.fetch_one(query, params)
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"按积分范围统计用户数失败: {e}")
            return 0
    
    @staticmethod
    async def count_users_by_xp_range(min_xp: int, max_xp: Optional[int] = None) -> int:
        """按经验值范围统计用户数"""
        try:
            if max_xp is None:
                query = "SELECT COUNT(*) as count FROM users WHERE xp >= ?"
                params = (min_xp,)
            else:
                query = "SELECT COUNT(*) as count FROM users WHERE xp >= ? AND xp <= ?"
                params = (min_xp, max_xp)
            
            result = await db_manager.fetch_one(query, params)
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"按经验值范围统计用户数失败: {e}")
            return 0
    
    @staticmethod
    async def count_users_with_activity() -> int:
        """统计有活动的用户数（有积分或经验的用户）"""
        try:
            query = "SELECT COUNT(*) as count FROM users WHERE xp > 0 OR points > 0"
            result = await db_manager.fetch_one(query)
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"统计活跃用户数失败: {e}")
            return 0
    
    @staticmethod
    async def get_average_xp() -> float:
        """获取平均经验值"""
        try:
            query = "SELECT AVG(xp) as avg_xp FROM users WHERE xp > 0"
            result = await db_manager.fetch_one(query)
            return result['avg_xp'] or 0
            
        except Exception as e:
            logger.error(f"获取平均经验值失败: {e}")
            return 0

    # ==================== 兼容/便捷方法（供Web服务调用） ==================== #

    @staticmethod
    async def get_all_users(limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """获取用户简要列表（用于筛选下拉等）"""
        try:
            query = """
                SELECT user_id, username, level_name, xp, points, badges, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            results = await db_manager.fetch_all(query, (int(limit), int(offset or 0)))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return []

    @staticmethod
    async def get_users_count_by_level() -> Dict[str, int]:
        """按等级统计用户数量（level_name -> count）"""
        return await UserManager.get_level_distribution()

    @staticmethod
    async def get_average_level() -> float:
        """估算平均等级（以user_levels.xp_required加权的平均水平）"""
        try:
            query = """
                SELECT AVG(ul.xp_required) as avg_level_metric
                FROM users u
                LEFT JOIN user_levels ul ON u.level_name = ul.level_name
                WHERE ul.xp_required IS NOT NULL
            """
            result = await db_manager.fetch_one(query)
            return float(result['avg_level_metric']) if result and result['avg_level_metric'] is not None else 0.0
        except Exception as e:
            logger.error(f"计算平均等级失败: {e}")
            return 0.0

    @staticmethod
    async def count_subscribed_users() -> int:
        """
        统计已订阅用户数（占位实现）
        说明：当前系统未持久化订阅状态，此处返回0以避免接口报错。
        后续若引入订阅持久化，可在此实现实际统计逻辑。
        """
        try:
            return 0
        except Exception:
            return 0

user_manager = UserManager()
