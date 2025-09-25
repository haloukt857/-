# -*- coding: utf-8 -*-
"""
RegionManager 补丁文件（统一为城市/区县标准）
添加缺少的方法以支持城市-区县二级地区管理
"""

from database.db_regions import RegionManager as BaseRegionManager
from database.db_connection import db_manager
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RegionManagerEnhanced(BaseRegionManager):
    """增强版RegionManager，添加缺少的方法（城市/区县）"""
    
    @staticmethod
    async def get_cities() -> List[Dict[str, Any]]:
        """获取所有城市列表"""
        try:
            query = "SELECT id, name, code, is_active FROM cities WHERE is_active = TRUE ORDER BY name"
            results = await db_manager.fetch_all(query)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取城市列表失败: {e}")
            return []
    
    @staticmethod 
    async def get_districts_by_city(city_id: int) -> List[Dict[str, Any]]:
        """获取指定城市下的所有区县"""
        try:
            query = """
                SELECT d.id, d.name, d.code, d.city_id, d.is_active,
                       c.name as city_name
                FROM districts d
                JOIN cities c ON d.city_id = c.id
                WHERE d.city_id = ? AND d.is_active = TRUE
                ORDER BY d.name
            """
            results = await db_manager.fetch_all(query, (city_id,))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取城市 {city_id} 的区县列表失败: {e}")
            return []
    
    @staticmethod
    async def get_district(district_id: int) -> Optional[Dict[str, Any]]:
        """获取单个区县信息"""
        try:
            query = """
                SELECT d.id, d.name, d.code, d.city_id, d.is_active,
                       c.name as city_name
                FROM districts d
                JOIN cities c ON d.city_id = c.id
                WHERE d.id = ?
            """
            result = await db_manager.fetch_one(query, (district_id,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取区县 {district_id} 信息失败: {e}")
            return None
    
    @staticmethod
    async def get_city(city_id: int) -> Optional[Dict[str, Any]]:
        """获取单个城市信息"""
        try:
            query = "SELECT id, name, code, is_active FROM cities WHERE id = ?"
            result = await db_manager.fetch_one(query, (city_id,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取城市 {city_id} 信息失败: {e}")
            return None

# 替换原有的RegionManager
RegionManager = RegionManagerEnhanced
