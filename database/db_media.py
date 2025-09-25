# -*- coding: utf-8 -*-
"""
媒体文件数据库管理器

负责与 `media` 表相关的所有数据库操作。
"""

import logging
from typing import Optional, List, Dict, Any

# 导入项目模块
# 媒体文件数据库管理模块

from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class MediaDB:
    """媒体文件数据库操作类"""

    @staticmethod
    async def get_telegram_file_id(media_id: int) -> Optional[str]:
        """
        根据媒体ID获取Telegram文件ID。

        Args:
            media_id: 媒体表中的主键ID。

        Returns:
            对应的 telegram_file_id，如果未找到则返回 None。
        """
        query = "SELECT telegram_file_id FROM media WHERE id = ?"
        try:
            result = await db_manager.fetch_one(query, (media_id,))
            if result:
                logger.debug(f"成功从数据库获取 media_id {media_id} 对应的 file_id: {result['telegram_file_id']}")
                return result['telegram_file_id']
            else:
                logger.warning(f"在数据库中未找到 media_id: {media_id}")
                return None
        except Exception as e:
            logger.error(f"通过 media_id ({media_id}) 获取 file_id 时发生数据库错误: {e}")
            return None

    @staticmethod
    async def get_media_by_merchant_id(merchant_id: int) -> List[Dict[str, Any]]:
        """
        获取指定商家的所有媒体文件。

        Args:
            merchant_id: 商家ID。

        Returns:
            一个包含媒体文件信息的字典列表。
        """
        query = "SELECT id, telegram_file_id, media_type, sort_order FROM media WHERE merchant_id = ? ORDER BY sort_order ASC"
        try:
            results = await db_manager.fetch_all(query, (merchant_id,))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取商家 {merchant_id} 的媒体文件时出错: {e}")
            return []

    @staticmethod
    async def add_media(merchant_id: int, telegram_file_id: str, media_type: str, sort_order: int = 0) -> Optional[int]:
        """
        为商家添加一个新的媒体文件记录。
        """
        query = "INSERT INTO media (merchant_id, telegram_file_id, media_type, sort_order) VALUES (?, ?, ?, ?)"
        try:
            return await db_manager.get_last_insert_id(query, (merchant_id, telegram_file_id, media_type, sort_order))
        except Exception as e:
            logger.error(f"为商家 {merchant_id} 添加媒体文件时出错: {e}")
            return None

# 创建实例
media_db = MediaDB()
