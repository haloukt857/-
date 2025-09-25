"""
发布频道配置 数据库访问
"""

import logging
from typing import List, Dict, Any, Optional
from database.db_connection import db_manager

logger = logging.getLogger(__name__)


class PostingChannelsDB:
    @staticmethod
    async def add_channel(display_name: str, channel_chat_id: Optional[str], channel_link: Optional[str], is_active: bool = True, role: str = 'post') -> int:
        query = "INSERT INTO posting_channels (display_name, channel_chat_id, channel_link, is_active, role) VALUES (?, ?, ?, ?, ?)"
        return await db_manager.get_last_insert_id(query, (display_name, channel_chat_id, channel_link, 1 if is_active else 0, role))

    @staticmethod
    async def get_all_channels() -> List[Dict[str, Any]]:
        rows = await db_manager.fetch_all("SELECT * FROM posting_channels ORDER BY is_active DESC, id DESC")
        return [dict(r) for r in rows]

    @staticmethod
    async def get_active_channel() -> Optional[Dict[str, Any]]:
        # 兼容：默认取 role='post' 的当前激活
        row = await db_manager.fetch_one("SELECT * FROM posting_channels WHERE is_active = 1 AND role = 'post' ORDER BY id DESC LIMIT 1")
        return dict(row) if row else None

    @staticmethod
    async def get_active_channel_by_role(role: str) -> Optional[Dict[str, Any]]:
        row = await db_manager.fetch_one("SELECT * FROM posting_channels WHERE is_active = 1 AND role = ? ORDER BY id DESC LIMIT 1", (role,))
        return dict(row) if row else None

    @staticmethod
    async def set_active_channel(channel_id: int) -> bool:
        # 兼容旧方法：将指定记录的 role 取出后，仅对该 role 范围内切换
        try:
            row = await db_manager.fetch_one("SELECT role FROM posting_channels WHERE id = ?", (channel_id,))
            role = dict(row)['role'] if row else 'post'
            await db_manager.execute_query("UPDATE posting_channels SET is_active = 0 WHERE role = ?", (role,))
            return (await db_manager.execute_query("UPDATE posting_channels SET is_active = 1 WHERE id = ?", (channel_id,))) > 0
        except Exception as e:
            logger.error(f"设置激活频道失败: {e}")
            return False

    @staticmethod
    async def set_active_channel_for_role(channel_id: int) -> bool:
        # 与 set_active_channel 等价（按该记录的 role 切换激活）
        return await PostingChannelsDB.set_active_channel(channel_id)

    @staticmethod
    async def update_channel(channel_id: int, display_name: Optional[str] = None, channel_chat_id: Optional[str] = None, channel_link: Optional[str] = None) -> bool:
        updates = []
        params = []
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if channel_chat_id is not None:
            updates.append("channel_chat_id = ?")
            params.append(channel_chat_id)
        if channel_link is not None:
            updates.append("channel_link = ?")
            params.append(channel_link)
        if not updates:
            return False
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(channel_id)
        query = f"UPDATE posting_channels SET {', '.join(updates)} WHERE id = ?"
        return (await db_manager.execute_query(query, tuple(params))) > 0

    @staticmethod
    async def delete_channel(channel_id: int) -> bool:
        return (await db_manager.execute_query("DELETE FROM posting_channels WHERE id = ?", (channel_id,))) > 0


posting_channels_db = PostingChannelsDB()
