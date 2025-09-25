# -*- coding: utf-8 -*-
"""
评价发布服务

职责：将已确认的评价发布到对应频道，并回填链接。
频道配置来源：web 端“频道配置”页面（posting_channels.role = review_u2m / review_m2u）。
"""

import logging
from typing import Optional, Dict
import json
import html

from aiogram import Bot

from database.db_channels import posting_channels_db
from database.db_reviews_u2m import u2m_reviews_manager
from database.db_merchant_reviews import merchant_reviews_manager
from database.db_orders import OrderManager
from database.db_merchants import MerchantManager

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


def _score_bar(score: Optional[int], width: int = 10, filled: str = '█', empty: str = '░') -> str:
    """将评分(0-10)渲染为条形图，例：[■■■■■□□□□□]。"""
    try:
        s = int(score or 0)
    except Exception:
        s = 0
    s = max(0, min(width, s))
    return f"[{filled * s}{empty * (width - s)}]"


def _esc(v: Optional[str]) -> str:
    try:
        return html.escape(str(v) if v is not None else '')
    except Exception:
        return ''


class ReviewPublishService:
    @staticmethod
    async def _get_user_display_name(user_id: Optional[int], bot: Optional[Bot] = None) -> str:
        if not user_id:
            return '-'
        try:
            from database.db_connection import db_manager
            row = await db_manager.fetch_one(
                "SELECT display_name, first_name, last_name, username FROM users WHERE user_id = ?",
                (int(user_id),)
            )
            if row:
                disp = (row.get('display_name') or '').strip()
                if not disp:
                    fn = (row.get('first_name') or '').strip()
                    ln = (row.get('last_name') or '').strip()
                    disp = (f"{fn} {ln}").strip()
                if disp:
                    return disp
                # 不使用用户名展示（按需求仅展示网名）；无网名则继续兜底
            # 尝试直接从 Telegram 读取网名
            if bot is not None and user_id:
                try:
                    chat = await bot.get_chat(int(user_id))
                    full = " ".join([p for p in [getattr(chat, 'first_name', None), getattr(chat, 'last_name', None)] if p]).strip()
                    if full:
                        return full
                except Exception:
                    pass
            # 找不到用户时，用 #id 兜底
            return f"#{user_id}"
        except Exception:
            return f"#{user_id}"

    @staticmethod
    async def _get_merchant_display_name(merchant: Optional[Dict], bot: Optional[Bot] = None) -> str:
        try:
            if not merchant:
                return '—'
            # 优先 user_info.full_name，其次 merchants.name
            ui = merchant.get('user_info')
            full = None
            if isinstance(ui, dict):
                full = (ui.get('full_name') or '').strip()
            elif isinstance(ui, str) and ui:
                import json
                try:
                    d = json.loads(ui)
                    full = (d.get('full_name') or '').strip()
                except Exception:
                    full = None
            if full:
                return full
            name = (merchant.get('name') or '').strip()
            if name:
                return name
            # 兜底：尝试从 Telegram 获取
            if bot is not None:
                try:
                    chat_id = merchant.get('telegram_chat_id')
                    if chat_id:
                        chat = await bot.get_chat(int(chat_id))
                        full2 = " ".join([p for p in [getattr(chat, 'first_name', None), getattr(chat, 'last_name', None)] if p]).strip()
                        if full2:
                            return full2
                except Exception:
                    pass
            return '—'
        except Exception:
            return '—'
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
            # 商户显示名：优先 Telegram 网名
            merchant_obj = None
            try:
                if order and order.get('merchant_id'):
                    merchant_obj = await MerchantManager.get_merchant(order.get('merchant_id'))
            except Exception:
                merchant_obj = None
            merchant_name = await ReviewPublishService._get_merchant_display_name(merchant_obj, bot)

            # 用户显示名：匿名则“匿名”；否则用 users.display_name / first+last
            user_disp = '匿名'
            if not review.get('is_anonymous'):
                uid = review.get('customer_user_id') or (order.get('customer_user_id') if order else None)
                user_disp = await ReviewPublishService._get_user_display_name(uid, bot)

            head_lines = [
                f"📊 用户→商户评价 | 订单#{_esc(review.get('order_id'))}",
                f"商户：{_esc(merchant_name)}",
                f"用户：{_esc(user_disp)}",
            ]
            # 评分条使用 HTML <pre>，保证对齐
            rating_block = (
                "<pre>"
                f"外貌 {int(review.get('rating_appearance') or 0):02d} | {_score_bar(review.get('rating_appearance'))}\n"
                f"身材 {int(review.get('rating_figure') or 0):02d} | {_score_bar(review.get('rating_figure'))}\n"
                f"服务 {int(review.get('rating_service') or 0):02d} | {_score_bar(review.get('rating_service'))}\n"
                f"态度 {int(review.get('rating_attitude') or 0):02d} | {_score_bar(review.get('rating_attitude'))}\n"
                f"环境 {int(review.get('rating_environment') or 0):02d} | {_score_bar(review.get('rating_environment'))}"
                "</pre>"
            )
            body_lines = []
            if review.get('text_review_by_user'):
                body_lines.append(f"🗒️ {_esc(review.get('text_review_by_user'))}")
            text = "\n".join(head_lines) + "\n" + rating_block
            if body_lines:
                text += "\n" + "\n".join(body_lines)

            chat_id = channel.get('channel_chat_id')
            sent = await bot.send_message(chat_id, text, parse_mode='HTML')
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
            # 商户显示名
            merchant_obj = None
            try:
                if order and order.get('merchant_id'):
                    merchant_obj = await MerchantManager.get_merchant(order.get('merchant_id'))
            except Exception:
                merchant_obj = None
            merchant_name = await ReviewPublishService._get_merchant_display_name(merchant_obj, bot)

            # 用户匿名策略：否则显示 users 表中的显示名
            user_disp = '匿名'
            if not review.get('is_user_anonymous'):
                uid = review.get('user_id') or (order.get('customer_user_id') if order else None)
                user_disp = await ReviewPublishService._get_user_display_name(uid, bot)

            head_lines = [
                f"📊 商户→用户评价 | 订单#{_esc(review.get('order_id'))}",
                f"商户：{_esc(merchant_name)}",
                f"用户：{_esc(user_disp)}",
            ]
            rating_block = (
                "<pre>"
                f"素质 {int(review.get('rating_attack_quality') or 0):02d} | {_score_bar(review.get('rating_attack_quality'))}\n"
                f"长度 {int(review.get('rating_length') or 0):02d} | {_score_bar(review.get('rating_length'))}\n"
                f"硬度 {int(review.get('rating_hardness') or 0):02d} | {_score_bar(review.get('rating_hardness'))}\n"
                f"时间 {int(review.get('rating_duration') or 0):02d} | {_score_bar(review.get('rating_duration'))}\n"
                f"气质 {int(review.get('rating_user_temperament') or 0):02d} | {_score_bar(review.get('rating_user_temperament'))}"
                "</pre>"
            )
            body_lines = []
            if review.get('text_review_by_merchant'):
                body_lines.append(f"🗒️ {_esc(review.get('text_review_by_merchant'))}")
            text = "\n".join(head_lines) + "\n" + rating_block
            if body_lines:
                text += "\n" + "\n".join(body_lines)

            chat_id = channel.get('channel_chat_id')
            sent = await bot.send_message(chat_id, text, parse_mode='HTML')
            link = _build_channel_post_link(str(chat_id), sent.message_id)
            await merchant_reviews_manager.set_report_meta(review_id, message_id=sent.message_id, url=link, published_at=sent.date)
            return True
        except Exception as e:
            logger.error(f"publish_m2u failed: {e}")
            return False


review_publish_service = ReviewPublishService()
