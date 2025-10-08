# -*- coding: utf-8 -*-
"""
记录与管理商户在频道中的帖子（每条频道消息一行）。
用于后续的跨回合同步编辑与删除。
"""

import logging
from typing import List, Dict, Optional

from .db_connection import db_manager

logger = logging.getLogger(__name__)


async def ensure_table() -> None:
    try:
        await db_manager.execute_query(
            """
            CREATE TABLE IF NOT EXISTS merchant_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                chat_id TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                post_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db_manager.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_merchant_posts_mid ON merchant_posts(merchant_id)"
        )
        await db_manager.execute_query(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_merchant_posts_unique ON merchant_posts(merchant_id, chat_id, message_id)"
        )
    except Exception as e:
        logger.error(f"初始化 merchant_posts 表失败: {e}")


async def record_posts(merchant_id: int, chat_id: str, message_ids: List[int], url_builder=None) -> int:
    """保存一组频道消息记录。

    Args:
        merchant_id: 商户ID
        chat_id: 频道chat_id（'@username' 或 '-100xxxx'）
        message_ids: 频道消息ID列表
        url_builder: 可选函数，根据 (chat_id, message_id) 返回 URL
    Returns:
        插入条数
    """
    await ensure_table()
    count = 0
    for mid in message_ids or []:
        try:
            url = url_builder(chat_id, mid) if callable(url_builder) else None
            await db_manager.execute_query(
                "INSERT OR IGNORE INTO merchant_posts (merchant_id, chat_id, message_id, post_url) VALUES (?,?,?,?)",
                (merchant_id, str(chat_id), int(mid), url)
            )
            count += 1
        except Exception as e:
            logger.warning(f"保存频道消息记录失败: merchant_id={merchant_id}, chat_id={chat_id}, message_id={mid}, error={e}")
    return count


async def list_posts(merchant_id: int) -> List[Dict]:
    await ensure_table()
    try:
        rows = await db_manager.fetch_all(
            "SELECT id, merchant_id, chat_id, message_id, post_url, created_at FROM merchant_posts WHERE merchant_id = ? ORDER BY created_at ASC",
            (merchant_id,)
        )
        return [dict(r) for r in (rows or [])]
    except Exception as e:
        logger.error(f"查询频道消息记录失败: merchant_id={merchant_id}, error={e}")
        return []


async def delete_records_for_merchant(merchant_id: int) -> int:
    await ensure_table()
    try:
        rc = await db_manager.execute_query("DELETE FROM merchant_posts WHERE merchant_id = ?", (merchant_id,))
        return int(rc or 0)
    except Exception as e:
        logger.error(f"删除频道消息记录失败: merchant_id={merchant_id}, error={e}")
        return 0

