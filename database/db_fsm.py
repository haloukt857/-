"""
FSM状态数据库操作模块
处理用户状态的持久化存储和管理
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json

from .db_connection import DatabaseManager

# 设置日志记录器
logger = logging.getLogger(__name__)


class FSMDatabaseManager:
    """FSM状态数据库管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        初始化FSM数据库管理器
        
        Args:
            db_manager: 数据库连接管理器
        """
        self.db_manager = db_manager
    
    async def save_user_state(
        self, 
        user_id: int, 
        state: Optional[str], 
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        保存用户状态到数据库
        
        Args:
            user_id: 用户ID
            state: 状态名称
            data: 状态数据字典
            
        Returns:
            是否保存成功
        """
        try:
            # 将数据字典转换为JSON字符串
            data_json = json.dumps(data, ensure_ascii=False) if data else None
            
            query = """
                INSERT OR REPLACE INTO fsm_states (user_id, state, data, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            await self.db_manager.execute_query(query, (user_id, state, data_json))
            logger.debug(f"用户 {user_id} 状态已保存: {state}")
            return True
            
        except Exception as e:
            logger.error(f"保存用户 {user_id} 状态失败: {e}")
            return False
    
    async def load_user_state(self, user_id: int) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        从数据库加载用户状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            状态名称和状态数据的元组
        """
        try:
            query = """
                SELECT state, data, updated_at FROM fsm_states 
                WHERE user_id = ?
            """
            
            result = await self.db_manager.fetch_one(query, (user_id,))
            
            if not result:
                logger.debug(f"用户 {user_id} 没有保存的状态")
                return None, None
            
            state, data_json, updated_at = result
            
            # 解析JSON数据
            data = None
            if data_json:
                try:
                    data = json.loads(data_json)
                except json.JSONDecodeError as e:
                    logger.warning(f"用户 {user_id} 状态数据JSON解析失败: {e}")
                    data = {}
            
            logger.debug(f"用户 {user_id} 状态已加载: {state}")
            return state, data
            
        except Exception as e:
            logger.error(f"加载用户 {user_id} 状态失败: {e}")
            return None, None
    
    async def clear_user_state(self, user_id: int) -> bool:
        """
        清除用户状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否清除成功
        """
        try:
            query = "DELETE FROM fsm_states WHERE user_id = ?"
            await self.db_manager.execute_query(query, (user_id,))
            logger.debug(f"用户 {user_id} 状态已清除")
            return True
            
        except Exception as e:
            logger.error(f"清除用户 {user_id} 状态失败: {e}")
            return False
    
    async def update_state_data(
        self, 
        user_id: int, 
        data_updates: Dict[str, Any]
    ) -> bool:
        """
        更新用户状态数据
        
        Args:
            user_id: 用户ID
            data_updates: 要更新的数据字典
            
        Returns:
            是否更新成功
        """
        try:
            # 先获取现有数据
            current_state, current_data = await self.load_user_state(user_id)
            
            if current_state is None:
                logger.warning(f"用户 {user_id} 没有现有状态，无法更新数据")
                return False
            
            # 合并数据
            if current_data is None:
                current_data = {}
            
            current_data.update(data_updates)
            
            # 保存更新后的数据
            return await self.save_user_state(user_id, current_state, current_data)
            
        except Exception as e:
            logger.error(f"更新用户 {user_id} 状态数据失败: {e}")
            return False
    
    async def get_state_data_value(
        self, 
        user_id: int, 
        key: str, 
        default: Any = None
    ) -> Any:
        """
        获取状态数据中的特定值
        
        Args:
            user_id: 用户ID
            key: 数据键
            default: 默认值
            
        Returns:
            数据值或默认值
        """
        try:
            _, data = await self.load_user_state(user_id)
            
            if data is None:
                return default
            
            return data.get(key, default)
            
        except Exception as e:
            logger.error(f"获取用户 {user_id} 状态数据值失败: {e}")
            return default
    
    async def set_state_data_value(
        self, 
        user_id: int, 
        key: str, 
        value: Any
    ) -> bool:
        """
        设置状态数据中的特定值
        
        Args:
            user_id: 用户ID
            key: 数据键
            value: 数据值
            
        Returns:
            是否设置成功
        """
        return await self.update_state_data(user_id, {key: value})
    
    async def remove_state_data_value(self, user_id: int, key: str) -> bool:
        """
        移除状态数据中的特定值
        
        Args:
            user_id: 用户ID
            key: 数据键
            
        Returns:
            是否移除成功
        """
        try:
            current_state, current_data = await self.load_user_state(user_id)
            
            if current_state is None or current_data is None:
                return True  # 没有数据，认为移除成功
            
            if key in current_data:
                del current_data[key]
                return await self.save_user_state(user_id, current_state, current_data)
            
            return True  # 键不存在，认为移除成功
            
        except Exception as e:
            logger.error(f"移除用户 {user_id} 状态数据值失败: {e}")
            return False
    
    async def get_users_in_state(self, state: str) -> List[int]:
        """
        获取处于特定状态的所有用户ID
        
        Args:
            state: 状态名称
            
        Returns:
            用户ID列表
        """
        try:
            query = "SELECT user_id FROM fsm_states WHERE state = ?"
            results = await self.db_manager.fetch_all(query, (state,))
            
            user_ids = [row[0] for row in results]
            logger.debug(f"找到 {len(user_ids)} 个用户处于状态 {state}")
            return user_ids
            
        except Exception as e:
            logger.error(f"获取状态 {state} 的用户列表失败: {e}")
            return []
    
    async def get_all_active_states(self) -> List[Dict[str, Any]]:
        """
        获取所有活跃状态的信息
        
        Returns:
            状态信息列表
        """
        try:
            query = """
                SELECT user_id, state, updated_at 
                FROM fsm_states 
                ORDER BY updated_at DESC
            """
            
            results = await self.db_manager.fetch_all(query)
            
            states = []
            for row in results:
                user_id, state, updated_at = row
                states.append({
                    'user_id': user_id,
                    'state': state,
                    'updated_at': updated_at
                })
            
            logger.debug(f"获取到 {len(states)} 个活跃状态")
            return states
            
        except Exception as e:
            logger.error(f"获取活跃状态列表失败: {e}")
            return []
    
    async def cleanup_expired_states(self, timeout_hours: int = 24) -> int:
        """
        清理过期的状态
        
        Args:
            timeout_hours: 超时时间（小时）
            
        Returns:
            清理的状态数量
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=timeout_hours)
            
            # 先查询要删除的记录数
            count_query = """
                SELECT COUNT(*) FROM fsm_states 
                WHERE updated_at < ?
            """
            
            count_result = await self.db_manager.fetch_one(
                count_query, 
                (cutoff_time.isoformat(),)
            )
            
            count = count_result[0] if count_result else 0
            
            if count > 0:
                # 执行删除
                delete_query = """
                    DELETE FROM fsm_states 
                    WHERE updated_at < ?
                """
                
                await self.db_manager.execute_query(
                    delete_query, 
                    (cutoff_time.isoformat(),)
                )
                
                logger.info(f"已清理 {count} 个过期状态（超过 {timeout_hours} 小时）")
            else:
                logger.debug("没有找到过期的状态需要清理")
            
            return count
            
        except Exception as e:
            logger.error(f"清理过期状态失败: {e}")
            return 0
    
    async def get_state_statistics(self) -> Dict[str, Any]:
        """
        获取状态统计信息
        
        Returns:
            统计信息字典
        """
        try:
            # 总状态数
            total_query = "SELECT COUNT(*) FROM fsm_states"
            total_result = await self.db_manager.fetch_one(total_query)
            total_states = total_result[0] if total_result else 0
            
            # 按状态分组统计
            state_query = """
                SELECT state, COUNT(*) as count 
                FROM fsm_states 
                GROUP BY state 
                ORDER BY count DESC
            """
            
            state_results = await self.db_manager.fetch_all(state_query)
            state_counts = {row[0]: row[1] for row in state_results}
            
            # 最近活跃时间
            recent_query = """
                SELECT MAX(updated_at) FROM fsm_states
            """
            
            recent_result = await self.db_manager.fetch_one(recent_query)
            last_activity = recent_result[0] if recent_result and recent_result[0] else None
            
            statistics = {
                'total_states': total_states,
                'state_counts': state_counts,
                'last_activity': last_activity
            }
            
            logger.debug(f"状态统计: {statistics}")
            return statistics
            
        except Exception as e:
            logger.error(f"获取状态统计失败: {e}")
            return {
                'total_states': 0,
                'state_counts': {},
                'last_activity': None
            }
    
    async def backup_states(self) -> List[Dict[str, Any]]:
        """
        备份所有状态数据
        
        Returns:
            状态数据列表
        """
        try:
            query = """
                SELECT user_id, state, data, updated_at 
                FROM fsm_states 
                ORDER BY user_id
            """
            
            results = await self.db_manager.fetch_all(query)
            
            backup_data = []
            for row in results:
                user_id, state, data_json, updated_at = row
                
                # 解析JSON数据
                data = None
                if data_json:
                    try:
                        data = json.loads(data_json)
                    except json.JSONDecodeError:
                        data = {}
                
                backup_data.append({
                    'user_id': user_id,
                    'state': state,
                    'data': data,
                    'updated_at': updated_at
                })
            
            logger.info(f"已备份 {len(backup_data)} 个状态")
            return backup_data
            
        except Exception as e:
            logger.error(f"备份状态数据失败: {e}")
            return []
    
    async def restore_states(self, backup_data: List[Dict[str, Any]]) -> int:
        """
        从备份恢复状态数据
        
        Args:
            backup_data: 备份的状态数据列表
            
        Returns:
            恢复的状态数量
        """
        restored_count = 0
        
        try:
            for state_data in backup_data:
                user_id = state_data.get('user_id')
                state = state_data.get('state')
                data = state_data.get('data')
                
                if user_id and state:
                    success = await self.save_user_state(user_id, state, data)
                    if success:
                        restored_count += 1
            
            logger.info(f"已恢复 {restored_count} 个状态")
            return restored_count
            
        except Exception as e:
            logger.error(f"恢复状态数据失败: {e}")
            return restored_count


# 创建全局FSM数据库管理器实例的工厂函数
def create_fsm_db_manager(db_manager: DatabaseManager) -> FSMDatabaseManager:
    """
    创建FSM数据库管理器实例
    
    Args:
        db_manager: 数据库连接管理器
        
    Returns:
        FSM数据库管理器实例
    """
    return FSMDatabaseManager(db_manager)