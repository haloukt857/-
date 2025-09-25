# -*- coding: utf-8 -*-
"""
地区数据库管理器

负责与 `cities` 和 `districts` 表相关的所有数据库操作。
"""

import logging
from typing import List, Dict, Any, Optional

# 导入项目模块
# 地区管理数据库模块

from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class RegionManager:

    @staticmethod
    async def search_regions(search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜索地区
        
        Args:
            search_term: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            List[Dict]: 匹配的地区列表
        """
        try:
            if not search_term.strip():
                return []
            
            # 搜索城市和地区
            query = """
                SELECT c.id as city_id, c.name as city_name,
                       d.id as district_id, d.name as district_name
                FROM cities c
                LEFT JOIN districts d ON c.id = d.city_id
                WHERE c.name LIKE ? OR d.name LIKE ?
                ORDER BY c.name, d.name
                LIMIT ?
            """
            
            search_pattern = f"%{search_term.strip()}%"
            results = await db_manager.fetch_all(query, (search_pattern, search_pattern, limit))
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"搜索地区失败: {e}")
            return []

    @staticmethod
    async def get_all_cities_with_districts() -> List[Dict[str, Any]]:
        """获取所有城市及其包含的地区"""
        query = """
            SELECT c.id as city_id, c.name as city_name, c.is_active as city_is_active,
                   d.id as district_id, d.name as district_name, d.is_active as district_is_active
            FROM cities c
            LEFT JOIN districts d ON c.id = d.city_id
            ORDER BY c.id, d.id;
        """
        try:
            results = await db_manager.fetch_all(query)
            cities = {}
            for row in results:
                city_id = row['city_id']
                if city_id not in cities:
                    cities[city_id] = {
                        'id': city_id,
                        'name': row['city_name'],
                        'is_active': row['city_is_active'],
                        'districts': []
                    }
                if row['district_id'] is not None:
                    cities[city_id]['districts'].append({
                        'id': row['district_id'],
                        'name': row['district_name'],
                        'is_active': row['district_is_active']
                    })
            return list(cities.values())
        except Exception as e:
            logger.error(f"获取所有城市和地区时出错: {e}")
            return []

    # 注释：add_city 已废弃，使用 create_city 替代

    # 注释：add_district 已废弃，使用 create_district 替代

    @staticmethod
    async def toggle_city_status(city_id: int) -> bool:
        """切换城市的激活状态"""
        query = "UPDATE cities SET is_active = NOT is_active WHERE id = ?"
        try:
            await db_manager.execute_query(query, (city_id,))
            return True
        except Exception as e:
            logger.error(f"切换城市 {city_id} 状态时出错: {e}")
            return False

    @staticmethod
    async def toggle_district_status(district_id: int) -> bool:
        """切换地区的激活状态"""
        query = "UPDATE districts SET is_active = NOT is_active WHERE id = ?"
        try:
            await db_manager.execute_query(query, (district_id,))
            return True
        except Exception as e:
            logger.error(f"切换地区 {district_id} 状态时出错: {e}")
            return False

    @staticmethod
    async def delete_city(city_id: int) -> bool:
        """删除一个城市及其所有地区"""
        query = "DELETE FROM cities WHERE id = ?"
        try:
            await db_manager.execute_query(query, (city_id,))
            return True
        except Exception as e:
            logger.error(f"删除城市 {city_id} 时出错: {e}")
            return False

    @staticmethod
    async def delete_district(district_id: int) -> bool:
        """删除一个地区"""
        query = "DELETE FROM districts WHERE id = ?"
        try:
            await db_manager.execute_query(query, (district_id,))
            return True
        except Exception as e:
            logger.error(f"删除地区 {district_id} 时出错: {e}")
            return False

    @staticmethod
    async def get_districts_by_city(city_id: int) -> List[Dict[str, Any]]:
        """获取指定城市下的所有地区"""
        query = "SELECT * FROM districts WHERE city_id = ? AND is_active = TRUE ORDER BY name ASC"
        try:
            results = await db_manager.fetch_all(query, (city_id,))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取城市 {city_id} 的地区时出错: {e}")
            return []

    @staticmethod
    async def get_all_districts_by_city(city_id: int) -> List[Dict[str, Any]]:
        """获取指定城市下的所有区县（包括禁用的），用于删除前检查"""
        query = "SELECT * FROM districts WHERE city_id = ? ORDER BY name ASC"
        try:
            results = await db_manager.fetch_all(query, (city_id,))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取城市 {city_id} 的所有区县时出错: {e}")
            return []

    @staticmethod
    async def get_all_cities() -> List[Dict[str, Any]]:
        """获取所有城市（含启用/禁用）"""
        query = "SELECT * FROM cities ORDER BY display_order ASC, name ASC"
        try:
            results = await db_manager.fetch_all(query)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取所有城市时出错: {e}")
            return []

    @staticmethod
    async def get_active_cities() -> List[Dict[str, Any]]:
        """获取所有活跃城市（仅 is_active = TRUE）"""
        query = "SELECT * FROM cities WHERE is_active = TRUE ORDER BY display_order ASC, name ASC"
        try:
            results = await db_manager.fetch_all(query)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取活跃城市时出错: {e}")
            return []

    @staticmethod
    async def get_city_by_id(city_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取城市信息"""
        query = "SELECT * FROM cities WHERE id = ?"
        try:
            result = await db_manager.fetch_one(query, (city_id,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取城市 {city_id} 信息时出错: {e}")
            return None

    @staticmethod
    async def get_district_by_id(district_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取地区信息"""
        query = "SELECT * FROM districts WHERE id = ?"
        try:
            result = await db_manager.fetch_one(query, (district_id,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取地区 {district_id} 信息时出错: {e}")
            return None

    @staticmethod
    async def update_city_display_order(city_id: int, display_order: int) -> bool:
        """更新城市显示顺序"""
        query = "UPDATE cities SET display_order = ? WHERE id = ?"
        try:
            await db_manager.execute_query(query, (display_order, city_id))
            return True
        except Exception as e:
            logger.error(f"更新城市 {city_id} 显示顺序时出错: {e}")
            return False

    @staticmethod
    async def update_district_display_order(district_id: int, display_order: int) -> bool:
        """更新地区显示顺序"""
        query = "UPDATE districts SET display_order = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        try:
            await db_manager.execute_query(query, (display_order, district_id))
            return True
        except Exception as e:
            logger.error(f"更新地区 {district_id} 显示顺序时出错: {e}")
            return False

    # 注释：update_city_name 已废弃，使用 update_city 替代

    # 注释：update_district_name 已废弃，使用 update_district 替代

    @staticmethod
    async def get_active_cities_with_districts() -> List[Dict[str, Any]]:
        """获取所有活跃的城市及其活跃的地区"""
        query = """
            SELECT c.id as city_id, c.name as city_name, c.display_order as city_order,
                   d.id as district_id, d.name as district_name, d.display_order as district_order
            FROM cities c
            LEFT JOIN districts d ON c.id = d.city_id AND d.is_active = TRUE
            WHERE c.is_active = TRUE
            ORDER BY c.display_order ASC, c.name ASC, d.display_order ASC, d.name ASC
        """
        try:
            results = await db_manager.fetch_all(query)
            cities = {}
            for row in results:
                city_id = row['city_id']
                if city_id not in cities:
                    cities[city_id] = {
                        'id': city_id,
                        'name': row['city_name'],
                        'display_order': row['city_order'],
                        'districts': []
                    }
                if row['district_id'] is not None:
                    cities[city_id]['districts'].append({
                        'id': row['district_id'],
                        'name': row['district_name'],
                        'display_order': row['district_order']
                    })
            return list(cities.values())
        except Exception as e:
            logger.error(f"获取活跃城市和地区时出错: {e}")
            return []

    @staticmethod
    async def get_all_districts() -> List[Dict[str, Any]]:
        """获取所有地区（含城市信息）"""
        query = """
            SELECT d.id, d.name, d.city_id, d.display_order, d.is_active,
                   d.created_at, d.updated_at, c.name as city_name
            FROM districts d
            LEFT JOIN cities c ON d.city_id = c.id
            ORDER BY d.city_id ASC, d.display_order ASC, d.name ASC
        """
        try:
            results = await db_manager.fetch_all(query)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取所有地区时出错: {e}")
            return []

    @staticmethod
    async def get_city_by_name(name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取城市信息"""
        query = "SELECT * FROM cities WHERE name = ?"
        try:
            result = await db_manager.fetch_one(query, (name,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"根据名称获取城市 {name} 信息时出错: {e}")
            return None

    @staticmethod
    async def create_city(name: str, is_active: bool = True, display_order: int = 0) -> Optional[int]:
        """创建城市"""
        if not name or not name.strip():
            logger.error("城市名称不能为空")
            return None
        
        query = "INSERT INTO cities (name, is_active, display_order) VALUES (?, ?, ?)"
        try:
            return await db_manager.get_last_insert_id(query, (name.strip(), is_active, display_order))
        except Exception as e:
            logger.error(f"创建城市 '{name}' 时出错: {e}")
            return None

    @staticmethod
    async def update_city(city_id: int, name: str, is_active: bool = True) -> bool:
        """更新城市信息"""
        if not name or not name.strip():
            logger.error("城市名称不能为空")
            return False
        
        query = "UPDATE cities SET name = ?, is_active = ? WHERE id = ?"
        try:
            await db_manager.execute_query(query, (name.strip(), is_active, city_id))
            return True
        except Exception as e:
            logger.error(f"更新城市 {city_id} 时出错: {e}")
            return False

    @staticmethod
    async def get_district_by_name(city_id: int, name: str) -> Optional[Dict[str, Any]]:
        """根据城市ID和名称获取区县信息"""
        query = "SELECT * FROM districts WHERE city_id = ? AND name = ?"
        try:
            result = await db_manager.fetch_one(query, (city_id, name))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"根据名称获取区县 {name} 信息时出错: {e}")
            return None

    @staticmethod
    async def create_district(city_id: int, name: str, is_active: bool = True, display_order: int = 0) -> Optional[int]:
        """创建区县"""
        if not name or not name.strip():
            logger.error("区县名称不能为空")
            return None
        
        if not city_id or city_id <= 0:
            logger.error("城市ID必须是有效的正整数")
            return None
        
        query = "INSERT INTO districts (city_id, name, is_active, display_order) VALUES (?, ?, ?, ?)"
        try:
            return await db_manager.get_last_insert_id(query, (city_id, name.strip(), is_active, display_order))
        except Exception as e:
            logger.error(f"为城市ID {city_id} 创建区县 '{name}' 时出错: {e}")
            return None

    @staticmethod
    async def update_district(district_id: int, city_id: int, name: str, is_active: bool = True) -> bool:
        """更新区县信息"""
        if not name or not name.strip():
            logger.error("区县名称不能为空")
            return False
        
        query = "UPDATE districts SET city_id = ?, name = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        try:
            await db_manager.execute_query(query, (city_id, name.strip(), is_active, district_id))
            return True
        except Exception as e:
            logger.error(f"更新区县 {district_id} 时出错: {e}")
            return False

# 创建实例
region_manager = RegionManager()
