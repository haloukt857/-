# -*- coding: utf-8 -*-
"""
激励系统数据库管理器

负责与 `user_levels`, `badges`, `badge_triggers` 表相关的所有数据库操作。
"""

import logging
from typing import List, Dict, Any, Optional

# 导入项目模块
# 激励系统数据库管理模块

from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class IncentiveManager:
    """
    激励系统数据库管理器
    提供完整的CRUD操作支持Web后台管理
    """

    # ==================== 等级管理 (user_levels表) ==================== #

    @staticmethod
    async def get_all_levels() -> List[Dict[str, Any]]:
        """
        获取所有等级配置，按经验值升序排列
        
        Returns:
            等级列表，每个等级包含id, level_name, xp_required
        """
        try:
            query = "SELECT * FROM user_levels ORDER BY xp_required ASC"
            results = await db_manager.fetch_all(query)
            levels = [dict(row) for row in results]
            logger.debug(f"获取等级列表成功，共{len(levels)}个等级")
            return levels
        except Exception as e:
            logger.error(f"获取等级列表失败: {e}")
            raise

    @staticmethod
    async def add_level(level_name: str, xp_required: int) -> Optional[int]:
        """
        添加新等级
        
        Args:
            level_name: 等级名称（如"大师"）
            xp_required: 升级所需经验值
            
        Returns:
            新创建等级的ID或None（失败时）
            
        Raises:
            ValueError: 等级名称或经验值无效时
            Exception: 数据库操作失败时
        """
        try:
            # 输入验证
            if not level_name or not level_name.strip():
                raise ValueError("等级名称不能为空")
            if xp_required < 0:
                raise ValueError("经验值不能为负数")
            
            # 检查等级名称是否已存在
            existing_query = "SELECT id FROM user_levels WHERE level_name = ?"
            existing = await db_manager.fetch_one(existing_query, (level_name.strip(),))
            if existing:
                raise ValueError(f"等级名称 '{level_name}' 已存在")
            
            # 检查经验值是否已存在
            xp_existing_query = "SELECT id FROM user_levels WHERE xp_required = ?"
            xp_existing = await db_manager.fetch_one(xp_existing_query, (xp_required,))
            if xp_existing:
                raise ValueError(f"经验值 {xp_required} 已被其他等级使用")
            
            # 插入新等级
            query = "INSERT INTO user_levels (level_name, xp_required) VALUES (?, ?)"
            level_id = await db_manager.get_last_insert_id(query, (level_name.strip(), xp_required))
            
            logger.info(f"等级创建成功: {level_name}, 经验值: {xp_required}, ID: {level_id}")
            return level_id
            
        except ValueError as e:
            logger.error(f"等级创建验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"等级创建失败: {e}")
            raise

    @staticmethod
    async def update_level(level_id: int, new_name: str, new_xp: int) -> bool:
        """
        更新现有等级信息
        
        Args:
            level_id: 等级ID
            new_name: 新等级名称
            new_xp: 新经验值要求
            
        Returns:
            更新是否成功
            
        Raises:
            ValueError: 输入参数无效时
            Exception: 数据库操作失败时
        """
        try:
            # 输入验证
            if not new_name or not new_name.strip():
                raise ValueError("等级名称不能为空")
            if new_xp < 0:
                raise ValueError("经验值不能为负数")
            
            # 检查等级是否存在
            existing_query = "SELECT id FROM user_levels WHERE id = ?"
            existing = await db_manager.fetch_one(existing_query, (level_id,))
            if not existing:
                raise ValueError(f"等级ID {level_id} 不存在")
            
            # 检查新名称是否与其他等级冲突
            name_conflict_query = "SELECT id FROM user_levels WHERE level_name = ? AND id != ?"
            name_conflict = await db_manager.fetch_one(name_conflict_query, (new_name.strip(), level_id))
            if name_conflict:
                raise ValueError(f"等级名称 '{new_name}' 已被其他等级使用")
            
            # 检查新经验值是否与其他等级冲突
            xp_conflict_query = "SELECT id FROM user_levels WHERE xp_required = ? AND id != ?"
            xp_conflict = await db_manager.fetch_one(xp_conflict_query, (new_xp, level_id))
            if xp_conflict:
                raise ValueError(f"经验值 {new_xp} 已被其他等级使用")
            
            # 执行更新
            update_query = "UPDATE user_levels SET level_name = ?, xp_required = ? WHERE id = ?"
            result = await db_manager.execute_query(update_query, (new_name.strip(), new_xp, level_id))
            
            if result > 0:
                logger.info(f"等级更新成功: ID {level_id}, 新名称: {new_name}, 新经验值: {new_xp}")
                return True
            else:
                logger.warning(f"等级更新失败: ID {level_id}")
                return False
                
        except ValueError as e:
            logger.error(f"等级更新验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"等级更新失败: {e}")
            raise

    @staticmethod
    async def delete_level(level_id: int) -> bool:
        """
        删除等级
        
        Args:
            level_id: 等级ID
            
        Returns:
            删除是否成功
            
        Raises:
            ValueError: 等级ID无效时
            Exception: 数据库操作失败时
        """
        try:
            # 检查等级是否存在
            existing_query = "SELECT level_name FROM user_levels WHERE id = ?"
            existing = await db_manager.fetch_one(existing_query, (level_id,))
            if not existing:
                raise ValueError(f"等级ID {level_id} 不存在")
            
            # 执行删除
            delete_query = "DELETE FROM user_levels WHERE id = ?"
            result = await db_manager.execute_query(delete_query, (level_id,))
            
            if result > 0:
                logger.info(f"等级删除成功: ID {level_id}, 名称: {existing['level_name']}")
                return True
            else:
                logger.warning(f"等级删除失败: ID {level_id}")
                return False
                
        except ValueError as e:
            logger.error(f"等级删除验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"等级删除失败: {e}")
            raise

    # ==================== 勋章管理 (badges表) ==================== #

    @staticmethod
    async def get_all_badges() -> List[Dict[str, Any]]:
        """
        获取所有勋章配置
        
        Returns:
            勋章列表，每个勋章包含id, badge_name, badge_icon, description
        """
        try:
            query = "SELECT * FROM badges ORDER BY id ASC"
            results = await db_manager.fetch_all(query)
            badges = [dict(row) for row in results]
            logger.debug(f"获取勋章列表成功，共{len(badges)}个勋章")
            return badges
        except Exception as e:
            logger.error(f"获取勋章列表失败: {e}")
            raise

    @staticmethod
    async def add_badge(badge_name: str, badge_icon: str, description: str) -> Optional[int]:
        """
        添加新勋章
        
        Args:
            badge_name: 勋章名称（如"十连胜"）
            badge_icon: 勋章图标（emoji或URL）
            description: 勋章描述
            
        Returns:
            新创建勋章的ID或None（失败时）
            
        Raises:
            ValueError: 勋章名称无效时
            Exception: 数据库操作失败时
        """
        try:
            # 输入验证
            if not badge_name or not badge_name.strip():
                raise ValueError("勋章名称不能为空")
            
            # 检查勋章名称是否已存在
            existing_query = "SELECT id FROM badges WHERE badge_name = ?"
            existing = await db_manager.fetch_one(existing_query, (badge_name.strip(),))
            if existing:
                raise ValueError(f"勋章名称 '{badge_name}' 已存在")
            
            # 插入新勋章
            query = "INSERT INTO badges (badge_name, badge_icon, description) VALUES (?, ?, ?)"
            badge_id = await db_manager.get_last_insert_id(
                query, 
                (badge_name.strip(), badge_icon or "", description or "")
            )
            
            logger.info(f"勋章创建成功: {badge_name}, 图标: {badge_icon}, ID: {badge_id}")
            return badge_id
            
        except ValueError as e:
            logger.error(f"勋章创建验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"勋章创建失败: {e}")
            raise

    @staticmethod
    async def update_badge(badge_id: int, badge_name: str = None, badge_icon: str = None, description: str = None) -> bool:
        """
        更新现有勋章信息
        
        Args:
            badge_id: 勋章ID
            badge_name: 新勋章名称（可选）
            badge_icon: 新勋章图标（可选）
            description: 新勋章描述（可选）
            
        Returns:
            更新是否成功
            
        Raises:
            ValueError: 输入参数无效时
            Exception: 数据库操作失败时
        """
        try:
            # 检查勋章是否存在
            existing_query = "SELECT * FROM badges WHERE id = ?"
            existing = await db_manager.fetch_one(existing_query, (badge_id,))
            if not existing:
                raise ValueError(f"勋章ID {badge_id} 不存在")
            
            # 构建更新字段
            update_fields = []
            update_params = []
            
            if badge_name is not None:
                if not badge_name.strip():
                    raise ValueError("勋章名称不能为空")
                # 检查名称是否与其他勋章冲突
                name_conflict_query = "SELECT id FROM badges WHERE badge_name = ? AND id != ?"
                name_conflict = await db_manager.fetch_one(name_conflict_query, (badge_name.strip(), badge_id))
                if name_conflict:
                    raise ValueError(f"勋章名称 '{badge_name}' 已被其他勋章使用")
                update_fields.append("badge_name = ?")
                update_params.append(badge_name.strip())
            
            if badge_icon is not None:
                update_fields.append("badge_icon = ?")
                update_params.append(badge_icon)
                
            if description is not None:
                update_fields.append("description = ?")
                update_params.append(description)
            
            # 如果没有要更新的字段
            if not update_fields:
                logger.warning(f"勋章更新请求没有提供任何更新字段: ID {badge_id}")
                return True
            
            # 执行更新
            update_query = f"UPDATE badges SET {', '.join(update_fields)} WHERE id = ?"
            update_params.append(badge_id)
            result = await db_manager.execute_query(update_query, tuple(update_params))
            
            if result > 0:
                logger.info(f"勋章更新成功: ID {badge_id}")
                return True
            else:
                logger.warning(f"勋章更新失败: ID {badge_id}")
                return False
                
        except ValueError as e:
            logger.error(f"勋章更新验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"勋章更新失败: {e}")
            raise

    @staticmethod
    async def delete_badge(badge_id: int) -> bool:
        """
        删除勋章（级联删除相关触发器）
        
        Args:
            badge_id: 勋章ID
            
        Returns:
            删除是否成功
            
        Raises:
            ValueError: 勋章ID无效时
            Exception: 数据库操作失败时
        """
        try:
            # 检查勋章是否存在
            existing_query = "SELECT badge_name FROM badges WHERE id = ?"
            existing = await db_manager.fetch_one(existing_query, (badge_id,))
            if not existing:
                raise ValueError(f"勋章ID {badge_id} 不存在")
            
            # 删除勋章（触发器会因外键约束自动级联删除）
            delete_query = "DELETE FROM badges WHERE id = ?"
            result = await db_manager.execute_query(delete_query, (badge_id,))
            
            if result > 0:
                logger.info(f"勋章删除成功: ID {badge_id}, 名称: {existing['badge_name']}")
                return True
            else:
                logger.warning(f"勋章删除失败: ID {badge_id}")
                return False
                
        except ValueError as e:
            logger.error(f"勋章删除验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"勋章删除失败: {e}")
            raise

    @staticmethod
    async def get_all_badges_with_triggers() -> List[Dict[str, Any]]:
        """
        获取所有勋章及其关联的触发条件
        
        Returns:
            勋章列表，每个勋章包含triggers数组
        """
        try:
            # 获取所有勋章
            badges = await IncentiveManager.get_all_badges()
            
            # 为每个勋章获取触发器
            for badge in badges:
                triggers = await IncentiveManager.get_triggers_for_badge(badge['id'])
                badge['triggers'] = triggers
            
            logger.debug(f"获取勋章及触发器列表成功，共{len(badges)}个勋章")
            return badges
            
        except Exception as e:
            logger.error(f"获取勋章及触发器列表失败: {e}")
            raise

    # ==================== 触发器管理 (badge_triggers表) ==================== #

    @staticmethod
    async def get_triggers_for_badge(badge_id: int) -> List[Dict[str, Any]]:
        """
        获取指定勋章的所有触发条件
        
        Args:
            badge_id: 勋章ID
            
        Returns:
            触发器列表
        """
        try:
            query = "SELECT * FROM badge_triggers WHERE badge_id = ? ORDER BY trigger_type, trigger_value"
            results = await db_manager.fetch_all(query, (badge_id,))
            triggers = [dict(row) for row in results]
            logger.debug(f"获取勋章{badge_id}的触发器成功，共{len(triggers)}个触发器")
            return triggers
        except Exception as e:
            logger.error(f"获取勋章{badge_id}的触发器失败: {e}")
            raise

    # ==================== 统计方法（供Web服务调用） ==================== #

    @staticmethod
    async def count_users_with_any_badge() -> int:
        """统计拥有任意勋章的用户数（基于user_badges表）"""
        try:
            query = "SELECT COUNT(DISTINCT user_id) as count FROM user_badges"
            result = await db_manager.fetch_one(query)
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"统计拥有任意勋章的用户数失败: {e}")
            return 0

    @staticmethod
    async def count_users_with_badge(badge_id: int) -> int:
        """统计拥有指定勋章的用户数（基于user_badges表）"""
        try:
            query = "SELECT COUNT(DISTINCT user_id) as count FROM user_badges WHERE badge_id = ?"
            result = await db_manager.fetch_one(query, (badge_id,))
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"统计拥有指定勋章的用户数失败: {e}")
            return 0

    @staticmethod
    async def add_trigger(badge_id: int, trigger_type: str, trigger_value: int) -> Optional[int]:
        """
        为勋章添加触发条件
        
        Args:
            badge_id: 勋章ID
            trigger_type: 触发类型（如order_count, perfect_reviews, total_points）
            trigger_value: 触发值
            
        Returns:
            新创建触发器的ID或None（失败时）
            
        Raises:
            ValueError: 输入参数无效时
            Exception: 数据库操作失败时
        """
        try:
            # 输入验证
            if not trigger_type or not trigger_type.strip():
                raise ValueError("触发类型不能为空")
            if trigger_value < 0:
                raise ValueError("触发值不能为负数")
            
            # 检查勋章是否存在
            badge_query = "SELECT id FROM badges WHERE id = ?"
            badge = await db_manager.fetch_one(badge_query, (badge_id,))
            if not badge:
                raise ValueError(f"勋章ID {badge_id} 不存在")
            
            # 检查是否已存在相同的触发条件
            existing_query = "SELECT id FROM badge_triggers WHERE badge_id = ? AND trigger_type = ? AND trigger_value = ?"
            existing = await db_manager.fetch_one(existing_query, (badge_id, trigger_type.strip(), trigger_value))
            if existing:
                raise ValueError(f"该勋章已存在相同的触发条件: {trigger_type} = {trigger_value}")
            
            # 插入新触发器
            query = "INSERT INTO badge_triggers (badge_id, trigger_type, trigger_value) VALUES (?, ?, ?)"
            trigger_id = await db_manager.get_last_insert_id(
                query, 
                (badge_id, trigger_type.strip(), trigger_value)
            )
            
            logger.info(f"触发器创建成功: 勋章ID {badge_id}, 类型: {trigger_type}, 值: {trigger_value}, 触发器ID: {trigger_id}")
            return trigger_id
            
        except ValueError as e:
            logger.error(f"触发器创建验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"触发器创建失败: {e}")
            raise

    @staticmethod
    async def delete_trigger(trigger_id: int) -> bool:
        """
        删除触发器
        
        Args:
            trigger_id: 触发器ID
            
        Returns:
            删除是否成功
            
        Raises:
            ValueError: 触发器ID无效时
            Exception: 数据库操作失败时
        """
        try:
            # 检查触发器是否存在
            existing_query = "SELECT badge_id, trigger_type, trigger_value FROM badge_triggers WHERE id = ?"
            existing = await db_manager.fetch_one(existing_query, (trigger_id,))
            if not existing:
                raise ValueError(f"触发器ID {trigger_id} 不存在")
            
            # 执行删除
            delete_query = "DELETE FROM badge_triggers WHERE id = ?"
            result = await db_manager.execute_query(delete_query, (trigger_id,))
            
            if result > 0:
                logger.info(f"触发器删除成功: ID {trigger_id}, 勋章ID: {existing['badge_id']}, 类型: {existing['trigger_type']}")
                return True
            else:
                logger.warning(f"触发器删除失败: ID {trigger_id}")
                return False
                
        except ValueError as e:
            logger.error(f"触发器删除验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"触发器删除失败: {e}")
            raise

# 创建实例
incentive_manager = IncentiveManager()
