"""
自动回复数据库操作模块
提供自动回复触发词和消息管理的CRUD操作，包括匹配、统计和管理功能
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, date, timedelta

# 导入数据库连接管理器
from .db_connection import db_manager

# 配置日志
logger = logging.getLogger(__name__)

class AutoReplyManager:
    """自动回复管理器类，提供所有自动回复相关的数据库操作"""
    
    # ===== 触发词管理 =====
    
    @staticmethod
    async def create_trigger(
        trigger_text: str,
        match_type: str,
        created_by: int,
        priority_order: int = 0,
        is_active: bool = True
    ) -> Optional[int]:
        """
        创建新的自动回复触发词
        
        Args:
            trigger_text: 触发词内容
            match_type: 匹配类型 ('exact' 或 'contains')
            created_by: 创建者管理员ID
            priority_order: 优先级排序（数字越小优先级越高）
            is_active: 是否启用
            
        Returns:
            新创建触发词的ID，失败时返回None
        """
        try:
            # 验证匹配类型
            if match_type not in ['exact', 'contains']:
                logger.error(f"无效的匹配类型: {match_type}")
                return None
            
            # 检查触发词是否已存在
            existing = await AutoReplyManager.get_trigger_by_text(trigger_text, match_type)
            if existing:
                logger.warning(f"触发词已存在: {trigger_text}")
                return existing['id']
            
            # 修复：添加admin_id字段，与created_by使用相同值
            query = """
                INSERT INTO auto_reply_triggers (admin_id, trigger_text, match_type, created_by, priority_order, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            
            params = (created_by, trigger_text, match_type, created_by, priority_order, is_active)
            trigger_id = await db_manager.get_last_insert_id(query, params)
            
            logger.info(f"触发词创建成功，ID: {trigger_id}, 内容: {trigger_text}")
            return trigger_id
            
        except Exception as e:
            logger.error(f"创建触发词失败: {e}")
            return None
    
    @staticmethod
    async def get_trigger(trigger_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取触发词信息
        
        Args:
            trigger_id: 触发词ID
            
        Returns:
            触发词信息字典，不存在时返回None
        """
        try:
            query = """
                SELECT id, trigger_text, match_type, is_active, priority_order,
                       trigger_count, last_triggered_at, created_by, created_at, updated_at
                FROM auto_reply_triggers WHERE id = ?
            """
            
            result = await db_manager.fetch_one(query, (trigger_id,))
            
            if result:
                return dict(result)
            return None
            
        except Exception as e:
            logger.error(f"获取触发词失败，ID: {trigger_id}, 错误: {e}")
            return None
    
    @staticmethod
    async def get_trigger_by_text(trigger_text: str, match_type: str) -> Optional[Dict[str, Any]]:
        """
        根据触发词内容和匹配类型获取触发词信息
        
        Args:
            trigger_text: 触发词内容
            match_type: 匹配类型
            
        Returns:
            触发词信息字典，不存在时返回None
        """
        try:
            query = """
                SELECT id, admin_id, trigger_text, match_type, is_active, priority_order,
                       trigger_count, last_triggered_at, created_by, created_at, updated_at
                FROM auto_reply_triggers 
                WHERE trigger_text = ? AND match_type = ?
            """
            
            result = await db_manager.fetch_one(query, (trigger_text, match_type))
            
            if result:
                return dict(result)
            return None
            
        except Exception as e:
            logger.error(f"根据内容获取触发词失败: {e}")
            return None
    
    @staticmethod
    async def get_all_active_triggers(admin_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有活跃的触发词，按优先级排序
        
        Args:
            admin_id: 可选的管理员ID过滤
            
        Returns:
            触发词列表，按priority_order升序排序
        """
        try:
            query = """
                SELECT id, admin_id, trigger_text, match_type, is_active, priority_order,
                       trigger_count, last_triggered_at, created_by, created_at, updated_at
                FROM auto_reply_triggers 
                WHERE is_active = TRUE
            """
            params = []
            
            if admin_id is not None:
                query += " AND (created_by = ? OR admin_id = ?)"
                params.extend([admin_id, admin_id])
            
            query += " ORDER BY priority_order ASC, created_at ASC"
            
            results = await db_manager.fetch_all(query, tuple(params) if params else ())
            
            triggers = [dict(row) for row in results]
            logger.debug(f"获取活跃触发词成功，数量: {len(triggers)}")
            return triggers
            
        except Exception as e:
            logger.error(f"获取活跃触发词失败: {e}")
            return []
    
    @staticmethod
    async def get_all_triggers(admin_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取所有触发词（包括非活跃的），按优先级排序
        
        Args:
            admin_id: 可选的管理员ID过滤
            
        Returns:
            触发词列表，按priority_order升序排序，包含关联的消息
        """
        try:
            query = """
                SELECT id, trigger_text, match_type, is_active, priority_order,
                       trigger_count, last_triggered_at, created_by, created_at, updated_at
                FROM auto_reply_triggers
            """
            params = []
            
            if admin_id is not None:
                query += " WHERE created_by = ?"
                params.append(admin_id)
            
            query += " ORDER BY priority_order ASC, created_at ASC"
            
            results = await db_manager.fetch_all(query, tuple(params) if params else ())
            
            triggers = []
            for row in results:
                trigger = dict(row)
                
                # 获取该触发词的所有消息
                messages = await AutoReplyManager.get_messages_by_trigger(trigger['id'])
                trigger['messages'] = messages
                
                triggers.append(trigger)
            
            logger.debug(f"获取所有触发词成功，数量: {len(triggers)}")
            return triggers
            
        except Exception as e:
            logger.error(f"获取所有触发词失败: {e}")
            return []
    
    @staticmethod
    async def update_trigger(
        trigger_id: int,
        trigger_text: Optional[str] = None,
        match_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        priority_order: Optional[int] = None
    ) -> bool:
        """
        更新触发词信息
        
        Args:
            trigger_id: 触发词ID
            trigger_text: 新的触发词内容（可选）
            match_type: 新的匹配类型（可选）
            is_active: 新的启用状态（可选）
            priority_order: 新的优先级排序（可选）
            
        Returns:
            更新是否成功
        """
        try:
            update_fields = []
            params = []
            
            if trigger_text is not None:
                update_fields.append("trigger_text = ?")
                params.append(trigger_text)
            
            if match_type is not None:
                if match_type not in ['exact', 'contains']:
                    logger.error(f"无效的匹配类型: {match_type}")
                    return False
                update_fields.append("match_type = ?")
                params.append(match_type)
            
            if is_active is not None:
                update_fields.append("is_active = ?")
                params.append(is_active)
            
            if priority_order is not None:
                update_fields.append("priority_order = ?")
                params.append(priority_order)
            
            if not update_fields:
                logger.warning("没有提供要更新的字段")
                return False
            
            query = f"""
                UPDATE auto_reply_triggers 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """
            params.append(trigger_id)
            
            affected_rows = await db_manager.execute_query(query, tuple(params))
            
            if affected_rows > 0:
                logger.info(f"触发词更新成功，ID: {trigger_id}")
                return True
            else:
                logger.warning(f"触发词不存在或无需更新，ID: {trigger_id}")
                return False
            
        except Exception as e:
            logger.error(f"更新触发词失败，ID: {trigger_id}, 错误: {e}")
            return False
    
    @staticmethod
    async def delete_trigger(trigger_id: int) -> bool:
        """
        删除触发词及其所有相关消息
        
        Args:
            trigger_id: 触发词ID
            
        Returns:
            删除是否成功
        """
        try:
            # 首先删除相关消息（外键约束会自动处理，但为了记录日志）
            messages = await AutoReplyManager.get_messages_by_trigger(trigger_id)
            
            query = "DELETE FROM auto_reply_triggers WHERE id = ?"
            affected_rows = await db_manager.execute_query(query, (trigger_id,))
            
            if affected_rows > 0:
                logger.info(f"触发词删除成功，ID: {trigger_id}, 同时删除了 {len(messages)} 条消息")
                return True
            else:
                logger.warning(f"触发词不存在，ID: {trigger_id}")
                return False
            
        except Exception as e:
            logger.error(f"删除触发词失败，ID: {trigger_id}, 错误: {e}")
            return False
    
    # ===== 消息管理 =====
    
    @staticmethod
    async def create_message(
        trigger_id: int,
        message_content: str,
        display_order: int = 0,
        is_active: bool = True
    ) -> Optional[int]:
        """
        为触发词创建新的回复消息
        
        Args:
            trigger_id: 触发词ID
            message_content: 消息内容
            display_order: 显示顺序
            is_active: 是否启用
            
        Returns:
            新创建消息的ID，失败时返回None
        """
        try:
            # 验证触发词存在
            trigger = await AutoReplyManager.get_trigger(trigger_id)
            if not trigger:
                logger.error(f"触发词不存在，ID: {trigger_id}")
                return None
            
            query = """
                INSERT INTO auto_reply_messages (trigger_id, message_content, display_order, is_active)
                VALUES (?, ?, ?, ?)
            """
            
            params = (trigger_id, message_content, display_order, is_active)
            message_id = await db_manager.get_last_insert_id(query, params)
            
            logger.info(f"回复消息创建成功，ID: {message_id}, 触发词ID: {trigger_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"创建回复消息失败: {e}")
            return None
    
    @staticmethod
    async def get_message(message_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取回复消息信息
        
        Args:
            message_id: 消息ID
            
        Returns:
            消息信息字典，不存在时返回None
        """
        try:
            query = """
                SELECT id, trigger_id, message_content, is_active, display_order,
                       send_count, last_sent_at, created_at, updated_at
                FROM auto_reply_messages WHERE id = ?
            """
            
            result = await db_manager.fetch_one(query, (message_id,))
            
            if result:
                return dict(result)
            return None
            
        except Exception as e:
            logger.error(f"获取回复消息失败，ID: {message_id}, 错误: {e}")
            return None
    
    @staticmethod
    async def get_messages_by_trigger(
        trigger_id: int, 
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取指定触发词的所有回复消息
        
        Args:
            trigger_id: 触发词ID
            active_only: 是否只获取活跃的消息
            
        Returns:
            消息列表，按display_order升序排序
        """
        try:
            query = """
                SELECT id, trigger_id, message_content, is_active, display_order,
                       send_count, last_sent_at, created_at, updated_at
                FROM auto_reply_messages WHERE trigger_id = ?
            """
            params = [trigger_id]
            
            if active_only:
                query += " AND is_active = TRUE"
            
            query += " ORDER BY display_order ASC, created_at ASC"
            
            results = await db_manager.fetch_all(query, tuple(params))
            
            messages = [dict(row) for row in results]
            logger.debug(f"获取触发词消息成功，触发词ID: {trigger_id}, 数量: {len(messages)}")
            return messages
            
        except Exception as e:
            logger.error(f"获取触发词消息失败，触发词ID: {trigger_id}, 错误: {e}")
            return []
    
    @staticmethod
    async def update_message(
        message_id: int,
        message_content: Optional[str] = None,
        is_active: Optional[bool] = None,
        display_order: Optional[int] = None
    ) -> bool:
        """
        更新回复消息
        
        Args:
            message_id: 消息ID
            message_content: 新的消息内容（可选）
            is_active: 新的启用状态（可选）
            display_order: 新的显示顺序（可选）
            
        Returns:
            更新是否成功
        """
        try:
            update_fields = []
            params = []
            
            if message_content is not None:
                update_fields.append("message_content = ?")
                params.append(message_content)
            
            if is_active is not None:
                update_fields.append("is_active = ?")
                params.append(is_active)
            
            if display_order is not None:
                update_fields.append("display_order = ?")
                params.append(display_order)
            
            if not update_fields:
                logger.warning("没有提供要更新的字段")
                return False
            
            query = f"""
                UPDATE auto_reply_messages 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """
            params.append(message_id)
            
            affected_rows = await db_manager.execute_query(query, tuple(params))
            
            if affected_rows > 0:
                logger.info(f"回复消息更新成功，ID: {message_id}")
                return True
            else:
                logger.warning(f"回复消息不存在或无需更新，ID: {message_id}")
                return False
            
        except Exception as e:
            logger.error(f"更新回复消息失败，ID: {message_id}, 错误: {e}")
            return False
    
    @staticmethod
    async def delete_message(message_id: int) -> bool:
        """
        删除回复消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            删除是否成功
        """
        try:
            query = "DELETE FROM auto_reply_messages WHERE id = ?"
            affected_rows = await db_manager.execute_query(query, (message_id,))
            
            if affected_rows > 0:
                logger.info(f"回复消息删除成功，ID: {message_id}")
                return True
            else:
                logger.warning(f"回复消息不存在，ID: {message_id}")
                return False
            
        except Exception as e:
            logger.error(f"删除回复消息失败，ID: {message_id}, 错误: {e}")
            return False
    
    # ===== 匹配和触发功能 =====
    
    @staticmethod
    async def find_matching_triggers(user_message: str) -> List[Dict[str, Any]]:
        """
        根据用户消息查找匹配的触发词
        
        Args:
            user_message: 用户发送的消息内容
            
        Returns:
            匹配的触发词列表，按优先级排序
        """
        try:
            if not user_message or not user_message.strip():
                return []
            
            # 获取所有活跃的触发词
            triggers = await AutoReplyManager.get_all_active_triggers()
            matching_triggers = []
            
            # 进行匹配检查（不区分大小写）
            user_message_lower = user_message.lower().strip()
            
            for trigger in triggers:
                trigger_text = trigger['trigger_text'].lower().strip()
                match_type = trigger['match_type']
                
                is_match = False
                
                if match_type == 'exact':
                    # 完全匹配
                    is_match = (user_message_lower == trigger_text)
                elif match_type == 'contains':
                    # 包含匹配
                    is_match = (trigger_text in user_message_lower)
                
                if is_match:
                    matching_triggers.append(trigger)
            
            # 按优先级排序（priority_order越小优先级越高）
            matching_triggers.sort(key=lambda x: (x['priority_order'], x['created_at']))
            
            if matching_triggers:
                logger.debug(f"找到匹配触发词 {len(matching_triggers)} 个: {[t['trigger_text'] for t in matching_triggers]}")
            
            return matching_triggers
            
        except Exception as e:
            logger.error(f"查找匹配触发词失败: {e}")
            return []
    
    @staticmethod
    async def record_trigger_usage(trigger_id: int, user_id: int) -> bool:
        """
        记录触发词的使用情况
        
        Args:
            trigger_id: 触发词ID
            user_id: 用户ID
            
        Returns:
            记录是否成功
        """
        try:
            # 更新触发词统计
            update_query = """
                UPDATE auto_reply_triggers 
                SET trigger_count = trigger_count + 1,
                    last_triggered_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """
            
            affected_rows = await db_manager.execute_query(update_query, (trigger_id,))
            
            if affected_rows > 0:
                # 更新每日统计
                await AutoReplyManager._update_daily_stats(trigger_id, user_id)
                logger.debug(f"触发词使用记录成功，触发词ID: {trigger_id}, 用户ID: {user_id}")
                return True
            else:
                logger.warning(f"触发词不存在，ID: {trigger_id}")
                return False
            
        except Exception as e:
            logger.error(f"记录触发词使用失败: {e}")
            return False
    
    @staticmethod
    async def record_message_sent(message_id: int) -> bool:
        """
        记录消息发送情况
        
        Args:
            message_id: 消息ID
            
        Returns:
            记录是否成功
        """
        try:
            query = """
                UPDATE auto_reply_messages 
                SET send_count = send_count + 1,
                    last_sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """
            
            affected_rows = await db_manager.execute_query(query, (message_id,))
            
            if affected_rows > 0:
                logger.debug(f"消息发送记录成功，消息ID: {message_id}")
                return True
            else:
                logger.warning(f"消息不存在，ID: {message_id}")
                return False
            
        except Exception as e:
            logger.error(f"记录消息发送失败: {e}")
            return False
    
    # ===== 统计功能 =====
    
    @staticmethod
    async def get_trigger_statistics(
        trigger_id: Optional[int] = None,
        admin_id: Optional[int] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取触发词统计信息
        
        Args:
            trigger_id: 特定触发词ID（可选）
            admin_id: 管理员ID过滤（可选）
            days: 统计天数
            
        Returns:
            统计信息字典
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # 基础查询条件
            base_where = "WHERE 1=1"
            params = []
            
            if trigger_id:
                base_where += " AND t.id = ?"
                params.append(trigger_id)
            
            if admin_id:
                base_where += " AND t.created_by = ?"
                params.append(admin_id)
            
            # 总体统计
            total_query = f"""
                SELECT COUNT(*) as total_triggers,
                       SUM(t.trigger_count) as total_trigger_count,
                       COUNT(CASE WHEN t.is_active = 1 THEN 1 END) as active_triggers
                FROM auto_reply_triggers t {base_where}
            """
            
            total_result = await db_manager.fetch_one(total_query, tuple(params))
            
            # 最近活跃的触发词
            recent_query = f"""
                SELECT t.id, t.trigger_text, t.trigger_count, t.last_triggered_at
                FROM auto_reply_triggers t {base_where}
                ORDER BY t.last_triggered_at DESC NULLS LAST
                LIMIT 10
            """
            
            recent_results = await db_manager.fetch_all(recent_query, tuple(params))
            
            # 每日统计（最近30天）
            daily_stats_query = """
                SELECT s.stat_date, 
                       SUM(s.trigger_count) as daily_triggers,
                       SUM(s.unique_users_count) as daily_users,
                       SUM(s.total_messages_sent) as daily_messages
                FROM auto_reply_daily_stats s
                INNER JOIN auto_reply_triggers t ON s.trigger_id = t.id
                WHERE s.stat_date BETWEEN ? AND ?
            """
            daily_params = [start_date, end_date]
            
            if trigger_id:
                daily_stats_query += " AND t.id = ?"
                daily_params.append(trigger_id)
            if admin_id:
                daily_stats_query += " AND t.created_by = ?"
                daily_params.append(admin_id)
            
            daily_stats_query += " GROUP BY s.stat_date ORDER BY s.stat_date DESC"
            
            daily_results = await db_manager.fetch_all(daily_stats_query, tuple(daily_params))
            
            statistics = {
                'total_triggers': total_result['total_triggers'] if total_result else 0,
                'total_trigger_count': total_result['total_trigger_count'] if total_result else 0,
                'active_triggers': total_result['active_triggers'] if total_result else 0,
                'recent_triggers': [dict(row) for row in recent_results],
                'daily_stats': [dict(row) for row in daily_results],
                'date_range': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                }
            }
            
            logger.info(f"触发词统计信息生成成功")
            return statistics
            
        except Exception as e:
            logger.error(f"获取触发词统计失败: {e}")
            return {}
    
    # ===== 批量操作 =====
    
    @staticmethod
    async def bulk_update_trigger_status(trigger_ids: List[int], is_active: bool) -> int:
        """
        批量更新触发词状态
        
        Args:
            trigger_ids: 触发词ID列表
            is_active: 新的启用状态
            
        Returns:
            成功更新的数量
        """
        try:
            if not trigger_ids:
                return 0
            
            placeholders = ','.join(['?'] * len(trigger_ids))
            query = f"""
                UPDATE auto_reply_triggers 
                SET is_active = ?
                WHERE id IN ({placeholders})
            """
            
            params = [is_active] + trigger_ids
            affected_rows = await db_manager.execute_query(query, tuple(params))
            
            logger.info(f"批量更新触发词状态成功，影响行数: {affected_rows}")
            return affected_rows
            
        except Exception as e:
            logger.error(f"批量更新触发词状态失败: {e}")
            return 0
    
    @staticmethod
    async def bulk_update_message_status(message_ids: List[int], is_active: bool) -> int:
        """
        批量更新消息状态
        
        Args:
            message_ids: 消息ID列表
            is_active: 新的启用状态
            
        Returns:
            成功更新的数量
        """
        try:
            if not message_ids:
                return 0
            
            placeholders = ','.join(['?'] * len(message_ids))
            query = f"""
                UPDATE auto_reply_messages 
                SET is_active = ?
                WHERE id IN ({placeholders})
            """
            
            params = [is_active] + message_ids
            affected_rows = await db_manager.execute_query(query, tuple(params))
            
            logger.info(f"批量更新消息状态成功，影响行数: {affected_rows}")
            return affected_rows
            
        except Exception as e:
            logger.error(f"批量更新消息状态失败: {e}")
            return 0
    
    # ===== 内部辅助方法 =====
    
    @staticmethod
    async def _update_daily_stats(trigger_id: int, user_id: int) -> bool:
        """
        更新每日统计数据
        
        Args:
            trigger_id: 触发词ID
            user_id: 用户ID
            
        Returns:
            更新是否成功
        """
        try:
            today = date.today()
            
            # 检查今日统计是否存在
            check_query = """
                SELECT id FROM auto_reply_daily_stats 
                WHERE trigger_id = ? AND stat_date = ?
            """
            
            existing = await db_manager.fetch_one(check_query, (trigger_id, today))
            
            if existing:
                # 更新现有记录
                update_query = """
                    UPDATE auto_reply_daily_stats 
                    SET trigger_count = trigger_count + 1,
                        total_messages_sent = total_messages_sent + 1
                    WHERE id = ?
                """
                await db_manager.execute_query(update_query, (existing['id'],))
            else:
                # 创建新记录
                insert_query = """
                    INSERT INTO auto_reply_daily_stats 
                    (trigger_id, stat_date, trigger_count, unique_users_count, total_messages_sent)
                    VALUES (?, ?, 1, 1, 1)
                """
                await db_manager.execute_query(insert_query, (trigger_id, today))
            
            return True
            
        except Exception as e:
            logger.error(f"更新每日统计失败: {e}")
            return False

# 创建全局实例
auto_reply_manager = AutoReplyManager()