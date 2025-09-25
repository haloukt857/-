# -*- coding: utf-8 -*-
"""
评价模块（Bot端）- 按钮+编辑模式

支持：
- U2M（用户→商户/老师）评分与文本（可后补）
- M2U（商户/老师→用户）评分与文本（可后补）

交互规范：
- 全程使用 inline button + edit_message（不刷屏）
- 列表/浏览由上层触发；本模块聚焦“开始评价→五维打分→可选文字→提交”

权限与校验：
- U2M：仅订单的 customer_user_id 可评价；订单需处于“已完成”
- M2U：仅订单的商户（telegram_chat_id）可评价；订单需处于“已完成”
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from dialogs.states import ReviewStates
from utils.telegram_helpers import safe_edit_message, safe_answer_callback

from database.db_orders import OrderManager
from database.db_reviews_u2m import u2m_reviews_manager
from database.db_merchant_reviews import merchant_reviews_manager
from database.db_connection import db_manager
from config import ADMIN_IDS
from services.review_publish_service import review_publish_service

logger = logging.getLogger(__name__)

reviews_router = Router()


# =============== 维度定义 ===============
U2M_DIM_ORDER: List[Tuple[str, str]] = [
    ("rating_appearance", "外貌"),
    ("rating_figure", "身材"),
    ("rating_service", "服务"),
    ("rating_attitude", "态度"),
    ("rating_environment", "环境"),
]

M2U_DIM_ORDER: List[Tuple[str, str]] = [
    ("rating_attack_quality", "出击素质"),
    ("rating_length", "长度"),
    ("rating_hardness", "硬度"),
    ("rating_duration", "时间"),
    ("rating_user_temperament", "用户气质"),
]


# =============== 工具函数 ===============
def _build_numbers_keyboard(prefix: str, order_id: int, dim_key: str) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(text=str(i), callback_data=f"rv:{prefix}:rate:{order_id}:{dim_key}:{i}")
        for i in range(1, 6)
    ]
    row2 = [
        InlineKeyboardButton(text=str(i), callback_data=f"rv:{prefix}:rate:{order_id}:{dim_key}:{i}")
        for i in range(6, 11)
    ]
    cancel_row = [InlineKeyboardButton(text="取消", callback_data=f"rv:{prefix}:cancel:{order_id}")]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2, cancel_row])


def _build_submit_keyboard(prefix: str, order_id: int, allow_text: bool = True) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="提交", callback_data=f"rv:{prefix}:submit:{order_id}")]]
    if allow_text:
        rows.append([
            InlineKeyboardButton(text="补充文字", callback_data=f"rv:{prefix}:text:{order_id}"),
            InlineKeyboardButton(text="重置评分", callback_data=f"rv:{prefix}:reset:{order_id}")
        ])
    rows.append([InlineKeyboardButton(text="取消", callback_data=f"rv:{prefix}:cancel:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_anon_confirm_keyboard(prefix: str, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="匿名提交", callback_data=f"rv:{prefix}:submit_anon:{order_id}")],
        [InlineKeyboardButton(text="公开提交", callback_data=f"rv:{prefix}:submit_pub:{order_id}")],
        [InlineKeyboardButton(text="返回", callback_data=f"rv:{prefix}:back_submit:{order_id}")],
    ])


def _ratings_progress_text(direction: str, ratings: Dict[str, int]) -> str:
    if direction == "u2m":
        dims = U2M_DIM_ORDER
    else:
        dims = M2U_DIM_ORDER
    lines = []
    for k, label in dims:
        v = ratings.get(k)
        lines.append(f"- {label}: {v if v else '未打'}")
    return "\n".join(lines)


def _next_dim_key(direction: str, ratings: Dict[str, int]) -> Optional[Tuple[str, str]]:
    dim_list = U2M_DIM_ORDER if direction == "u2m" else M2U_DIM_ORDER
    for k, label in dim_list:
        if not ratings.get(k):
            return k, label
    return None


def _ratings_complete(direction: str, ratings: Dict[str, int]) -> bool:
    dim_list = U2M_DIM_ORDER if direction == 'u2m' else M2U_DIM_ORDER
    for k, _ in dim_list:
        v = ratings.get(k)
        if not isinstance(v, int) or not (1 <= v <= 10):
            return False
    return True


async def _load_order(order_id: int) -> Optional[Dict]:
    try:
        return await OrderManager.get_order(order_id)
    except Exception as e:
        logger.error(f"load order failed: {e}")
        return None


async def _check_permission(direction: str, order: Dict, actor_user_id: int) -> Tuple[bool, str]:
    if order is None:
        return False, "订单不存在"
    if direction == "u2m":
        if int(order.get("customer_user_id") or 0) != int(actor_user_id):
            return False, "无权限：仅本订单的用户可评价此商户"
        return True, ""
    else:
        # m2u：校验商户身份（telegram_chat_id）
        merchant_chat_id = order.get("merchant_chat_id")
        if str(merchant_chat_id or "") != str(actor_user_id):
            return False, "无权限：仅本订单的商户可评价该用户"
        return True, ""


# =============== 入口（按钮） ===============
@reviews_router.callback_query(F.data.startswith("rv:u2m:start:"))
async def on_u2m_start(cb: CallbackQuery, state: FSMContext):
    try:
        order_id = int(cb.data.split(":")[-1])
    except Exception:
        await safe_answer_callback(cb, "参数错误")
        return

    order = await _load_order(order_id)
    ok, msg = await _check_permission("u2m", order, cb.from_user.id)
    if not ok:
        await safe_answer_callback(cb, msg, show_alert=True)
        return

    # 若订单尚未完成，点击该按钮即视为已完成
    try:
        if str(order.get("status")) != "已完成":
            await OrderManager.update_order_status(order_id, "已完成")
            order["status"] = "已完成"
    except Exception as e:
        logger.warning(f"自动标记订单完成失败（已忽略）：{e}")

    await state.set_state(ReviewStates.AwaitingRating)
    await state.update_data(
        direction="u2m",
        order_id=order_id,
        merchant_id=order["merchant_id"],
        user_id=order["customer_user_id"],
        ratings={},
        panel_chat_id=cb.message.chat.id,
        panel_msg_id=cb.message.message_id,
    )

    # 展示第一个维度
    next_dim = _next_dim_key("u2m", {})
    dim_key, label = next_dim
    text = f"📝 订单 #{order_id} | 用户→商户评价\n\n请选择评分：{label} (1-10)\n\n" + _ratings_progress_text("u2m", {})
    kb = _build_numbers_keyboard("u2m", order_id, dim_key)
    await safe_edit_message(cb.message, text, kb)
    await safe_answer_callback(cb, "请选择评分")


@reviews_router.callback_query(F.data.startswith("rv:m2u:start:"))
async def on_m2u_start(cb: CallbackQuery, state: FSMContext):
    try:
        order_id = int(cb.data.split(":")[-1])
    except Exception:
        await safe_answer_callback(cb, "参数错误")
        return

    order = await _load_order(order_id)
    ok, msg = await _check_permission("m2u", order, cb.from_user.id)
    if not ok:
        await safe_answer_callback(cb, msg, show_alert=True)
        return

    # 若订单尚未完成，点击该按钮即视为已完成
    try:
        if str(order.get("status")) != "已完成":
            await OrderManager.update_order_status(order_id, "已完成")
            order["status"] = "已完成"
    except Exception as e:
        logger.warning(f"自动标记订单完成失败（已忽略）：{e}")

    await state.set_state(ReviewStates.AwaitingRating)
    await state.update_data(
        direction="m2u",
        order_id=order_id,
        merchant_id=order["merchant_id"],
        user_id=order["customer_user_id"],
        ratings={},
        panel_chat_id=cb.message.chat.id,
        panel_msg_id=cb.message.message_id,
    )

    next_dim = _next_dim_key("m2u", {})
    dim_key, label = next_dim
    text = f"📝 订单 #{order_id} | 商户→用户评价\n\n请选择评分：{label} (1-10)\n\n" + _ratings_progress_text("m2u", {})
    kb = _build_numbers_keyboard("m2u", order_id, dim_key)
    await safe_edit_message(cb.message, text, kb)
    await safe_answer_callback(cb, "请选择评分")


# =============== 评分选择 ===============
@reviews_router.callback_query(F.data.startswith("rv:u2m:rate:"))
async def on_u2m_rate(cb: CallbackQuery, state: FSMContext):
    try:
        _, _, _, order_id_s, dim_key, val_s = cb.data.split(":")
        order_id = int(order_id_s)
        val = int(val_s)
    except Exception:
        await safe_answer_callback(cb, "参数错误")
        return
    data = await state.get_data()
    ratings = dict(data.get("ratings") or {})
    ratings[dim_key] = val
    await state.update_data(ratings=ratings)

    nxt = _next_dim_key("u2m", ratings)
    if nxt:
        next_key, label = nxt
        text = f"📝 订单 #{order_id} | 用户→商户评价\n\n请选择评分：{label} (1-10)\n\n" + _ratings_progress_text("u2m", ratings)
        kb = _build_numbers_keyboard("u2m", order_id, next_key)
        await safe_edit_message(cb.message, text, kb)
        await safe_answer_callback(cb, f"已选择 {label if label in ['外貌','身材','服务','态度','环境'] else dim_key}: {val}")
    else:
        text = f"✅ 评分完成（用户→商户）\n订单 #{order_id}\n\n" + _ratings_progress_text("u2m", ratings)
        kb = _build_submit_keyboard("u2m", order_id, allow_text=True)
        await safe_edit_message(cb.message, text, kb)
        await safe_answer_callback(cb, "评分已完成，可提交或补充文字")


@reviews_router.callback_query(F.data.startswith("rv:m2u:rate:"))
async def on_m2u_rate(cb: CallbackQuery, state: FSMContext):
    try:
        _, _, _, order_id_s, dim_key, val_s = cb.data.split(":")
        order_id = int(order_id_s)
        val = int(val_s)
    except Exception:
        await safe_answer_callback(cb, "参数错误")
        return
    data = await state.get_data()
    ratings = dict(data.get("ratings") or {})
    ratings[dim_key] = val
    await state.update_data(ratings=ratings)

    nxt = _next_dim_key("m2u", ratings)
    if nxt:
        next_key, label = nxt
        text = f"📝 订单 #{order_id} | 商户→用户评价\n\n请选择评分：{label} (1-10)\n\n" + _ratings_progress_text("m2u", ratings)
        kb = _build_numbers_keyboard("m2u", order_id, next_key)
        await safe_edit_message(cb.message, text, kb)
        await safe_answer_callback(cb, f"已选择 {label}: {val}")
    else:
        text = f"✅ 评分完成（商户→用户）\n订单 #{order_id}\n\n" + _ratings_progress_text("m2u", ratings)
        kb = _build_submit_keyboard("m2u", order_id, allow_text=True)
        await safe_edit_message(cb.message, text, kb)
        await safe_answer_callback(cb, "评分已完成，可提交或补充文字")


# =============== 补充文字 ===============
@reviews_router.callback_query(F.data.regexp(r"^rv:(u2m|m2u):text:\d+$"))
async def on_text_request(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ReviewStates.AwaitingTextReview)
    # 记录当前面板消息坐标，便于文本提交后恢复带按钮面板
    await state.update_data(panel_chat_id=cb.message.chat.id, panel_msg_id=cb.message.message_id)
    await safe_answer_callback(cb, "请发送文字评价（500-1000字内，可简要）")
    await safe_edit_message(cb.message, "📝 请输入文字评价（发送后我会更新当前面板）\n\n发送 '取消' 以退出。", None)


@reviews_router.message(ReviewStates.AwaitingTextReview)
async def on_text_receive(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    data = await state.get_data()
    direction = data.get("direction")
    order_id = data.get("order_id")
    ratings = data.get("ratings") or {}
    await state.set_state(ReviewStates.AwaitingRating)
    await state.update_data(text_review=text)

    header = "用户→商户" if direction == "u2m" else "商户→用户"
    panel = f"✅ 评分完成（{header}）\n订单 #{order_id}\n\n" + _ratings_progress_text(direction, ratings)
    panel += f"\n\n🗒️ 文字评价：\n{text[:200]}{'...' if len(text)>200 else ''}"
    kb = _build_submit_keyboard(direction, order_id, allow_text=True)
    # 恢复面板消息并带上按钮
    try:
        data = await state.get_data()
        chat_id = data.get("panel_chat_id")
        msg_id = data.get("panel_msg_id")
        if chat_id and msg_id:
            await msg.bot.edit_message_text(panel, chat_id=chat_id, message_id=msg_id, reply_markup=kb)
        else:
            # 如果没有记录，退化为发送新消息
            await msg.answer(panel, reply_markup=kb)
    except Exception as e:
        logger.warning(f"恢复评价面板失败：{e}")
        await msg.answer("已记录文字评价，点击下方按钮提交或继续修改评分。", reply_markup=kb)


# =============== 提交 / 重置 / 取消 ===============
@reviews_router.callback_query(F.data.regexp(r"^rv:(u2m|m2u):submit:\d+$"))
async def on_submit(cb: CallbackQuery, state: FSMContext):
    # 提交前先进行匿名确认
    try:
        parts = cb.data.split(":")
        direction = parts[1]
        order_id_s = parts[3]
    except Exception:
        await safe_answer_callback(cb, "参数错误")
        return
    order_id = int(order_id_s)
    # 评分完整性检查
    data = await state.get_data()
    ratings = dict(data.get('ratings') or {})
    if not _ratings_complete(direction, ratings):
        nxt = _next_dim_key(direction, ratings)
        if nxt:
            key, label = nxt
            text = f"还有未评分的项目：{label}，请先完成评分。\n\n" + _ratings_progress_text(direction, ratings)
            kb = _build_numbers_keyboard(direction, order_id, key)
            await safe_edit_message(cb.message, text, kb)
            await safe_answer_callback(cb, "请先完成所有评分")
            return
    await safe_edit_message(cb.message, "请选择是否匿名提交：", _build_anon_confirm_keyboard(direction, order_id))
    await safe_answer_callback(cb, "请选择匿名或公开")


@reviews_router.callback_query(F.data.regexp(r"^rv:(u2m|m2u):(submit_anon|submit_pub):\d+$"))
async def on_submit_final(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    direction, order_id = data.get("direction"), int(data.get("order_id"))
    ratings: Dict[str, int] = data.get("ratings") or {}
    text_review: Optional[str] = data.get("text_review")
    is_anon = cb.data.split(":")[2] == 'submit_anon'

    if not _ratings_complete(direction, ratings):
        nxt = _next_dim_key(direction, ratings)
        if nxt:
            key, label = nxt
            text = f"还有未评分的项目：{label}，请先完成评分。\n\n" + _ratings_progress_text(direction, ratings)
            kb = _build_numbers_keyboard(direction, order_id, key)
            await safe_edit_message(cb.message, text, kb)
            await safe_answer_callback(cb, "请先完成所有评分")
            return

    order = await _load_order(order_id)
    ok, msg = await _check_permission(direction, order, cb.from_user.id)
    if not ok:
        await safe_answer_callback(cb, msg, show_alert=True)
        return

    if direction == "u2m":
        # 查重，存在则更新；否则创建
        existed = await u2m_reviews_manager.get_by_order_id(order_id)
        if existed:
            ok1 = await u2m_reviews_manager.update_scores(existed["id"], ratings)
            ok2 = await u2m_reviews_manager.update_text(existed["id"], text_review)
            ok3 = await u2m_reviews_manager.set_anonymous_flag(existed["id"], is_anon)
            success = ok1 and ok2 and ok3
            review_id = existed["id"] if success else None
        else:
            review_id = await u2m_reviews_manager.create(order_id, order["merchant_id"], order["customer_user_id"], ratings, text_review, is_anonymous=is_anon)
            success = review_id is not None
    else:
        existed = await merchant_reviews_manager.get_by_order_id(order_id)
        if existed:
            ok1 = await merchant_reviews_manager.update_scores(existed["id"], ratings)
            ok2 = await merchant_reviews_manager.update_text(existed["id"], text_review)
            ok3 = await merchant_reviews_manager.set_user_anonymous_flag(existed["id"], is_anon)
            success = ok1 and ok2 and ok3
            review_id = existed["id"] if success else None
        else:
            review_id = await merchant_reviews_manager.create(order_id, order["merchant_id"], order["customer_user_id"], ratings, text_review, is_user_anonymous=is_anon)
            success = review_id is not None

    if not success:
        await safe_answer_callback(cb, "提交失败，请稍后再试", show_alert=True)
        return

    # 清状态的文字缓存，评分保留以便继续编辑（可选）
    await state.update_data(text_review=None)

    link_note = "（发布后我会在此更新链接）"
    text = (
        f"✅ 评价已提交，等待管理员确认\n订单 #{order_id}\n"
        f"🔗 报告链接：{link_note}"
    )
    await safe_edit_message(cb.message, text, None)
    await safe_answer_callback(cb, "已提交")
    # 向管理员发送完整评价信息
    try:
        await _notify_admins_new_review(direction, review_id, order, cb.message.bot)
    except Exception as e:
        logger.warning(f"管理员通知失败：{e}")


@reviews_router.callback_query(F.data.regexp(r"^rv:(u2m|m2u):reset:\d+$"))
async def on_reset(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    direction, order_id = data.get("direction"), int(data.get("order_id"))
    await state.update_data(ratings={}, text_review=None)
    nxt = _next_dim_key(direction, {})
    if not nxt:
        await safe_answer_callback(cb, "重置失败")
        return
    dim_key, label = nxt
    header = "用户→商户" if direction == "u2m" else "商户→用户"
    text = f"📝 订单 #{order_id} | {header}评价\n\n请选择评分：{label} (1-10)\n\n" + _ratings_progress_text(direction, {})
    kb = _build_numbers_keyboard(direction, order_id, dim_key)
    await safe_edit_message(cb.message, text, kb)
    await safe_answer_callback(cb, "已重置评分")


@reviews_router.callback_query(F.data.regexp(r"^rv:(u2m|m2u):back_submit:\d+$"))
async def on_back_to_submit(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    direction, order_id = data.get("direction"), int(data.get("order_id"))
    kb = _build_submit_keyboard(direction, order_id, allow_text=True)
    await safe_edit_message(cb.message, "请确认提交或继续修改。", kb)
    await safe_answer_callback(cb, "已返回")


@reviews_router.callback_query(F.data.regexp(r"^rv:(u2m|m2u):cancel:\d+$"))
async def on_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit_message(cb.message, "已取消当前评价流程。", None)
    await safe_answer_callback(cb, "已取消")


# =============== 工具：生成“开始评价”按钮（供其他handler使用） ===============
def build_start_review_button(direction: str, order_id: int, text: Optional[str] = None) -> InlineKeyboardMarkup:
    label = text or ("开始评价（用户→商户）" if direction == "u2m" else "开始评价（商户→用户）")
    prefix = "u2m" if direction == "u2m" else "m2u"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=f"rv:{prefix}:start:{order_id}")]]
    )


def get_reviews_router() -> Router:
    return reviews_router


def init_reviews_handler(bot: Bot) -> None:
    # 目前无全局初始化需求；保留接口以对齐其他handler
    pass


# =============== 管理员通知与确认 ===============
async def _notify_admins_new_review(direction: str, review_id: int, order: Dict, bot: Bot):
    # 构造完整信息
    is_u2m = (direction == 'u2m')
    if is_u2m:
        sql = "SELECT * FROM reviews WHERE id=?"
    else:
        sql = "SELECT * FROM merchant_reviews WHERE id=?"
    row = await db_manager.fetch_one(sql, (review_id,))
    if not row:
        return
    r = dict(row)

    merchant_name = order.get('merchant_name') or '—'
    merchant_username = order.get('merchant_chat_id')
    merchant_mention = f"@{str(merchant_username).lstrip('@')}" if isinstance(merchant_username, str) and merchant_username.startswith('@') else '—'
    user_username = order.get('customer_username')
    user_disp = user_username if user_username else f"{order.get('customer_user_id')}"

    title = "用户→商户评价" if is_u2m else "商户→用户评价"
    head = [
        f"🆕 {title} 提交 | 订单#{order.get('id')}",
        f"商家：{merchant_name} ({merchant_mention})",
        f"用户：{user_disp if user_username else ('用户ID ' + str(order.get('customer_user_id')))}",
        "",
    ]
    if is_u2m:
        body = [
            f"外貌：{r.get('rating_appearance')}",
            f"身材：{r.get('rating_figure')}",
            f"服务：{r.get('rating_service')}",
            f"态度：{r.get('rating_attitude')}",
            f"环境：{r.get('rating_environment')}",
        ]
        if r.get('text_review_by_user'):
            body += ["", f"🗒️ {r.get('text_review_by_user')}"]
        cb_data = f"rv:u2m:adm_confirm:{review_id}"
    else:
        body = [
            f"出击素质：{r.get('rating_attack_quality')}",
            f"长度：{r.get('rating_length')}",
            f"硬度：{r.get('rating_hardness')}",
            f"时间：{r.get('rating_duration')}",
            f"用户气质：{r.get('rating_user_temperament')}",
        ]
        if r.get('text_review_by_merchant'):
            body += ["", f"🗒️ {r.get('text_review_by_merchant')}"]
        cb_data = f"rv:m2u:adm_confirm:{review_id}"

    text = "\n".join(head + body)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ 确认评价", callback_data=cb_data)]])

    # 广播到所有管理员
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, reply_markup=kb, parse_mode=None)
        except Exception as e:
            logger.warning(f"发送给管理员 {aid} 失败：{e}")


@reviews_router.callback_query(F.data.regexp(r"^rv:(u2m|m2u):adm_confirm:\d+$"))
async def on_admin_confirm(cb: CallbackQuery):
    # 校验管理员
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("仅限管理员", show_alert=True)
        return
    parts = cb.data.split(":")
    direction = parts[1]
    review_id = int(parts[-1])
    ok = False
    if direction == 'u2m':
        ok = await u2m_reviews_manager.confirm_by_admin(review_id, cb.from_user.id)
    else:
        ok = await merchant_reviews_manager.confirm_by_admin(review_id, cb.from_user.id)
    await cb.answer("已确认" if ok else "确认失败", show_alert=not ok)
    # 确认后自动发布到频道，并通知双方
    if ok:
        link = '—'
        pub_ok = False
        if direction == 'u2m':
            pub_ok = await review_publish_service.publish_u2m(review_id, cb.message.bot)
            row = await db_manager.fetch_one("SELECT order_id, report_post_url FROM reviews WHERE id=?", (review_id,))
        else:
            pub_ok = await review_publish_service.publish_m2u(review_id, cb.message.bot)
            row = await db_manager.fetch_one("SELECT order_id, report_post_url FROM merchant_reviews WHERE id=?", (review_id,))
        if row:
            d = dict(row)
            link = d.get('report_post_url') or link
            order_id = d.get('order_id')
            try:
                order = await OrderManager.get_order(int(order_id)) if order_id else None
            except Exception:
                order = None
            if order:
                user_id = order.get('customer_user_id')
                merchant_chat_id = order.get('merchant_chat_id')
                try:
                    if direction == 'u2m':
                        if user_id:
                            await cb.message.bot.send_message(int(user_id), f"📣 你的评价已发布到频道\n🔗 {link}")
                        if merchant_chat_id:
                            await cb.message.bot.send_message(int(merchant_chat_id), f"📣 有用户对你提交了评价，已发布到频道\n🔗 {link}")
                    else:
                        if merchant_chat_id:
                            await cb.message.bot.send_message(int(merchant_chat_id), f"📣 你的评价已发布到频道\n🔗 {link}")
                        if user_id:
                            await cb.message.bot.send_message(int(user_id), f"📣 商家/老师对你提交了评价，已发布到频道\n🔗 {link}")
                except Exception:
                    pass
        try:
            await cb.message.edit_reply_markup(None)
            await cb.message.reply(f"📣 已发布：{link}" if pub_ok else "📣 发布失败")
        except Exception:
            pass


@reviews_router.callback_query(F.data.regexp(r"^rv:(u2m|m2u):adm_publish:\d+$"))
async def on_admin_publish(cb: CallbackQuery):
    # 仅管理员
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("仅限管理员", show_alert=True)
        return
    parts = cb.data.split(":")
    direction = parts[1]
    review_id = int(parts[-1])
    # 仅允许在已确认后手动（重新）发布；否则提示先确认
    if direction == 'u2m':
        row_c = await db_manager.fetch_one("SELECT is_confirmed_by_admin FROM reviews WHERE id=?", (review_id,))
        if not row_c or not dict(row_c).get('is_confirmed_by_admin'):
            await cb.answer("请先确认评价", show_alert=True)
            return
        ok = await review_publish_service.publish_u2m(review_id, cb.message.bot, re_publish=True)
        # 读取链接回显
        row = await db_manager.fetch_one("SELECT report_post_url FROM reviews WHERE id=?", (review_id,))
        link = (dict(row)['report_post_url'] if row else None) or '—'
    else:
        row_c = await db_manager.fetch_one("SELECT is_confirmed_by_admin FROM merchant_reviews WHERE id=?", (review_id,))
        if not row_c or not dict(row_c).get('is_confirmed_by_admin'):
            await cb.answer("请先确认评价", show_alert=True)
            return
        ok = await review_publish_service.publish_m2u(review_id, cb.message.bot, re_publish=True)
        row = await db_manager.fetch_one("SELECT report_post_url FROM merchant_reviews WHERE id=?", (review_id,))
        link = (dict(row)['report_post_url'] if row else None) or '—'
    await cb.answer("已发布" if ok else "发布失败", show_alert=not ok)
    try:
        await cb.message.reply(f"📣 已发布：{link}")
    except Exception:
        pass

    # 发布成功后通知用户与商户
    if ok:
        try:
            ord_row = await db_manager.fetch_one(
                "SELECT order_id FROM {} WHERE id=?".format('reviews' if direction=='u2m' else 'merchant_reviews'), (review_id,))
            order_id = dict(ord_row)['order_id'] if ord_row else None
            order = await OrderManager.get_order(int(order_id)) if order_id else None
            user_id = order.get('customer_user_id')
            merchant_chat_id = order.get('merchant_chat_id')
            if direction == 'u2m':
                # 用户评价商户：通知用户与商户
                if user_id:
                    try:
                        await cb.message.bot.send_message(int(user_id), f"📣 你的评价已发布到频道\n🔗 {link}")
                    except Exception:
                        pass
                if merchant_chat_id:
                    try:
                        await cb.message.bot.send_message(int(merchant_chat_id), f"📣 有用户对你提交了评价，已发布到频道\n🔗 {link}")
                    except Exception:
                        pass
            else:
                # 商户评价用户：通知商户与用户
                if merchant_chat_id:
                    try:
                        await cb.message.bot.send_message(int(merchant_chat_id), f"📣 你的评价已发布到频道\n🔗 {link}")
                    except Exception:
                        pass
                if user_id:
                    try:
                        await cb.message.bot.send_message(int(user_id), f"📣 商家/老师对你提交了评价，已发布到频道\n🔗 {link}")
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"发布后通知用户与商户失败：{e}")
