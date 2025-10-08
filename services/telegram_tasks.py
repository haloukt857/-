# -*- coding: utf-8 -*-
"""
Telegram 相关的后台任务封装：编辑频道贴文、发送消息、删除消息。

对外只暴露 enqueue_* 方法，将任务提交给进程内任务队列执行。
"""

import logging
from typing import Any, Dict, List, Optional
import aiohttp

from services.task_queue import enqueue_task
from config import BOT_TOKEN

logger = logging.getLogger(__name__)


# ---------- 任务入队 API ---------- #

def enqueue_edit_caption(merchant_id: int) -> None:
    enqueue_task(_job_edit_caption, int(merchant_id))


def enqueue_send_message(chat_id: int | str, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
    enqueue_task(_job_send_message, chat_id, text, reply_markup)


def enqueue_delete_merchant_posts(merchant_id: int) -> None:
    enqueue_task(_job_delete_merchant_posts, int(merchant_id))


# ---------- 任务实现 ---------- #

async def _job_edit_caption(merchant_id: int) -> None:
    try:
        from services.review_publish_service import refresh_merchant_post_reviews
        ok = await refresh_merchant_post_reviews(merchant_id)
        if not ok:
            logger.warning(f"编辑caption任务未成功: merchant_id={merchant_id}")
    except Exception as e:
        logger.error(f"编辑caption任务异常: {e}")


async def _job_send_message(chat_id: int | str, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
    try:
        api_send = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload: Dict[str, Any] = {
            'chat_id': chat_id,
            'text': text,
            'disable_web_page_preview': True,
        }
        if reply_markup:
            payload['reply_markup'] = reply_markup
        async with aiohttp.ClientSession() as session:
            async with session.post(api_send, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.json()
                if not data.get('ok'):
                    logger.warning(f"发送消息失败: chat_id={chat_id}, resp={data}")
    except Exception as e:
        logger.error(f"发送消息任务异常: {e}")


async def _job_delete_merchant_posts(merchant_id: int) -> None:
    """删除记录在 merchant_posts 的频道消息；若无记录，尝试 post_url 兜底。"""
    try:
        from database.db_channel_posts import list_posts, delete_records_for_merchant
        from database.db_merchants import MerchantManager as _MM
        from services.review_publish_service import _parse_channel_post_link

        rows = await list_posts(merchant_id)
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        deleted_any = False
        async with aiohttp.ClientSession() as session:
            for r in rows or []:
                try:
                    payload = {'chat_id': r.get('chat_id'), 'message_id': int(r.get('message_id'))}
                    async with session.post(api_url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                        data = await resp.json()
                        if data.get('ok'):
                            deleted_any = True
                        else:
                            logger.warning(f"删除消息失败: {r} -> {data}")
                except Exception as _e:
                    logger.warning(f"删除消息异常: {r} -> {_e}")
        if rows:
            await delete_records_for_merchant(merchant_id)

        # 兜底：若没有记录，尝试用 post_url 删除首条
        if not rows:
            try:
                merchant = await _MM.get_merchant_by_id(merchant_id)
                url = (merchant.get('post_url') or '').strip() if merchant else ''
                if url:
                    parsed = _parse_channel_post_link(url)
                    if parsed:
                        chat_id_val, message_id_val = parsed
                        async with aiohttp.ClientSession() as session:
                            async with session.post(api_url, json={'chat_id': chat_id_val, 'message_id': int(message_id_val)}, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                                data = await resp.json()
                                if not data.get('ok'):
                                    logger.warning(f"post_url 删除失败: {url} -> {data}")
            except Exception as _fe:
                logger.warning(f"post_url 兜底删除异常: {_fe}")
    except Exception as e:
        logger.error(f"删除频道消息任务异常: {e}")

