# -*- coding: utf-8 -*-
"""
NotificationService

统一所有对商家的通知发送，避免在各个 handler 分散调用 bot.send_message。
提供面向场景的便捷方法：
 - notify_channel_click
 - notify_new_order
 - notify_system_alert

说明：
 - 仅依赖 merchant 字典中的 'telegram_chat_id'；为空时记录 warning 并返回 False。
 - 默认 parse_mode=None，避免 Markdown 解析问题。
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    async def _send_to_merchant_chat(bot, merchant: Dict[str, Any], text: str, *, parse_mode: Optional[str] = None) -> bool:
        try:
            chat_id = merchant.get('telegram_chat_id') if isinstance(merchant, dict) else None
            if not chat_id:
                logger.warning("商家缺少 telegram_chat_id，无法发送通知")
                return False
            await bot.send_message(chat_id, text, parse_mode=parse_mode or None)
            return True
        except Exception as e:
            logger.warning(f"发送商家通知失败: {e}")
            return False

    @staticmethod
    async def notify_channel_click(bot, merchant: Dict[str, Any], user) -> bool:
        """频道点击通知：用户点击了查看频道。
        user: aiogram.types.User
        """
        label = f"@{user.username}" if getattr(user, 'username', None) else "用户未设置用户名"
        note = (
            f"💬 系统提示:您的频道被用户（{label}）点击了。\n\n"
            "🔈 小提示：保持频道积极更新，潜在用户更容易约课哦～"
        )
        return await NotificationService._send_to_merchant_chat(bot, merchant, note, parse_mode=None)

    @staticmethod
    async def notify_new_order(
        bot,
        merchant: Dict[str, Any],
        user,
        order_id: int,
        *,
        course_type: Optional[str] = None,
        price: Optional[int] = None,
    ) -> bool:
        """新预约通知给商家。"""
        uname = getattr(user, 'username', None)
        ulabel = f"@{uname}" if uname else str(getattr(user, 'id', '用户'))
        course = course_type or '-'
        price_str = str(price) if price is not None else '-'
        msg = (
            "📩 新预约请求\n\n"
            f"用户：{ulabel}\n"
            f"订单号：{order_id}\n"
            f"选择：{course} 课程\n"
            f"价格：{price_str}"
        )
        return await NotificationService._send_to_merchant_chat(bot, merchant, msg, parse_mode=None)

    @staticmethod
    async def notify_system_alert(bot, merchant: Dict[str, Any], text: str) -> bool:
        return await NotificationService._send_to_merchant_chat(bot, merchant, text, parse_mode=None)

