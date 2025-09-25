"""
活动日志数据库操作模块
提供全面的日志记录和统计功能
支持按钮点击、用户交互和系统事件的记录与分析
"""

import logging
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum

from .db_connection import db_manager

# 配置日志
logger = logging.getLogger(__name__)

class ActionType(Enum):
    """活动类型枚举"""
    BUTTON_CLICK = "button_click"
    USER_INTERACTION = "user_interaction"
    MERCHANT_REGISTRATION = "merchant_registration"
    ORDER_CREATED = "order_created"
    ORDER_UPDATED = "order_updated"
    ADMIN_ACTION = "admin_action"
    SYSTEM_EVENT = "system_event"
    ERROR_EVENT = "error_event"
    LOGIN_EVENT = "login_event"
    BINDING_CODE_USED = "binding_code_used"
    AUTO_REPLY_TRIGGERED = "auto_reply_triggered"
    AUTO_REPLY_MANAGEMENT = "auto_reply_management"

class ActivityLogsDatabase:
    """
    活动日志数据库操作类
    处理所有与活动日志相关的数据库操作
    """
    
    @staticmethod
    async def log_button_click(
        user_id: int,
        button_id: str,
        merchant_id: Optional[int] = None,
        additional_details: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        记录按钮点击事件
        
        Args:
            user_id: 用户ID
            button_id: 按钮ID
            merchant_id: 相关商户ID（可选）
            additional_details: 额外详细信息（可选）
            
        Returns:
            日志记录ID
        """
        try:
            details = {
                'button_id': button_id,
                'click_timestamp': datetime.now().isoformat()
            }
            
            if additional_details:
                details.update(additional_details)
            
            log_id = await ActivityLogsDatabase._create_log_entry(
                user_id=user_id,
                action_type=ActionType.BUTTON_CLICK.value,
                details=details,
                button_id=button_id,
                merchant_id=merchant_id
            )
            
            logger.info(f"按钮点击记录成功，用户: {user_id}, 按钮: {button_id}")
            return log_id
            
        except Exception as e:
            logger.error(f"记录按钮点击失败: {e}")
            raise
    
    @staticmethod
    async def log_user_interaction(
        user_id: int,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        merchant_id: Optional[int] = None
    ) -> int:
        """
        记录用户交互事件
        
        Args:
            user_id: 用户ID
            action: 交互动作描述
            details: 详细信息（可选）
            merchant_id: 相关商户ID（可选）
            
        Returns:
            日志记录ID
        """
        try:
            interaction_details = {
                'action': action,
                'interaction_timestamp': datetime.now().isoformat()
            }
            
            if details:
                interaction_details.update(details)
            
            log_id = await ActivityLogsDatabase._create_log_entry(
                user_id=user_id,
                action_type=ActionType.USER_INTERACTION.value,
                details=interaction_details,
                merchant_id=merchant_id
            )
            
            logger.debug(f"用户交互记录成功，用户: {user_id}, 动作: {action}")
            return log_id
            
        except Exception as e:
            logger.error(f"记录用户交互失败: {e}")
            raise
    
    @staticmethod
    async def log_merchant_registration(
        user_id: int,
        merchant_id: int,
        binding_code: str,
        registration_details: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        记录商户注册事件
        
        Args:
            user_id: 用户ID
            merchant_id: 商户ID
            binding_code: 使用的绑定码
            registration_details: 注册详细信息（可选）
            
        Returns:
            日志记录ID
        """
        try:
            details = {
                'binding_code': binding_code,
                'merchant_id': merchant_id,
                'registration_timestamp': datetime.now().isoformat()
            }
            
            if registration_details:
                details.update(registration_details)
            
            log_id = await ActivityLogsDatabase._create_log_entry(
                user_id=user_id,
                action_type=ActionType.MERCHANT_REGISTRATION.value,
                details=details,
                merchant_id=merchant_id
            )
            
            logger.info(f"商户注册记录成功，用户: {user_id}, 商户: {merchant_id}")
            return log_id
            
        except Exception as e:
            logger.error(f"记录商户注册失败: {e}")
            raise
    
    @staticmethod
    async def log_order_event(
        user_id: int,
        order_id: int,
        merchant_id: int,
        event_type: str,  # 'created' 或 'updated'
        order_details: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        记录订单相关事件
        
        Args:
            user_id: 用户ID
            order_id: 订单ID
            merchant_id: 商户ID
            event_type: 事件类型（'created' 或 'updated'）
            order_details: 订单详细信息（可选）
            
        Returns:
            日志记录ID
        """
        try:
            action_type = ActionType.ORDER_CREATED.value if event_type == 'created' else ActionType.ORDER_UPDATED.value
            
            details = {
                'order_id': order_id,
                'event_type': event_type,
                'event_timestamp': datetime.now().isoformat()
            }
            
            if order_details:
                details.update(order_details)
            
            log_id = await ActivityLogsDatabase._create_log_entry(
                user_id=user_id,
                action_type=action_type,
                details=details,
                merchant_id=merchant_id
            )
            
            logger.info(f"订单事件记录成功，订单: {order_id}, 事件: {event_type}")
            return log_id
            
        except Exception as e:
            logger.error(f"记录订单事件失败: {e}")
            raise
    
    @staticmethod
    async def log_admin_action(
        admin_id: int,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        action_details: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        记录管理员操作事件
        
        Args:
            admin_id: 管理员ID
            action: 操作描述
            target_type: 操作目标类型（如 'merchant', 'button_config'）
            target_id: 操作目标ID
            action_details: 操作详细信息（可选）
            
        Returns:
            日志记录ID
        """
        try:
            details = {
                'action': action,
                'target_type': target_type,
                'target_id': target_id,
                'admin_timestamp': datetime.now().isoformat()
            }
            
            if action_details:
                details.update(action_details)
            
            log_id = await ActivityLogsDatabase._create_log_entry(
                user_id=admin_id,
                action_type=ActionType.ADMIN_ACTION.value,
                details=details
            )
            
            logger.info(f"管理员操作记录成功，管理员: {admin_id}, 操作: {action}")
            return log_id
            
        except Exception as e:
            logger.error(f"记录管理员操作失败: {e}")
            raise
    
    @staticmethod
    async def log_system_event(
        event_type: str,
        event_details: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
    ) -> int:
        """
        记录系统事件
        
        Args:
            event_type: 事件类型
            event_details: 事件详细信息（可选）
            user_id: 相关用户ID（可选）
            
        Returns:
            日志记录ID
        """
        try:
            details = {
                'event_type': event_type,
                'system_timestamp': datetime.now().isoformat()
            }
            
            if event_details:
                details.update(event_details)
            
            log_id = await ActivityLogsDatabase._create_log_entry(
                user_id=user_id,
                action_type=ActionType.SYSTEM_EVENT.value,
                details=details
            )
            
            logger.info(f"系统事件记录成功，事件: {event_type}")
            return log_id
            
        except Exception as e:
            logger.error(f"记录系统事件失败: {e}")
            raise
    
    @staticmethod
    async def log_error_event(
        error_type: str,
        error_message: str,
        user_id: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        记录错误事件
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
            user_id: 相关用户ID（可选）
            error_details: 错误详细信息（可选）
            
        Returns:
            日志记录ID
        """
        try:
            details = {
                'error_type': error_type,
                'error_message': error_message,
                'error_timestamp': datetime.now().isoformat()
            }
            
            if error_details:
                details.update(error_details)
            
            log_id = await ActivityLogsDatabase._create_log_entry(
                user_id=user_id,
                action_type=ActionType.ERROR_EVENT.value,
                details=details
            )
            
            logger.warning(f"错误事件记录成功，错误: {error_type}")
            return log_id
            
        except Exception as e:
            logger.error(f"记录错误事件失败: {e}")
            raise
    
    @staticmethod
    async def _create_log_entry(
        user_id: Optional[int],
        action_type: str,
        details: Dict[str, Any],
        button_id: Optional[str] = None,
        merchant_id: Optional[int] = None
    ) -> int:
        """
        创建日志条目的内部方法
        
        Args:
            user_id: 用户ID
            action_type: 动作类型
            details: 详细信息
            button_id: 按钮ID（可选）
            merchant_id: 商户ID（可选）
            
        Returns:
            日志记录ID
        """
        try:
            insert_query = """
                INSERT INTO activity_logs (user_id, action_type, details, button_id, merchant_id)
                VALUES (?, ?, ?, ?, ?)
            """
            
            details_json = json.dumps(details, ensure_ascii=False, default=str)
            
            params = (user_id, action_type, details_json, button_id, merchant_id)
            
            log_id = await db_manager.get_last_insert_id(insert_query, params)
            return log_id
            
        except Exception as e:
            logger.error(f"创建日志条目失败: {e}")
            raise
    
    @staticmethod
    async def get_user_activity_logs(
        user_id: int,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = 100
    ) -> List[Dict[str, Any]]:
        """
        获取用户活动日志
        
        Args:
            user_id: 用户ID
            action_type: 动作类型过滤（可选）
            start_date: 开始时间（可选）
            end_date: 结束时间（可选）
            limit: 返回数量限制
            
        Returns:
            活动日志列表
        """
        try:
            query = "SELECT * FROM activity_logs WHERE user_id = ?"
            params = [user_id]
            
            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)
            
            query += " ORDER BY timestamp DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            logs = []
            for row in results:
                log_dict = dict(row)
                # 解析JSON详细信息
                if log_dict['details']:
                    try:
                        log_dict['details'] = json.loads(log_dict['details'])
                    except json.JSONDecodeError:
                        logger.warning(f"无法解析日志详细信息，ID: {log_dict['id']}")
                        log_dict['details'] = {}
                logs.append(log_dict)
            
            logger.debug(f"获取用户活动日志成功，用户: {user_id}, 数量: {len(logs)}")
            return logs
            
        except Exception as e:
            logger.error(f"获取用户活动日志失败，用户: {user_id}, 错误: {e}")
            raise
    
    @staticmethod
    async def get_merchant_activity_logs(
        merchant_id: int,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = 100
    ) -> List[Dict[str, Any]]:
        """
        获取商户相关活动日志
        
        Args:
            merchant_id: 商户ID
            action_type: 动作类型过滤（可选）
            start_date: 开始时间（可选）
            end_date: 结束时间（可选）
            limit: 返回数量限制
            
        Returns:
            活动日志列表
        """
        try:
            query = "SELECT * FROM activity_logs WHERE merchant_id = ?"
            params = [merchant_id]
            
            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)
            
            query += " ORDER BY timestamp DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            logs = []
            for row in results:
                log_dict = dict(row)
                if log_dict['details']:
                    try:
                        log_dict['details'] = json.loads(log_dict['details'])
                    except json.JSONDecodeError:
                        log_dict['details'] = {}
                logs.append(log_dict)
            
            logger.debug(f"获取商户活动日志成功，商户: {merchant_id}, 数量: {len(logs)}")
            return logs
            
        except Exception as e:
            logger.error(f"获取商户活动日志失败，商户: {merchant_id}, 错误: {e}")
            raise
    
    @staticmethod
    async def get_button_click_statistics(
        button_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        merchant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取按钮点击统计
        
        Args:
            button_id: 按钮ID过滤（可选）
            start_date: 开始时间（可选）
            end_date: 结束时间（可选）
            merchant_id: 商户ID过滤（可选）
            
        Returns:
            按钮点击统计字典
        """
        try:
            # 设置默认时间范围
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # 基础查询条件
            base_where = "WHERE action_type = 'button_click' AND timestamp BETWEEN ? AND ?"
            base_params = [start_date, end_date]
            
            if button_id:
                base_where += " AND button_id = ?"
                base_params.append(button_id)
            
            if merchant_id:
                base_where += " AND merchant_id = ?"
                base_params.append(merchant_id)
            
            # 总点击数
            total_query = f"SELECT COUNT(*) as total FROM activity_logs {base_where}"
            total_result = await db_manager.fetch_one(total_query, tuple(base_params))
            total_clicks = total_result['total'] if total_result else 0
            
            # 唯一用户数
            unique_users_query = f"SELECT COUNT(DISTINCT user_id) as unique_users FROM activity_logs {base_where}"
            unique_users_result = await db_manager.fetch_one(unique_users_query, tuple(base_params))
            unique_users = unique_users_result['unique_users'] if unique_users_result else 0
            
            # 按按钮分组统计
            button_stats_query = f"""
                SELECT button_id, COUNT(*) as clicks, COUNT(DISTINCT user_id) as unique_users
                FROM activity_logs {base_where}
                GROUP BY button_id
                ORDER BY clicks DESC
            """
            button_stats_results = await db_manager.fetch_all(button_stats_query, tuple(base_params))
            button_stats = {row['button_id']: {'clicks': row['clicks'], 'unique_users': row['unique_users']} 
                           for row in button_stats_results}
            
            # 按日期分组统计
            daily_stats_query = f"""
                SELECT DATE(timestamp) as click_date, COUNT(*) as clicks
                FROM activity_logs {base_where}
                GROUP BY DATE(timestamp)
                ORDER BY click_date DESC
            """
            daily_stats_results = await db_manager.fetch_all(daily_stats_query, tuple(base_params))
            daily_stats = {row['click_date']: row['clicks'] for row in daily_stats_results}
            
            # 按小时分组统计（最近24小时）
            recent_24h = end_date - timedelta(hours=24)
            hourly_where = base_where + " AND timestamp >= ?"
            hourly_params = base_params + [recent_24h]
            
            hourly_stats_query = f"""
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as clicks
                FROM activity_logs {hourly_where}
                GROUP BY strftime('%H', timestamp)
                ORDER BY hour
            """
            hourly_stats_results = await db_manager.fetch_all(hourly_stats_query, tuple(hourly_params))
            hourly_stats = {f"{row['hour']}:00": row['clicks'] for row in hourly_stats_results}
            
            statistics = {
                'total_clicks': total_clicks,
                'unique_users': unique_users,
                'average_clicks_per_user': total_clicks / unique_users if unique_users > 0 else 0,
                'button_stats': button_stats,
                'daily_stats': daily_stats,
                'hourly_stats': hourly_stats,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
            logger.info(f"按钮点击统计生成成功，总点击数: {total_clicks}")
            return statistics
            
        except Exception as e:
            logger.error(f"获取按钮点击统计失败: {e}")
            raise
    
    @staticmethod
    async def get_activity_statistics(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取活动统计信息
        
        Args:
            start_date: 开始时间（可选）
            end_date: 结束时间（可选）
            action_type: 动作类型过滤（可选）
            
        Returns:
            活动统计字典
        """
        try:
            # 设置默认时间范围
            if not end_date:
                end_date = datetime.now()
            if not start_date:
                start_date = end_date - timedelta(days=30)
            
            # 基础查询条件
            base_where = "WHERE timestamp BETWEEN ? AND ?"
            base_params = [start_date, end_date]
            
            if action_type:
                base_where += " AND action_type = ?"
                base_params.append(action_type)
            
            # 总活动数
            total_query = f"SELECT COUNT(*) as total FROM activity_logs {base_where}"
            total_result = await db_manager.fetch_one(total_query, tuple(base_params))
            total_activities = total_result['total'] if total_result else 0
            
            # 按动作类型分组统计
            action_type_query = f"""
                SELECT action_type, COUNT(*) as count
                FROM activity_logs {base_where}
                GROUP BY action_type
                ORDER BY count DESC
            """
            action_type_results = await db_manager.fetch_all(action_type_query, tuple(base_params))
            action_type_stats = {row['action_type']: row['count'] for row in action_type_results}
            
            # 活跃用户统计
            active_users_query = f"SELECT COUNT(DISTINCT user_id) as active_users FROM activity_logs {base_where} AND user_id IS NOT NULL"
            active_users_result = await db_manager.fetch_one(active_users_query, tuple(base_params))
            active_users = active_users_result['active_users'] if active_users_result else 0
            
            # 最活跃用户
            top_users_query = f"""
                SELECT user_id, COUNT(*) as activity_count
                FROM activity_logs {base_where} AND user_id IS NOT NULL
                GROUP BY user_id
                ORDER BY activity_count DESC
                LIMIT 10
            """
            top_users_results = await db_manager.fetch_all(top_users_query, tuple(base_params))
            top_users = [{'user_id': row['user_id'], 'activity_count': row['activity_count']} 
                        for row in top_users_results]
            
            # 按日期分组统计
            daily_activity_query = f"""
                SELECT DATE(timestamp) as activity_date, COUNT(*) as count
                FROM activity_logs {base_where}
                GROUP BY DATE(timestamp)
                ORDER BY activity_date DESC
                LIMIT 30
            """
            daily_activity_results = await db_manager.fetch_all(daily_activity_query, tuple(base_params))
            daily_activity = {row['activity_date']: row['count'] for row in daily_activity_results}
            
            statistics = {
                'total_activities': total_activities,
                'action_type_stats': action_type_stats,
                'active_users': active_users,
                'top_users': top_users,
                'daily_activity': daily_activity,
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
            logger.info(f"活动统计生成成功，总活动数: {total_activities}")
            return statistics
            
        except Exception as e:
            logger.error(f"获取活动统计失败: {e}")
            raise
    
    @staticmethod
    async def cleanup_old_logs(days_to_keep: int = 90) -> int:
        """
        清理旧的日志记录
        
        Args:
            days_to_keep: 保留的天数
            
        Returns:
            清理的日志数量
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            delete_query = "DELETE FROM activity_logs WHERE timestamp < ?"
            result = await db_manager.execute_query(delete_query, (cutoff_date,))
            
            if result > 0:
                logger.info(f"清理旧日志成功，删除 {result} 条记录")
            else:
                logger.debug("没有需要清理的旧日志")
            
            return result
            
        except Exception as e:
            logger.error(f"清理旧日志失败: {e}")
            raise
    
    @staticmethod
    async def get_recent_activities(
        limit: int = 50,
        action_type: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取最近的活动记录
        
        Args:
            limit: 返回数量限制
            action_type: 动作类型过滤（可选）
            user_id: 用户ID过滤（可选）
            
        Returns:
            最近活动列表
        """
        try:
            query = "SELECT * FROM activity_logs WHERE 1=1"
            params = []
            
            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            activities = []
            for row in results:
                activity_dict = dict(row)
                if activity_dict['details']:
                    try:
                        activity_dict['details'] = json.loads(activity_dict['details'])
                    except json.JSONDecodeError:
                        activity_dict['details'] = {}
                activities.append(activity_dict)
            
            logger.debug(f"获取最近活动成功，数量: {len(activities)}")
            return activities
            
        except Exception as e:
            logger.error(f"获取最近活动失败: {e}")
            raise

# 创建全局实例
activity_logs_db = ActivityLogsDatabase()