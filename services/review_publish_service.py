# -*- coding: utf-8 -*-
"""
评价发布服务

职责：将已确认的评价发布到对应频道，并回填链接。
频道配置来源：web 端“频道配置”页面（posting_channels.role = review_u2m / review_m2u）。
"""

import logging
from typing import Optional, Dict

from aiogram import Bot

from database.db_channels import posting_channels_db
from database.db_reviews_u2m import u2m_reviews_manager
from database.db_merchant_reviews import merchant_reviews_manager
from database.db_orders import OrderManager

logger = logging.getLogger(__name__)


def _build_channel_post_link(channel_chat_id: str, message_id: int) -> Optional[str]:
    try:
        if not channel_chat_id:
            return None
        if channel_chat_id.startswith('@'):
            username = channel_chat_id.lstrip('@')
            return f"https://t.me/{username}/{message_id}"
        # -100xxxxxxxx 形式
        if channel_chat_id.startswith('-100'):
            internal = channel_chat_id[4:]
            return f"https://t.me/c/{internal}/{message_id}"
        # 其他字符串，尝试当做 username
        return f"https://t.me/{channel_chat_id}/{message_id}"
    except Exception:
        return None


def _score_bar(score: Optional[int], width: int = 10, filled: str = '■', empty: str = '□') -> str:
    """将评分(0-10)渲染为条形图，例：[■■■■■□□□□□]。"""
    try:
        s = int(score or 0)
    except Exception:
        s = 0
    s = max(0, min(width, s))
    return f"[{filled * s}{empty * (width - s)}]"


class ReviewPublishService:
    @staticmethod
    async def publish_u2m(review_id: int, bot: Bot, re_publish: bool = False) -> bool:
        try:
            # 直接查询 u2m 单条记录
            from database.db_connection import db_manager
            row = await db_manager.fetch_one("SELECT * FROM reviews WHERE id=?", (review_id,))
            if not row:
                return False
            review = dict(row)
            if review.get('report_post_url') and not re_publish:
                return True

            channel = await posting_channels_db.get_active_channel_by_role('review_u2m')
            if not channel:
                logger.warning('未配置 review_u2m 频道')
                return False

            order = await OrderManager.get_order(review.get('order_id'))
            merchant_name = review.get('merchant_name') or (order.get('merchant_name') if order else '-')
            user_disp = '匿名' if review.get('is_anonymous') else (order.get('customer_username') or f"#{order.get('customer_user_id')}")

            text_lines = [
                f"📊 用户→商户评价 | 订单#{review.get('order_id')}",
                f"商户：{merchant_name}",
                f"用户：{user_disp}",
                "",
                f"🧏🏻‍♀️外貌：{review.get('rating_appearance')} 分  {_score_bar(review.get('rating_appearance'))}",
                f"💃🏻身材：{review.get('rating_figure')} 分  {_score_bar(review.get('rating_figure'))}",
                f"🏵️服务：{review.get('rating_service')} 分  {_score_bar(review.get('rating_service'))}",
                f"🈺态度：{review.get('rating_attitude')} 分  {_score_bar(review.get('rating_attitude'))}",
                f"🛏️环境：{review.get('rating_environment')} 分  {_score_bar(review.get('rating_environment'))}",
            ]
            if review.get('text_review_by_user'):
                text_lines.append("")
                text_lines.append(f"🗒️ {review.get('text_review_by_user')}")
            text = "\n".join(text_lines)

            chat_id = channel.get('channel_chat_id')
            sent = await bot.send_message(chat_id, text, parse_mode=None)
            link = _build_channel_post_link(str(chat_id), sent.message_id)
            await u2m_reviews_manager.set_report_meta(review_id, message_id=sent.message_id, url=link, published_at=sent.date)
            return True
        except Exception as e:
            logger.error(f"publish_u2m failed: {e}")
            return False

    @staticmethod
    async def publish_m2u(review_id: int, bot: Bot, re_publish: bool = False) -> bool:
        try:
            # 需要 m2u 详情（含 is_user_anonymous）
            from database.db_connection import db_manager
            row = await db_manager.fetch_one("SELECT * FROM merchant_reviews WHERE id=?", (review_id,))
            review = dict(row) if row else None
            if not review:
                return False
            if review.get('report_post_url') and not re_publish:
                return True

            channel = await posting_channels_db.get_active_channel_by_role('review_m2u')
            if not channel:
                logger.warning('未配置 review_m2u 频道')
                return False

            order = await OrderManager.get_order(review.get('order_id'))
            merchant_name = None
            try:
                if order:
                    merchant_name = order.get('merchant_name')
                if not merchant_name:
                    merchant_name = '—'
            except Exception:
                merchant_name = '—'

            # 用户匿名策略
            user_disp = '匿名' if review.get('is_user_anonymous') else (order.get('customer_username') or f"#{order.get('customer_user_id')}")

            text_lines = [
                f"📊 商户→用户评价 | 订单#{review.get('order_id')}",
                f"商户：{merchant_name}",  # 仅网名，不带 @
                f"用户：{user_disp}",
                "",
                f"出击素质：{review.get('rating_attack_quality')} 分  {_score_bar(review.get('rating_attack_quality'))}",
                f"长度：{review.get('rating_length')} 分  {_score_bar(review.get('rating_length'))}",
                f"硬度：{review.get('rating_hardness')} 分  {_score_bar(review.get('rating_hardness'))}",
                f"时间：{review.get('rating_duration')} 分  {_score_bar(review.get('rating_duration'))}",
                f"用户气质：{review.get('rating_user_temperament')} 分  {_score_bar(review.get('rating_user_temperament'))}",
            ]
            if review.get('text_review_by_merchant'):
                text_lines.append("")
                text_lines.append(f"🗒️ {review.get('text_review_by_merchant')}")
            text = "\n".join(text_lines)

            chat_id = channel.get('channel_chat_id')
            sent = await bot.send_message(chat_id, text, parse_mode=None)
            link = _build_channel_post_link(str(chat_id), sent.message_id)
            await merchant_reviews_manager.set_report_meta(review_id, message_id=sent.message_id, url=link, published_at=sent.date)
            return True
        except Exception as e:
            logger.error(f"publish_m2u failed: {e}")
            return False


review_publish_service = ReviewPublishService()
