# -*- coding: utf-8 -*-
"""
地区手动白名单与总开关。

开关：system_config.manual_region_gate_enabled ∈ {'true','false'}
白名单表：region_manual_whitelist(merchant_id)
"""

import logging
from typing import Optional, Set

from .db_connection import db_manager

logger = logging.getLogger(__name__)


async def is_manual_gate_enabled() -> bool:
    try:
        row = await db_manager.fetch_one(
            "SELECT config_value FROM system_config WHERE config_key = 'manual_region_gate_enabled'"
        )
        val = (row['config_value'] if row and 'config_value' in row.keys() else (row[0] if row else '')).strip().lower() if row else ''
        return val in {'1', 'true', 'yes', 'on'}
    except Exception as e:
        logger.debug(f"读取手动地区开关失败: {e}")
        return False


async def set_manual_gate_enabled(enabled: bool) -> bool:
    try:
        await db_manager.execute_query(
            "INSERT OR REPLACE INTO system_config (config_key, config_value, description) VALUES ('manual_region_gate_enabled', ?, '启用机器人地区搜索白名单')",
            ('true' if enabled else 'false',)
        )
        return True
    except Exception as e:
        logger.error(f"设置手动地区开关失败: {e}")
        return False


async def add_whitelist(merchant_id: int) -> bool:
    try:
        await db_manager.execute_query(
            "INSERT OR IGNORE INTO region_manual_whitelist (merchant_id) VALUES (?)",
            (int(merchant_id),)
        )
        return True
    except Exception as e:
        logger.error(f"加入地区白名单失败: {e}")
        return False


async def remove_whitelist(merchant_id: int) -> bool:
    try:
        await db_manager.execute_query(
            "DELETE FROM region_manual_whitelist WHERE merchant_id = ?",
            (int(merchant_id),)
        )
        return True
    except Exception as e:
        logger.error(f"移除地区白名单失败: {e}")
        return False


async def get_whitelist_set(merchant_ids: list[int]) -> Set[int]:
    if not merchant_ids:
        return set()
    try:
        qmarks = ','.join(['?'] * len(merchant_ids))
        rows = await db_manager.fetch_all(
            f"SELECT merchant_id FROM region_manual_whitelist WHERE merchant_id IN ({qmarks})",
            tuple(merchant_ids)
        )
        return {int(r['merchant_id']) for r in (rows or [])}
    except Exception as e:
        logger.error(f"获取白名单集合失败: {e}")
        return set()

