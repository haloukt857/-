# -*- coding: utf-8 -*-
"""
评价发布服务

职责：将已确认的评价发布到对应频道，并回填链接。
频道配置来源：web 端“频道配置”页面（posting_channels.role = review_u2m / review_m2u）。
"""

import logging
from typing import Optional, Dict, Tuple, List
import json
import html

from aiogram import Bot
import aiohttp

from database.db_channels import posting_channels_db
from database.db_reviews_u2m import u2m_reviews_manager
from database.db_merchant_reviews import merchant_reviews_manager
from database.db_orders import OrderManager
from database.db_merchants import MerchantManager
from config import DEEPLINK_BOT_USERNAME

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


def _parse_channel_post_link(url: str) -> Optional[Tuple[str, int]]:
    """解析频道贴文URL，返回 (chat_id, message_id)。
    支持两种形式：
    - https://t.me/c/<internal>/<message_id>  -> chat_id = -100<internal>
    - https://t.me/<username>/<message_id>    -> chat_id = @username
    """
    try:
        import re
        m = re.search(r"https://t\.me/(c/([\d]+)/([\d]+)|([A-Za-z0-9_]+)/([\d]+))", str(url))
        if not m:
            return None
        if m.group(2) and m.group(3):
            return (f"-100{m.group(2)}", int(m.group(3)))
        if m.group(4) and m.group(5):
            return (f"@{m.group(4)}", int(m.group(5)))
        return None
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
        if not user_id or bot is None:
            return ''
        # 只取 Telegram 网名：first_name [+ last_name]；不读数据库、不退回用户名/ID
        try:
            chat = await bot.get_chat(int(user_id))
            parts = []
            fn = getattr(chat, 'first_name', None)
            ln = getattr(chat, 'last_name', None)
            if isinstance(fn, str) and fn.strip():
                parts.append(fn.strip())
            if isinstance(ln, str) and ln.strip():
                parts.append(ln.strip())
            return " ".join(parts)
        except Exception:
            return ''

    @staticmethod
    async def _get_merchant_display_name(merchant: Optional[Dict], bot: Optional[Bot] = None) -> str:
        try:
            if not merchant:
                return '—'
            # 仅使用商户资料中的名称（非用户名）
            name = (merchant.get('name') or '').strip()
            return name or '—'
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

            # 构建 deeplink 与商户频道链接
            mid = (order.get('merchant_id') if order else None) or (merchant_obj.get('id') if merchant_obj else None)
            did = merchant_obj.get('district_id') if merchant_obj else None
            district_name = (merchant_obj.get('district_name') or '').strip() if merchant_obj else ''
            p_price = str(merchant_obj.get('p_price') or '').strip() if merchant_obj else ''
            bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
            link_merchant = f"https://t.me/{bot_u}?start=m_{mid}" if bot_u and mid else ''
            link_district = f"https://t.me/{bot_u}?start=d_{did}" if bot_u and did else ''
            city_id = merchant_obj.get('city_id') if merchant_obj else None
            city_suffix = f"_c_{city_id}" if city_id else ''
            link_price_p = f"https://t.me/{bot_u}?start=price_p_{p_price}{city_suffix}" if bot_u and p_price else ''

            # 报告链接：严格使用“贴文发布”频道（role=post）的链接
            try:
                post_channel = await posting_channels_db.get_active_channel()  # role='post'
            except Exception:
                post_channel = None
            channel_url = (post_channel.get('channel_link') or '').strip() if post_channel else ''

            # 顶部信息（按指定模板，不带 deeplink）
            report_line = f"🔖 报告 {html.escape(channel_url)}" if channel_url else "🔖 报告"
            name_line = (
                f"🔆 艺名 <a href=\"{link_merchant}\">{_esc(merchant_name)}</a>"
                if link_merchant else f"🔆 艺名 {_esc(merchant_name)}"
            )
            loc_line = (
                f"📌 位置 <a href=\"{link_district}\">{_esc(district_name)}</a>"
                if link_district else f"📌 位置 {_esc(district_name)}"
            )

            # 费用：仅展示本订单课程与价格，带城市上下文 deeplink
            ct = (order.get('course_type') or '').upper() if order else ''
            price_val = order.get('price') if order else None
            price_str = str(price_val) if (price_val is not None) else ''
            fee_line = "✨ 费用"
            if ct == 'P' and price_str:
                link_price = f"https://t.me/{bot_u}?start=price_p_{price_str}{city_suffix}" if bot_u else ''
                fee_disp = f"{_esc(price_str)}P"
                fee_line = f"✨ 费用 <a href=\"{link_price}\">{fee_disp}</a>" if link_price else f"✨ 费用 {fee_disp}"
            elif ct == 'PP' and price_str:
                link_price = f"https://t.me/{bot_u}?start=price_pp_{price_str}{city_suffix}" if bot_u else ''
                fee_disp = f"{_esc(price_str)}PP"
                fee_line = f"✨ 费用 <a href=\"{link_price}\">{fee_disp}</a>" if link_price else f"✨ 费用 {fee_disp}"

            # 文字详情：标题单独一行，正文从下一行开始
            detail_header = "📜 文字详情："
            details_body = None
            if review.get('text_review_by_user'):
                details_body = _esc(review.get('text_review_by_user'))

            # 留名与时间（同一行）
            from datetime import datetime
            date_disp = ''
            try:
                cts = order.get('created_at') if order else None
                if isinstance(cts, str):
                    dt = datetime.fromisoformat(cts.replace('Z',''))
                else:
                    dt = cts
                if dt:
                    date_disp = dt.strftime('%Y.%m.%d')
            except Exception:
                date_disp = ''
            footer_line = f"🙋🏻 留名 {_esc(user_disp or '')} ｜ 🗓️ 时间 {date_disp}".strip()

            # 评分块（使用 <pre>）
            rating_head = "🌟 总体评分："
            rating_block = (
                "<pre>"
                f"▫️ 外貌 {int(review.get('rating_appearance') or 0):02d} | {_score_bar(review.get('rating_appearance'))}\n"
                f"▫️ 身材 {int(review.get('rating_figure') or 0):02d} | {_score_bar(review.get('rating_figure'))}\n"
                f"▫️ 服务 {int(review.get('rating_service') or 0):02d} | {_score_bar(review.get('rating_service'))}\n"
                f"▫️ 态度 {int(review.get('rating_attitude') or 0):02d} | {_score_bar(review.get('rating_attitude'))}\n"
                f"▫️ 环境 {int(review.get('rating_environment') or 0):02d} | {_score_bar(review.get('rating_environment'))}"
                "</pre>"
            )

            # 组装：单行费用 → 空行 → 评分区；其后文字详情与留名
            header_lines = [report_line, name_line, loc_line, fee_line, "", rating_head]
            text = "\n".join(header_lines) + "\n" + rating_block + "\n\n"
            if details_body:
                text += detail_header + "\n" + details_body + "\n\n"
            text += footer_line + "\n\n"

            chat_id = channel.get('channel_chat_id')
            sent = await bot.send_message(chat_id, text, parse_mode='HTML')
            link = _build_channel_post_link(str(chat_id), sent.message_id)
            await u2m_reviews_manager.set_report_meta(review_id, message_id=sent.message_id, url=link, published_at=sent.date)
            # 发布成功后，刷新商户主帖的“评价”区（累积所有U2M链接）
            if mid:
                try:
                    await refresh_merchant_post_reviews(int(mid))
                except Exception:
                    pass
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

            # 顶部信息
            bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
            mid = (order.get('merchant_id') if order else None) or (merchant_obj.get('id') if merchant_obj else None)
            did = merchant_obj.get('district_id') if merchant_obj else None
            district_name = (merchant_obj.get('district_name') or '').strip() if merchant_obj else ''
            link_merchant = f"https://t.me/{bot_u}?start=m_{mid}" if bot_u and mid else ''
            link_district = f"https://t.me/{bot_u}?start=d_{did}" if bot_u and did else ''

            # 费用（按订单课程类型与价格）
            ct = (order.get('course_type') or '').upper() if order else ''
            price_val = order.get('price') if order else None
            price_str = str(price_val) if (price_val is not None) else ''
            city_id = merchant_obj.get('city_id') if merchant_obj else None
            city_suffix = f"_c_{city_id}" if city_id else ''
            if ct == 'P' and price_str:
                link_price = f"https://t.me/{bot_u}?start=price_p_{price_str}{city_suffix}" if bot_u else ''
                fee_disp = f"{_esc(price_str)}P"
                fee_line = f"费用 <a href=\"{link_price}\">{fee_disp}</a>" if link_price else f"费用 {fee_disp}"
            elif ct == 'PP' and price_str:
                link_price = f"https://t.me/{bot_u}?start=price_pp_{price_str}{city_suffix}" if bot_u else ''
                fee_disp = f"{_esc(price_str)}PP"
                fee_line = f"费用 <a href=\"{link_price}\">{fee_disp}</a>" if link_price else f"费用 {fee_disp}"
            else:
                fee_line = "费用"

            # 报告链接：严格使用“贴文发布”频道（role=post）
            try:
                post_channel = await posting_channels_db.get_active_channel()  # role='post'
            except Exception:
                post_channel = None
            channel_url = (post_channel.get('channel_link') or '').strip() if post_channel else ''

            report_line = f"报告 {html.escape(channel_url)}" if channel_url else "报告"
            name_line = (f"艺名 <a href=\"{link_merchant}\">{_esc(merchant_name)}</a>" if link_merchant else f"艺名 {_esc(merchant_name)}")
            loc_line = (f"位置 <a href=\"{link_district}\">{_esc(district_name)}</a>" if link_district else f"位置 {_esc(district_name)}")

            # 评分块改为 <pre>（使用真实换行）
            rating_block = (
                "<pre>"
                f"素质 {int(review.get('rating_attack_quality') or 0):02d} | {_score_bar(review.get('rating_attack_quality'))}\n"
                f"长度 {int(review.get('rating_length') or 0):02d} | {_score_bar(review.get('rating_length'))}\n"
                f"硬度 {int(review.get('rating_hardness') or 0):02d} | {_score_bar(review.get('rating_hardness'))}\n"
                f"时间 {int(review.get('rating_duration') or 0):02d} | {_score_bar(review.get('rating_duration'))}\n"
                f"气质 {int(review.get('rating_user_temperament') or 0):02d} | {_score_bar(review.get('rating_user_temperament'))}"
                "</pre>"
            )

            # 文字详情
            body_lines = []
            if review.get('text_review_by_merchant'):
                body_lines.append(f"文字详情：\n{_esc(review.get('text_review_by_merchant'))}")

            # 留名（商户名）+ 时间
            from datetime import datetime
            date_disp = ''
            try:
                cts = order.get('created_at') if order else None
                if isinstance(cts, str):
                    dt = datetime.fromisoformat(cts.replace('Z',''))
                else:
                    dt = cts
                if dt:
                    date_disp = dt.strftime('%Y.%m.%d')
            except Exception:
                date_disp = ''
            footer_line = f"留名 { _esc(merchant_name or '') } ｜ 时间 {date_disp}".strip()

            text = "\n".join([report_line, name_line, loc_line, fee_line]) + "\n\n" + rating_block
            if body_lines:
                text += "\n\n" + "\n".join(body_lines)
            if footer_line:
                text += "\n\n" + footer_line

            chat_id = channel.get('channel_chat_id')
            sent = await bot.send_message(chat_id, text, parse_mode='HTML')
            link = _build_channel_post_link(str(chat_id), sent.message_id)
            await merchant_reviews_manager.set_report_meta(review_id, message_id=sent.message_id, url=link, published_at=sent.date)
            return True
        except Exception as e:
            logger.error(f"publish_m2u failed: {e}")
            return False


review_publish_service = ReviewPublishService()


async def refresh_merchant_post_reviews(merchant_id: int) -> bool:
    """刷新商户帖子caption中的“评价”区，拼接所有U2M评价链接。

    约束：
    - 不兜底，caption 超长或调用失败将直接返回 False，不做重试。
    - 仅当商户状态为 published 且存在 post_url 时执行。
    """
    try:
        from database.db_merchants import MerchantManager
        from config import DEEPLINK_BOT_USERNAME, BOT_TOKEN
        from utils.caption_renderer import render_channel_caption_md

        merchant = await MerchantManager.get_merchant_by_id(merchant_id)
        if not merchant:
            return False
        if str(merchant.get('status')) != 'published':
            return False
        post_url = (merchant.get('post_url') or '').strip()
        if not post_url:
            return False

        # 取所有已确认的 U2M 评价，并收集频道URL
        reviews: List[Dict] = await u2m_reviews_manager.list_by_merchant(merchant_id, limit=1000, offset=0, admin_mode=False)
        urls = [str(r.get('report_post_url')).strip() for r in (reviews or []) if r and r.get('report_post_url')]

        # 组装“评价1/评价2/...”
        rev_payload = [{"text": f"评价{i+1}", "url": u} for i, u in enumerate(urls)]
        bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
        caption = await render_channel_caption_md(merchant, bot_u, reviews=rev_payload)

        parsed = _parse_channel_post_link(post_url)
        if not parsed:
            return False
        chat_id_val, message_id_val = parsed

        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageCaption"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_url,
                json={
                    'chat_id': chat_id_val,
                    'message_id': int(message_id_val),
                    'caption': caption,
                    'parse_mode': 'MarkdownV2'
                },
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json()
                return bool(data.get('ok'))
    except Exception as e:
        logger.error(f"refresh_merchant_post_reviews failed: {e}")
        return False
