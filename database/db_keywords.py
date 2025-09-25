"""
关键词管理数据库操作类
提供关键词的增删改查功能，支持动态关键词管理和多选功能

重构要点:
- 强制使用db_connection.py中的DatabaseManager连接池
- 所有方法强制async/await模式
- 与当前架构完全适配
- 保持功能完全对等
"""

import logging
from typing import List, Dict, Any, Optional
from database.db_connection import db_manager

logger = logging.getLogger(__name__)


class KeywordManager:
    """关键词数据库管理类"""

    @staticmethod
    async def create_keyword(name: str, display_order: int = 0) -> int:
        """
        创建新关键词
        
        Args:
            name: 关键词名称（通常2字）
            display_order: 显示顺序
            
        Returns:
            int: 新创建关键词的ID
            
        Raises:
            ValueError: 如果关键词名称已存在或输入无效
        """
        try:
            # 验证关键词长度（推荐2个字符）
            if len(name.strip()) == 0:
                raise ValueError("关键词不能为空")
            
            if len(name.strip()) > 6:
                raise ValueError("关键词长度不应超过6个字符")
            
            # 检查关键词是否已存在
            existing_query = "SELECT id FROM keywords WHERE name = ?"
            existing = await db_manager.fetch_one(existing_query, (name.strip(),))
            if existing:
                raise ValueError(f"关键词 '{name}' 已存在")
            
            # 插入新关键词
            insert_query = """
                INSERT INTO keywords (name, display_order) VALUES (?, ?)
            """
            keyword_id = await db_manager.get_last_insert_id(
                insert_query, (name.strip(), display_order)
            )
            
            logger.info(f"关键词创建成功: {name} (ID: {keyword_id})")
            return keyword_id
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"创建关键词失败: {e}")
            raise

    @staticmethod
    async def get_all_keywords(order_by: str = 'display_order') -> List[Dict[str, Any]]:
        """
        获取所有关键词
        
        Args:
            order_by: 排序字段 ('display_order', 'name', 'created_at')
            
        Returns:
            List[Dict]: 关键词列表
        """
        try:
            # 验证排序字段安全性
            valid_orders = ['display_order', 'name', 'created_at', 'id']
            if order_by not in valid_orders:
                order_by = 'display_order'
            
            query = f"""
                SELECT k.*, 
                       COALESCE(mk_count.usage_count, 0) as usage_count,
                       '未分类' as category,
                       '' as description,
                       k.is_active
                FROM keywords k
                LEFT JOIN (
                    SELECT keyword_id, COUNT(*) as usage_count 
                    FROM merchant_keywords 
                    GROUP BY keyword_id
                ) mk_count ON k.id = mk_count.keyword_id
                ORDER BY {order_by} ASC, k.name ASC
            """
            
            results = await db_manager.fetch_all(query)
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"获取关键词列表失败: {e}")
            raise

    @staticmethod
    async def get_keyword_by_id(keyword_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取关键词
        
        Args:
            keyword_id: 关键词ID
            
        Returns:
            Dict: 关键词信息，不存在则返回None
        """
        try:
            query = """
                SELECT k.*, 
                       COALESCE(mk_count.usage_count, 0) as usage_count,
                       '未分类' as category,
                       '' as description
                FROM keywords k
                LEFT JOIN (
                    SELECT keyword_id, COUNT(*) as usage_count 
                    FROM merchant_keywords 
                    GROUP BY keyword_id
                ) mk_count ON k.id = mk_count.keyword_id
                WHERE k.id = ?
            """
            result = await db_manager.fetch_one(query, (keyword_id,))
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"根据ID获取关键词失败: {e}")
            raise

    @staticmethod
    async def get_keyword_by_name(name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取关键词
        
        Args:
            name: 关键词名称
            
        Returns:
            Dict: 关键词信息，不存在则返回None
        """
        try:
            query = """
                SELECT k.*, 
                       COALESCE(mk_count.usage_count, 0) as usage_count,
                       '未分类' as category,
                       '' as description
                FROM keywords k
                LEFT JOIN (
                    SELECT keyword_id, COUNT(*) as usage_count 
                    FROM merchant_keywords 
                    GROUP BY keyword_id
                ) mk_count ON k.id = mk_count.keyword_id
                WHERE k.name = ?
            """
            result = await db_manager.fetch_one(query, (name.strip(),))
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"根据名称获取关键词失败: {e}")
            raise

    @staticmethod
    async def update_keyword(keyword_id: int, name: str = None, display_order: int = None) -> bool:
        """
        更新关键词信息
        
        Args:
            keyword_id: 关键词ID
            name: 新的关键词名称（可选）
            display_order: 新的显示顺序（可选）
            
        Returns:
            bool: 更新成功返回True，失败返回False
        """
        try:
            # 检查关键词是否存在
            existing = await KeywordManager.get_keyword_by_id(keyword_id)
            if not existing:
                logger.warning(f"关键词ID {keyword_id} 不存在")
                return False
            
            # 准备更新字段
            updates = []
            params = []
            
            if name is not None:
                name = name.strip()
                if len(name) == 0:
                    raise ValueError("关键词不能为空")
                if len(name) > 6:
                    raise ValueError("关键词长度不应超过6个字符")
                
                # 检查新名称是否与其他关键词冲突
                conflict_query = "SELECT id FROM keywords WHERE name = ? AND id != ?"
                conflict = await db_manager.fetch_one(conflict_query, (name, keyword_id))
                if conflict:
                    raise ValueError(f"关键词 '{name}' 已存在")
                
                updates.append("name = ?")
                params.append(name)
            
            if display_order is not None:
                updates.append("display_order = ?")
                params.append(display_order)
            
            if not updates:
                logger.warning("没有提供任何更新字段")
                return False
            
            # 添加更新时间
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(keyword_id)
            
            # 执行更新
            query = f"UPDATE keywords SET {', '.join(updates)} WHERE id = ?"
            result = await db_manager.execute_query(query, tuple(params))
            
            if result > 0:
                logger.info(f"关键词更新成功 (ID: {keyword_id})")
                return True
            else:
                logger.warning(f"关键词更新失败，可能不存在 (ID: {keyword_id})")
                return False
                
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"更新关键词失败: {e}")
            raise

    @staticmethod
    async def delete_keyword(keyword_id: int) -> bool:
        """
        删除关键词
        
        Args:
            keyword_id: 关键词ID
            
        Returns:
            bool: 删除成功返回True，失败返回False
        """
        try:
            # 检查关键词是否存在
            existing = await KeywordManager.get_keyword_by_id(keyword_id)
            if not existing:
                logger.warning(f"关键词ID {keyword_id} 不存在")
                return False
            
            # 执行删除
            query = "DELETE FROM keywords WHERE id = ?"
            result = await db_manager.execute_query(query, (keyword_id,))
            
            if result > 0:
                logger.info(f"关键词删除成功: {existing['name']} (ID: {keyword_id})")
                return True
            else:
                logger.warning(f"关键词删除失败 (ID: {keyword_id})")
                return False
                
        except Exception as e:
            logger.error(f"删除关键词失败: {e}")
            raise

    @staticmethod
    async def search_keywords(search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜索关键词
        
        Args:
            search_term: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            List[Dict]: 匹配的关键词列表
        """
        try:
            if not search_term.strip():
                return []
            
            query = """
                SELECT * FROM keywords 
                WHERE name LIKE ? 
                ORDER BY display_order ASC, name ASC
                LIMIT ?
            """
            
            search_pattern = f"%{search_term.strip()}%"
            results = await db_manager.fetch_all(query, (search_pattern, limit))
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"搜索关键词失败: {e}")
            raise

    @staticmethod
    async def get_keyword_statistics() -> Dict[str, Any]:
        """
        获取关键词统计信息
        
        Returns:
            Dict: 包含总数、最新创建等统计信息
        """
        try:
            stats = {}
            
            # 总关键词数
            count_query = "SELECT COUNT(*) as total FROM keywords"
            count_result = await db_manager.fetch_one(count_query)
            stats['total_keywords'] = count_result['total'] if count_result else 0
            
            # 获取最新创建的关键词
            recent_query = """
                SELECT name, created_at FROM keywords 
                ORDER BY created_at DESC 
                LIMIT 5
            """
            recent_results = await db_manager.fetch_all(recent_query)
            stats['recent_keywords'] = [dict(row) for row in recent_results]
            
            return stats
            
        except Exception as e:
            logger.error(f"获取关键词统计失败: {e}")
            raise

    @staticmethod
    async def get_keywords_with_usage_count() -> List[Dict[str, Any]]:
        """
        获取关键词及其使用频次（如果有相关表的话）
        
        Returns:
            List[Dict]: 关键词列表，包含使用统计
        """
        try:
            # 基础关键词查询
            query = """
                SELECT k.*, 
                       COALESCE(mk_count.usage_count, 0) as usage_count,
                       '未分类' as category,
                       '' as description
                FROM keywords k
                LEFT JOIN (
                    SELECT keyword_id, COUNT(*) as usage_count 
                    FROM merchant_keywords 
                    GROUP BY keyword_id
                ) mk_count ON k.id = mk_count.keyword_id
                ORDER BY k.display_order ASC, k.name ASC
            """
            
            results = await db_manager.fetch_all(query)
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"获取关键词使用统计失败: {e}")
            raise

    @staticmethod
    async def bulk_update_display_order(keyword_orders: List[Dict[str, Any]]) -> bool:
        """
        批量更新关键词显示顺序
        
        Args:
            keyword_orders: 关键词ID和显示顺序的列表
                格式: [{'id': 1, 'display_order': 10}, ...]
            
        Returns:
            bool: 更新是否成功
        """
        try:
            if not keyword_orders:
                return True
            
            # 准备批量更新
            for item in keyword_orders:
                if not isinstance(item, dict) or 'id' not in item or 'display_order' not in item:
                    raise ValueError("无效的关键词顺序数据格式")
                
                query = "UPDATE keywords SET display_order = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                await db_manager.execute_query(query, (item['display_order'], item['id']))
            
            logger.info(f"批量更新关键词显示顺序成功，数量: {len(keyword_orders)}")
            return True
            
        except Exception as e:
            logger.error(f"批量更新关键词显示顺序失败: {e}")
            raise


# 实例化管理器（保持兼容性）
keyword_manager = KeywordManager()

# V1兼容性便捷函数
async def create_keyword(name: str, display_order: int = 0) -> int:
    """创建关键词的便捷函数"""
    return await KeywordManager.create_keyword(name, display_order)

async def get_all_keywords(order_by: str = 'display_order') -> List[Dict[str, Any]]:
    """获取所有关键词的便捷函数"""
    return await KeywordManager.get_all_keywords(order_by)

async def get_keyword_by_id(keyword_id: int) -> Optional[Dict[str, Any]]:
    """根据ID获取关键词的便捷函数"""
    return await KeywordManager.get_keyword_by_id(keyword_id)

async def update_keyword(keyword_id: int, name: str = None, display_order: int = None) -> bool:
    """更新关键词的便捷函数"""
    return await KeywordManager.update_keyword(keyword_id, name, display_order)

async def delete_keyword(keyword_id: int) -> bool:
    """删除关键词的便捷函数"""
    return await KeywordManager.delete_keyword(keyword_id)

async def search_keywords(search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
    """搜索关键词的便捷函数"""
    return await KeywordManager.search_keywords(search_term, limit)

async def get_keyword_statistics() -> Dict[str, Any]:
    """获取关键词统计的便捷函数"""
    return await KeywordManager.get_keyword_statistics()


# 扩展方法：补充admin_keyword_management.py需要的方法
class KeywordManagerExtended(KeywordManager):
    """扩展关键词管理器，补充管理界面需要的方法"""
    
    @staticmethod
    async def count_keywords(only_active: bool = False) -> int:
        """
        获取关键词总数
        
        Args:
            only_active: 是否只统计激活的关键词
            
        Returns:
            int: 关键词数量
        """
        try:
            if only_active:
                query = "SELECT COUNT(*) as total FROM keywords WHERE is_active = 1"
            else:
                query = "SELECT COUNT(*) as total FROM keywords"
            
            result = await db_manager.fetch_one(query)
            return result['total'] if result else 0
            
        except Exception as e:
            logger.error(f"统计关键词数量失败: {e}")
            raise
    
    @staticmethod
    async def get_all_keywords(limit: Optional[int] = None, offset: int = 0, order_by: str = 'display_order') -> List[Dict[str, Any]]:
        """
        获取所有关键词（支持分页）
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            order_by: 排序字段
            
        Returns:
            List[Dict]: 关键词列表
        """
        try:
            # 验证排序字段安全性
            valid_orders = ['display_order', 'name', 'created_at', 'id']
            if order_by not in valid_orders:
                order_by = 'display_order'
            
            query = f"""
                SELECT k.*, 
                       COALESCE(mk_count.usage_count, 0) as usage_count,
                       '未分类' as category,
                       '' as description,
                       k.is_active
                FROM keywords k
                LEFT JOIN (
                    SELECT keyword_id, COUNT(*) as usage_count 
                    FROM merchant_keywords 
                    GROUP BY keyword_id
                ) mk_count ON k.id = mk_count.keyword_id
                ORDER BY {order_by} ASC, k.name ASC
            """
            
            if limit:
                query += f" LIMIT {limit}"
                if offset > 0:
                    query += f" OFFSET {offset}"
            
            results = await db_manager.fetch_all(query)
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"获取关键词列表失败: {e}")
            raise
    
    @staticmethod
    async def update_keyword_status(keyword_id: int, is_active: bool) -> bool:
        """
        更新关键词状态
        
        Args:
            keyword_id: 关键词ID
            is_active: 是否激活
            
        Returns:
            bool: 更新是否成功
        """
        try:
            query = "UPDATE keywords SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            result = await db_manager.execute_query(query, (is_active, keyword_id))
            
            if result > 0:
                logger.info(f"关键词状态更新成功 (ID: {keyword_id}, 状态: {is_active})")
                return True
            else:
                logger.warning(f"关键词状态更新失败，可能不存在 (ID: {keyword_id})")
                return False
                
        except Exception as e:
            logger.error(f"更新关键词状态失败: {e}")
            raise
    
    @staticmethod
    async def get_keyword_categories() -> Dict[str, int]:
        """
        获取关键词分类统计
        
        Returns:
            Dict[str, int]: 分类名称和对应的关键词数量
        """
        try:
            # 由于当前表结构没有category字段，返回默认分类
            total_count = await KeywordManagerExtended.count_keywords()
            return {"未分类": total_count} if total_count > 0 else {}
            
        except Exception as e:
            logger.error(f"获取关键词分类失败: {e}")
            raise
    
    @staticmethod
    async def get_popular_keywords(limit: int = 5) -> List[Dict[str, Any]]:
        """
        获取最受欢迎的关键词
        
        Args:
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 按使用次数排序的关键词列表
        """
        try:
            query = """
                SELECT k.*, 
                       COALESCE(mk_count.usage_count, 0) as usage_count
                FROM keywords k
                LEFT JOIN (
                    SELECT keyword_id, COUNT(*) as usage_count 
                    FROM merchant_keywords 
                    GROUP BY keyword_id
                ) mk_count ON k.id = mk_count.keyword_id
                WHERE k.is_active = 1
                ORDER BY mk_count.usage_count DESC, k.name ASC
                LIMIT ?
            """
            
            results = await db_manager.fetch_all(query, (limit,))
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"获取热门关键词失败: {e}")
            raise


# 创建扩展实例，替换原有的keyword_manager
keyword_manager = KeywordManagerExtended()