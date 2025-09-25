"""
发布计划/时间槽 数据库管理
"""

import logging
from typing import List, Dict, Any, Optional
from database.db_connection import db_manager

logger = logging.getLogger(__name__)


class PostingTimeSlotsDB:
    @staticmethod
    async def add_slot(time_str: str, display_order: int = 0, is_active: bool = True) -> int:
        query = "INSERT INTO posting_time_slots (time_str, display_order, is_active) VALUES (?, ?, ?)"
        return await db_manager.get_last_insert_id(query, (time_str, display_order, 1 if is_active else 0))

    @staticmethod
    async def get_all_slots() -> List[Dict[str, Any]]:
        query = "SELECT * FROM posting_time_slots ORDER BY is_active DESC, display_order ASC, time_str ASC"
        rows = await db_manager.fetch_all(query)
        return [dict(r) for r in rows]

    @staticmethod
    async def get_active_slots() -> List[Dict[str, Any]]:
        query = "SELECT * FROM posting_time_slots WHERE is_active = 1 ORDER BY display_order ASC, time_str ASC"
        rows = await db_manager.fetch_all(query)
        return [dict(r) for r in rows]

    @staticmethod
    async def toggle_slot(slot_id: int, is_active: bool) -> bool:
        query = "UPDATE posting_time_slots SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        return (await db_manager.execute_query(query, (1 if is_active else 0, slot_id))) > 0

    @staticmethod
    async def delete_slot(slot_id: int) -> bool:
        query = "DELETE FROM posting_time_slots WHERE id = ?"
        return (await db_manager.execute_query(query, (slot_id,))) > 0

    @staticmethod
    async def update_slot(slot_id: int, time_str: Optional[str] = None, display_order: Optional[int] = None) -> bool:
        updates = []
        params = []
        if time_str is not None:
            updates.append("time_str = ?")
            params.append(time_str)
        if display_order is not None:
            updates.append("display_order = ?")
            params.append(display_order)
        if not updates:
            return False
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(slot_id)
        query = f"UPDATE posting_time_slots SET {', '.join(updates)} WHERE id = ?"
        return (await db_manager.execute_query(query, tuple(params))) > 0


posting_time_slots_db = PostingTimeSlotsDB()

