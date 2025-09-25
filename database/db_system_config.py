# -*- coding: utf-8 -*-
"""
系统配置数据库管理器
"""

import logging
import json
from typing import Optional, Dict, Any

from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class SystemConfigManager:
    @staticmethod
    async def get_config(key: str, default: Any = None) -> Any:
        query = "SELECT config_value FROM system_config WHERE config_key = ?"
        try:
            result = await db_manager.fetch_one(query, (key,))
            if result:
                return json.loads(result['config_value'])
            return default
        except Exception as e:
            logger.error(f"获取配置 '{key}' 时出错: {e}")
            return default

    @staticmethod
    async def set_config(key: str, value: Any, description: str = "") -> bool:
        """设置或更新配置项"""
        query = """
            INSERT OR REPLACE INTO system_config (config_key, config_value, description, updated_at)
            VALUES (?, ?, ?, ?)
        """
        try:
            config_value = json.dumps(value, ensure_ascii=False)
            await db_manager.execute_query(
                query,
                (key, config_value, description, "datetime('now', 'localtime')")
            )
            # 降低轮询锁的日志级别，避免每分钟心跳刷屏
            if key == 'polling_lock':
                logger.debug(f"配置 '{key}' 设置成功")
            else:
                logger.info(f"配置 '{key}' 设置成功")
            return True
        except Exception as e:
            logger.error(f"设置配置 '{key}' 时出错: {e}")
            return False

    @staticmethod
    async def delete_config(key: str) -> bool:
        """删除配置项"""
        query = "DELETE FROM system_config WHERE config_key = ?"
        try:
            result = await db_manager.execute_query(query, (key,))
            if result > 0:
                logger.info(f"配置 '{key}' 删除成功")
                return True
            else:
                logger.warning(f"配置 '{key}' 不存在，无法删除")
                return False
        except Exception as e:
            logger.error(f"删除配置 '{key}' 时出错: {e}")
            return False

system_config_manager = SystemConfigManager()
