# -*- coding: utf-8 -*-
"""
用户核心命令处理器
处理 /start, /profile 等核心命令。
"""

import logging
import asyncio
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import DEEPLINK_BOT_USERNAME, ADMIN_IDS
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

# 导入数据库管理器
from database.db_users import user_manager
from database.db_regions import region_manager
from database.db_merchants import merchant_manager
from database.db_orders import order_manager
from database.db_connection import db_manager
from database.db_fsm import create_fsm_db_manager
from database.db_media import media_db
from handlers.reviews import build_start_review_button
from database.db_logs import ActivityLogsDatabase
from services.notification_service import NotificationService
from database.db_templates import template_manager
from database.db_connection import db_manager
from utils.template_utils import get_template_async

# 导入键盘工具以提供主菜单
from utils.keyboard_utils import (
    create_main_menu_keyboard,
    create_city_keyboard,
    create_district_keyboard,
    create_merchants_keyboard,
    create_merchant_detail_keyboard,
)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
router = Router()
_fsm_db_profile = create_fsm_db_manager(db_manager)

# 会话级“当前城市”上下文（内存态）。
# 作用：当用户通过城市深链/callback选择了城市后，后续列表型深链（价格/标签）仅返回该城市的商家。
# 注意：该上下文仅保存在内存，进程重启会清空；若需持久化可后续扩展到 users 表。
USER_CITY_CTX: dict[int, int] = {}

def _set_user_city_ctx(user_id: int, city_id: int) -> None:
    try:
        USER_CITY_CTX[user_id] = int(city_id)
    except Exception:
        USER_CITY_CTX[user_id] = city_id

def _get_user_city_ctx(user_id: int) -> int | None:
    return USER_CITY_CTX.get(user_id)

def _clear_user_city_ctx(user_id: int) -> None:
    try:
        if user_id in USER_CITY_CTX:
            del USER_CITY_CTX[user_id]
    except Exception:
        pass

def get_user_router() -> Router:
    """获取用户路由器"""
    return router

async def init_user_handler(bot):
    """初始化用户处理器"""
    logger.info("用户处理器已初始化")


async def _render_channel_post_html(merchant: dict) -> str:
    """按频道统一模板渲染商户贴文（MarkdownV2）。
    为与频道帖子完全同步，这里也聚合该商户的所有 U2M 评价链接，
    以「评价1」「评价2」… 的形式渲染到“✍️评价：”行（每行最多3个）。
    """
    bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
    mid = merchant.get('id')
    did = merchant.get('district_id')
    p_price = str(merchant.get('p_price') or '').strip()
    pp_price = str(merchant.get('pp_price') or '').strip()
    link_merchant = f"https://t.me/{bot_u}?start=m_{mid}" if bot_u and mid else ''
    link_district = f"https://t.me/{bot_u}?start=d_{did}" if bot_u and did else ''
    link_price_p = f"https://t.me/{bot_u}?start=price_p_{p_price}" if bot_u and p_price else ''
    link_price_pp = f"https://t.me/{bot_u}?start=price_pp_{pp_price}" if bot_u and pp_price else ''
    link_report = f"https://t.me/{bot_u}?start=report_{mid}" if bot_u and mid else ''

    from utils.caption_renderer import render_channel_caption_md
    from database.db_reviews_u2m import u2m_reviews_manager

    # 聚合所有已确认且有效的 U2M 评价链接
    reviews = await u2m_reviews_manager.list_by_merchant(int(mid), limit=1000, offset=0, admin_mode=False) if mid else []
    urls = [str(r.get('report_post_url')).strip() for r in (reviews or []) if r and r.get('report_post_url')]
    rev_payload = [{"text": f"评价{i+1}", "url": u} for i, u in enumerate(urls)]

    return await render_channel_caption_md(merchant, bot_u, reviews=rev_payload)

@router.callback_query(F.data == "profile")
async def profile_callback_handler(callback: CallbackQuery):
    await callback.answer()
    # 注意：callback.message.from_user 是机器人自身；真正的用户是 callback.from_user
    await profile_command(callback.message, override_user=callback.from_user)

@router.callback_query(F.data == "search_start")
async def search_start_callback(callback: CallbackQuery):
    """开始地区搜索：展示活跃城市列表。"""
    try:
        await callback.answer()
        cities = await region_manager.get_active_cities()
        if not cities:
            from utils.telegram_helpers import safe_edit_message as _sem
            await _sem(callback.message, "当前暂无可用城市")
            return
        kb = create_city_keyboard(cities)
        from utils.telegram_helpers import safe_edit_message as _sem
        await _sem(callback.message, "📌 选择城市：", reply_markup=kb)
    except Exception as e:
        logger.error(f"search_start 处理失败: {e}")
        await callback.message.answer("获取城市列表失败")

@router.callback_query(F.data.startswith("city_"))
async def select_city_callback(callback: CallbackQuery):
    """选择城市后，展示该城市下的地区列表。"""
    try:
        await callback.answer()
        city_id = int(callback.data.split("_", 1)[1])
        _set_user_city_ctx(callback.from_user.id, city_id)
        districts = await region_manager.get_districts_by_city(city_id)
        if not districts:
            from utils.telegram_helpers import safe_edit_message as _sem
            await _sem(callback.message, "该城市暂无可用地区")
            return
        kb = create_district_keyboard(districts, city_id)
        from utils.telegram_helpers import safe_edit_message as _sem
        await _sem(callback.message, "📌 选择区域：", reply_markup=kb)
    except Exception as e:
        logger.error(f"选择城市失败: {e}")
        await callback.message.answer("获取地区列表失败")

@router.callback_query(F.data.startswith("district_"))
async def select_district_callback(callback: CallbackQuery):
    """选择地区后，展示该地区的商户列表（默认展示所有状态）。"""
    try:
        await callback.answer()
        district_id = int(callback.data.split("_", 1)[1])
        # 获取该地区所属城市ID用于返回按钮
        district = await region_manager.get_district_by_id(district_id)
        city_id = district.get("city_id") if district else 0
        # 只展示“活跃”商户（已审核/已发布，且未过期）
        merchants = await merchant_manager.list_active_by_district(district_id, limit=30, offset=0)
        if not merchants:
            from utils.telegram_helpers import safe_edit_message as _sem
            await _sem(callback.message, "该地区暂无商户")
            return
        kb = create_merchants_keyboard(merchants, city_id or 0)
        from utils.telegram_helpers import safe_edit_message as _sem
        district_name = district.get('name') if isinstance(district, dict) else ''
        await _sem(callback.message, f"💃 查看「{district_name}」的老师/商家：", reply_markup=kb)
    except Exception as e:
        logger.error(f"选择地区失败: {e}")
        await callback.message.answer("获取商户列表失败")

@router.callback_query(F.data.startswith("merchant_"))
async def merchant_detail_callback(callback: CallbackQuery):
    """查看单个商户详情。"""
    try:
        await callback.answer()
        merchant_id = int(callback.data.split("_", 1)[1])
        merchant = await merchant_manager.get_merchant_by_id(merchant_id)
        if not merchant:
            from utils.telegram_helpers import safe_edit_message as _sem
            await _sem(callback.message, "商户不存在或已删除")
            return
        # 使用频道统一模板（MarkdownV2）渲染详情，并在原消息上就地更新
        detail_md = await _render_channel_post_html(merchant)
        kb = create_merchant_detail_keyboard(merchant)
        from utils.telegram_helpers import safe_edit_message as _sem
        await _sem(callback.message, detail_md, reply_markup=kb, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"商户详情失败: {e}")
        from utils.telegram_helpers import safe_edit_message as _sem
        await _sem(callback.message, "获取商户详情失败")

@router.callback_query(F.data.startswith("view_channel_"))
async def view_channel_callback(callback: CallbackQuery):
    """查看频道：记录一次点击并通知商家，同时给用户返回频道链接。"""
    try:
        await callback.answer()
        merchant_id = int(callback.data.split("_", 2)[-1])
        merchant = await merchant_manager.get_merchant_by_id(merchant_id)
        if not merchant:
            await callback.message.answer("商户不存在或已删除")
            return
        # 记录点击（后台任务，不阻塞主流程）
        try:
            _t1 = asyncio.create_task(
                ActivityLogsDatabase.log_button_click(
                    user_id=callback.from_user.id,
                    button_id="view_channel",
                    merchant_id=merchant_id,
                    additional_details={}
                )
            )
            _t1.add_done_callback(lambda t: logger.error(f"log_button_click 失败: {t.exception()}") if t.exception() else None)
        except Exception:
            pass
        # 通知商家（后台任务，不阻塞主流程）
        try:
            _t2 = asyncio.create_task(NotificationService.notify_channel_click(callback.bot, merchant, callback.from_user))
            _t2.add_done_callback(lambda t: logger.warning(f"发送频道点击通知失败: {t.exception()}") if t.exception() else None)
        except Exception:
            pass
        # 向用户展示频道链接
        ch = merchant.get('channel_chat_id') or merchant.get('channel_link')
        if isinstance(ch, str):
            link = ch if ch.startswith('http') else f"https://t.me/{ch.lstrip('@')}"
            await callback.message.answer(f"📣 打开频道：{link}")
    except Exception as e:
        logger.error(f"查看频道失败: {e}")
        await callback.message.answer("打开频道失败，请稍后重试")

@router.callback_query(F.data.startswith("order_now_"))
async def order_now_callback(callback: CallbackQuery):
    """用户点击“立即预约”后：创建一条尝试预约订单，并分别通知用户与商户。"""
    try:
        await callback.answer()
        merchant_id = int(callback.data.split('_', 2)[-1])
        merchant = await merchant_manager.get_merchant_by_id(merchant_id)
        if not merchant:
            await callback.message.answer("商户不存在或已删除")
            return

        user = callback.from_user
        price = merchant.get('p_price') or 0
        order_id = await order_manager.create_order({
            'customer_user_id': user.id,
            'customer_username': user.username,
            'merchant_id': merchant_id,
            'price': int(price) if str(price).isdigit() else 0,
            'course_type': None,
            'status': '尝试预约'
        })

        # UX：不再重复发送商家预览，直接确认，并将当前消息键盘替换为“返回列表”
        try:
            back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ 返回商家列表", callback_data=f"district_{merchant.get('district_id')}")]])
            await callback.message.edit_reply_markup(reply_markup=back_kb)
        except Exception:
            pass
        # 用户确认文案（统一固定内容）
        admin_display = "@admin"
        try:
            if ADMIN_IDS:
                first_admin = ADMIN_IDS[0]
                try:
                    admin_chat = await callback.bot.get_chat(first_admin)
                    if getattr(admin_chat, 'username', None):
                        admin_display = f"@{admin_chat.username}"
                except Exception:
                    pass
        except Exception:
            pass

        confirm_text = (
            "✅ 榜上老师均已通过认证\n\n"
            "📅 请放心预约。\n\n"
            f"🙋🏻 有任何问题及时联系管理员 {admin_display}\n\n"
            "✍️ 写真实评价会获得积分哦～ \n\n"
            "🥇 还可以请老师返评你的出击表现，可以在机器人内查看排行榜。"
        )
        choose_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="预约P课程", callback_data=f"order_choose_p_{merchant_id}_{order_id}")],
            [InlineKeyboardButton(text="预约PP课程", callback_data=f"order_choose_pp_{merchant_id}_{order_id}")],
        ])
        await callback.message.answer(confirm_text, reply_markup=choose_kb, parse_mode=None)

        # 商户通知改到用户选择 P/PP 后进行
    except Exception as e:
        logger.error(f"预约入口处理失败: {e}")
        await callback.message.answer("预约处理失败，请重试")

@router.callback_query(F.data.startswith("order_choose_"))
async def order_choose_callback(callback: CallbackQuery):
    """用户在确认后选择预约P/PP课程，回复商家联系方式。"""
    try:
        await callback.answer()
        data = callback.data  # order_choose_p_{id} 或 order_choose_pp_{id}
        parts = data.split("_")
        if len(parts) < 5:
            await callback.message.answer("参数错误，请重试")
            return
        merchant_id = int(parts[3])
        order_id = int(parts[4])
        merchant = await merchant_manager.get_merchant_by_id(merchant_id)
        if not merchant:
            await callback.message.answer("商户不存在或已删除")
            return
        name = merchant.get('name') or '-'
        raw_contact = (merchant.get('contact_info') or '').strip()
        # 选择价格并写入订单
        selected_is_p = (parts[2] == 'p')
        sel_price = int(merchant.get('p_price') or 0) if selected_is_p else int(merchant.get('pp_price') or 0)
        try:
            await order_manager.update_order(order_id, {'price': sel_price, 'course_type': ('P' if selected_is_p else 'PP')})
        except Exception:
            pass

        # 生成用户可读信息（不包含 https 链接；@username 后面加一个空格）
        if raw_contact.startswith('@') and len(raw_contact) > 1:
            mention = raw_contact + ' '
        else:
            mention = raw_contact or '未设置'

        text = (
            f"📑 {name} 老师/商家的TG为：\n"
            f"▌{mention}\n"
            f"▌\n"
            f"▌请主动联系私聊～"
        )
        await callback.message.answer(text, disable_web_page_preview=False, parse_mode=None)

        # 发送“完成后评价”入口（用户端）
        try:
            u2m_kb = build_start_review_button('u2m', order_id, text='❗️完成后评价老师')
            await callback.message.answer('上完课后点击按钮进行评价：', reply_markup=u2m_kb)
        except Exception as e:
            logger.warning(f"发送用户评价入口失败（忽略）：{e}")

        # 选择了 P/PP 后再通知商户（后台任务，不阻塞主流程）
        try:
            _t3 = asyncio.create_task(
                NotificationService.notify_new_order(
                    bot=callback.bot,
                    merchant=merchant,
                    user=callback.from_user,
                    order_id=order_id,
                    course_type=('P' if selected_is_p else 'PP'),
                    price=sel_price,
                )
            )
            _t3.add_done_callback(lambda t: logger.warning(f"通知商户失败: {t.exception()}") if t.exception() else None)
        except Exception:
            pass

        # 发送“完成后评价”入口（商户/老师端）
        try:
            m_chat_id = merchant.get('telegram_chat_id')
            if m_chat_id:
                m2u_kb = build_start_review_button('m2u', order_id, text='❗️完成后评价狼友')
                await callback.bot.send_message(int(m_chat_id), '上完课后点击按钮进行评价：', reply_markup=m2u_kb)
        except Exception as e:
            logger.warning(f"发送商户评价入口失败（忽略）：{e}")
    except Exception as e:
        logger.error(f"处理预约课程回调失败: {e}")
        await callback.message.answer("处理失败，请重试")

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """/start 唯一深链处理：不做回退。
    支持：
      - m_{id}: 展示商户详情
      - d_{district_id}: 列出该区活跃未过期商户
      - price_p_{value}: 列出P价=值的商户
      - price_pp_{value}: 列出PP价=值的商户
      - kw_{keyword_id}: 列出含该关键词的商户
      - report_{merchant_id}: 评价入口占位
    无匹配则给出“无效链接”提示，不回退到主菜单。
    """
    # 避免处于某个输入态时 /start 被当作输入文本拦截
    try:
        await state.clear()
    except Exception:
        pass
    await user_manager.create_or_update_user(message.from_user.id, message.from_user.username)

    payload = None
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) > 1:
        payload = (parts[1] or '').strip()

    # 普通 /start（无参数）：展示主菜单（保持原有体验）
    if not payload:
        welcome_text = await template_manager.get_template('user_welcome_message')
        await message.answer(welcome_text, reply_markup=create_main_menu_keyboard())
        return

    # c_{city_id}: 设置“当前城市”上下文（不输出多余文案）
    if payload.startswith('c_'):
        try:
            cid = int(payload.split('_',1)[1])
            city = await region_manager.get_city_by_id(cid)
            if city:
                _set_user_city_ctx(message.from_user.id, cid)
                # 使用不可见但被Telegram视为非空的占位字符
                await message.answer("\u2063")
                return
        except Exception as e:
            logger.warning(f"c_ 解析失败: {e}")
        await message.answer("无效的城市链接")
        return

    # c_clear: 清除“当前城市”上下文，恢复全城市范围
    if payload == 'c_clear':
        _clear_user_city_ctx(message.from_user.id)
        await message.answer("已清除城市筛选，将显示全部城市范围。")
        return

    # m_{id}
    if payload.startswith('m_'):
        try:
            mid = int(payload.split('_',1)[1])
            merchant = await merchant_manager.get_merchant_by_id(mid)
            if not merchant:
                await message.answer("未找到商家")
                return
            html = await _render_channel_post_html(merchant)
            kb = create_merchant_detail_keyboard(merchant)
            await message.answer(html, reply_markup=kb, parse_mode='MarkdownV2')
            return
        except Exception as e:
            logger.warning(f"m_ 解析失败: {e}")
            await message.answer("无效的商家链接")
            return

    # d_{district_id}
    if payload.startswith('d_'):
        try:
            did = int(payload.split('_',1)[1])
            items = await merchant_manager.list_active_by_district(did, limit=20)
            if not items:
                await message.answer("该地区暂无可用商家")
                return
            # 与“地区搜索”一致：仅展示商户按钮列表（callback），不输出冗余文字行
            try:
                district = await region_manager.get_district_by_id(did)
                city_id = district.get("city_id") if district else 0
            except Exception:
                city_id = 0
            kb = create_merchants_keyboard(items, city_id or 0)
            district_name = (district or {}).get('name', '')
            await message.answer(f"💃 查看「{district_name}」的老师/商家：", reply_markup=kb)
            return
        except Exception as e:
            logger.warning(f"d_ 解析失败: {e}")
            await message.answer("无效的地区链接")
            return

    # price_p_{value} / price_pp_{value}
    if payload.startswith('price_p_') or payload.startswith('price_pp_'):
        try:
            is_p = payload.startswith('price_p_')
            rest = payload[len('price_p_'):] if is_p else payload[len('price_pp_'):]
            # 支持附带城市上下文：price_p_{value}_c_{cityId}
            city_id_from_link = None
            if '_c_' in rest:
                price_part, city_part = rest.split('_c_', 1)
                val = int(price_part)
                try:
                    city_id_from_link = int(city_part)
                except Exception:
                    city_id_from_link = None
            else:
                val = int(rest)
            if is_p:
                items = await merchant_manager.list_active_by_price('p_price', val, limit=20)
            else:
                items = await merchant_manager.list_active_by_price('pp_price', val, limit=20)
            # 若已有“当前城市”上下文，仅展示该城市商家
            ctx_city_id = city_id_from_link or _get_user_city_ctx(message.from_user.id)
            if ctx_city_id:
                try:
                    city = await region_manager.get_city_by_id(ctx_city_id)
                    cname = (city or {}).get('name')
                    if cname:
                        items = [m for m in items if (m.get('city_name') == cname)]
                except Exception:
                    pass
            if not items:
                await message.answer("暂无同价位的商家")
                return
            # 仅展示按钮列表（两列），点击进入商户详情，再进行预约
            buttons = [InlineKeyboardButton(text=m.get('name'), callback_data=f"merchant_{m['id']}") for m in items]
            keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
            label = 'P' if is_p else 'PP'
            await message.answer(f"💵 {label} 价格为 {val} 的老师：", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
            return
        except Exception as e:
            logger.warning(f"price_* 解析失败: {e}")
            await message.answer("无效的价格链接")
            return

    # kw_{keyword_id}
    if payload.startswith('kw_'):
        try:
            kid = int(payload.split('_',1)[1])
            items = await merchant_manager.list_active_by_keyword(kid, limit=20)
            # 若已有“当前城市”上下文，仅展示该城市商家
            ctx_city_id = _get_user_city_ctx(message.from_user.id)
            if ctx_city_id:
                try:
                    city = await region_manager.get_city_by_id(ctx_city_id)
                    cname = (city or {}).get('name')
                    if cname:
                        items = [m for m in items if (m.get('city_name') == cname)]
                except Exception:
                    pass
            if not items:
                await message.answer("暂无该标签的商家")
                return
            # 仅展示按钮列表（两列），点击进入商户详情，再进行预约
            buttons = [InlineKeyboardButton(text=m.get('name'), callback_data=f"merchant_{m['id']}") for m in items]
            keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
            await message.answer(f"✅ 按关键词 {kid} 查找：", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
            return
        except Exception as e:
            logger.warning(f"kw_ 解析失败: {e}")
            await message.answer("无效的标签链接")
            return

    # report_{merchant_id}（占位）
    if payload.startswith('report_'):
        await message.answer("评价入口即将上线，敬请期待")
        return

    await message.answer("无效链接参数")

@router.message(Command("profile"))
async def profile_command(message: Message, override_user=None):
    """处理 /profile 命令。
    - 若用户是商家：展示“我的商户资料”并提供基础字段的快速编辑入口。
    - 否则：展示用户成长资料（等级/积分/勋章）。
    """
    user_ctx = override_user or message.from_user
    user_id = user_ctx.id

    # 1) 若是商家：展示商户基础资料 + 编辑按钮
    try:
        merchant = await merchant_manager.get_merchant_by_chat_id(user_id)
    except Exception:
        merchant = None

    if merchant:
        name = merchant.get('name') or (user_ctx.full_name or '-')
        p_price = merchant.get('p_price') or '-'
        pp_price = merchant.get('pp_price') or '-'
        desc = merchant.get('custom_description') or '-'
        channel = merchant.get('channel_chat_id') or '-'

        # 地区名称
        city_name = '-'
        district_name = '-'
        try:
            district_id = merchant.get('district_id')
            if district_id:
                d = await region_manager.get_district_by_id(int(district_id))
                if d:
                    district_name = d.get('name') or '-'
                    city_id = d.get('city_id')
                    if city_id:
                        c = await region_manager.get_city_by_id(int(city_id))
                        if c:
                            city_name = c.get('name') or '-'
        except Exception:
            pass

        # 预览使用“频道发布模板”，仅发文本（不带媒体）
        html_preview = await _render_channel_post_html({
            **merchant,
            'name': name,
            'p_price': p_price,
            'pp_price': pp_price,
            'custom_description': desc,
            'city_name': city_name,
            'district_name': district_name,
            'channel_chat_id': channel,
        })

        def _short(s: str, n: int = 18) -> str:
            s = str(s or '-')
            return s if len(s) <= n else (s[: n - 1] + '…')

        tmap = {'teacher': '老师', 'business': '商家'}
        type_txt = tmap.get((merchant.get('merchant_type') or '').lower(), '-')
        channel_val = merchant.get('channel_chat_id') or ''
        channel_label = f"修改频道：{_short(channel_val, 16)}" if channel_val else "修改频道"

        # 统计媒体数量用于按钮文案
        media_count = 0
        try:
            existing_media = await media_db.get_media_by_merchant_id(merchant['id'])
            media_count = len(existing_media or [])
        except Exception:
            media_count = 0

        submit_label = "✅ 提交审核" if (merchant.get('status') not in ("pending_approval","approved","published")) else "已提交审核"

        # 发布时间显示
        pub_disp = '-'
        try:
            pt = merchant.get('publish_time')
            if pt:
                pub_disp = str(pt)
        except Exception:
            pass

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"名称：{_short(name, 14)}", callback_data="merchant_edit_name"),
             InlineKeyboardButton(text=f"类型：{_short(type_txt, 10)}", callback_data="merchant_edit_type")],
            [InlineKeyboardButton(text=f"地区：{_short(city_name + '-' + district_name, 18)}", callback_data="merchant_edit_region"),
             InlineKeyboardButton(text="修改关键词", callback_data="merchant_edit_keywords")],
            [InlineKeyboardButton(text=f"P价格：{_short(p_price, 10)}", callback_data="merchant_edit_p"),
             InlineKeyboardButton(text=f"PP价格：{_short(pp_price, 10)}", callback_data="merchant_edit_pp")],
            [InlineKeyboardButton(text="修改描述", callback_data="merchant_edit_desc"),
             InlineKeyboardButton(text=channel_label, callback_data="merchant_edit_channel")],
            [InlineKeyboardButton(text=f"联系方式：{_short(merchant.get('contact_info') or '-', 16)}", callback_data="merchant_edit_contact")],
            [InlineKeyboardButton(text=f"发布时间：{_short(pub_disp, 16)}", callback_data="merchant_edit_publish_time")],
            [InlineKeyboardButton(text=("管理媒体（已有6张）" if media_count >= 6 else f"管理媒体（{media_count}/6）"), callback_data="merchant_edit_media")],
            [InlineKeyboardButton(text=submit_label, callback_data="merchant_submit_review")],
        ])
        sent = await message.answer(html_preview, reply_markup=kb, parse_mode='MarkdownV2')
        # 记录面板消息ID，便于后续编辑而不是追加
        try:
            state_name, data = await _fsm_db_profile.load_user_state(user_id)
            if state_name is None:
                await _fsm_db_profile.save_user_state(user_id, 'merchant_binding_flow', {'panel_message_id': sent.message_id})
            else:
                await _fsm_db_profile.update_state_data(user_id, {'panel_message_id': sent.message_id})
        except Exception:
            pass
        return

    # 2) 否则：展示用户成长资料
    profile = await user_manager.get_user_profile(user_id)
    if not profile:
        no_profile_text = await template_manager.get_template('user_no_profile')
        await message.answer(no_profile_text)
        return

    try:
        badges_list = json.loads(profile.get('badges', '[]'))
        badges_text = ' '.join(badges_list) if badges_list else '无'
    except (json.JSONDecodeError, TypeError):
        badges_text = await template_manager.get_template('data_invalid_format', '格式错误')

    profile_title = await template_manager.get_template('user_profile_title')
    level_text = await template_manager.get_template('user_profile_level')
    xp_text = await template_manager.get_template('user_profile_xp')
    points_text = await template_manager.get_template('user_profile_points')
    orders_text = await template_manager.get_template('user_profile_orders')
    badges_text_template = await template_manager.get_template('user_profile_badges')

    profile_card = f"""{profile_title}

{level_text.format(level_name=profile.get('level_name', '新手'))}
{xp_text.format(xp=profile.get('xp', 0))}
{points_text.format(points=profile.get('points', 0))}
{orders_text.format(order_count=profile.get('order_count', 0))}
{badges_text_template.format(badges_text=badges_text)}"""
    # 用户资料 + 功能按钮（含“我的出击记录”）
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗒️ 我的出击记录", callback_data="my_attack_records")]
    ])
    await message.answer(profile_card, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "my_attack_records")
async def my_attack_records_callback(callback: CallbackQuery):
    """用户端：查看最近20个已确认（非“尝试预约”）的出击记录。"""
    try:
        uid = callback.from_user.id
        # 最近20条，排除“尝试预约”
        sql = """
            SELECT 
                o.id as order_id,
                o.merchant_id,
                m.name as merchant_name,
                o.price,
                o.course_type,
                COALESCE(o.completion_time, o.created_at) as ts,
                r.report_post_url as u2m_link,
                mr.report_post_url as m2u_link
            FROM orders o
            JOIN merchants m ON m.id = o.merchant_id
            LEFT JOIN reviews r ON r.order_id = o.id
            LEFT JOIN merchant_reviews mr ON mr.order_id = o.id
            WHERE o.customer_user_id = ? AND o.status != '尝试预约'
            ORDER BY COALESCE(o.completion_time, o.created_at) DESC
            LIMIT 20
        """
        rows = await db_manager.fetch_all(sql, (uid,))
        if not rows:
            await callback.message.answer("暂无已确认的出击记录。")
            await callback.answer()
            return
        lines = ["🗒️ 最近出击记录（仅显示已确认）：\n"]
        for idx, row in enumerate(rows, 1):
            d = dict(row)
            price = d.get('price') or 0
            ct = (d.get('course_type') or '').upper()
            suffix = (ct.lower() if ct in ('P','PP') else '')
            ts = str(d.get('ts') or '')
            link = d.get('u2m_link') or d.get('m2u_link') or '-'
            line = f"{idx}. {ts}  订单#{d['order_id']}  {d.get('merchant_name','-')}  价格: ¥{price}{suffix}\n   报告: {link}"
            lines.append(line)
        text = "\n".join(lines)
        await callback.message.answer(text)
        await callback.answer()
    except Exception as e:
        logger.error(f"加载出击记录失败: {e}")
        await callback.message.answer("加载出击记录失败，请稍后再试。")
        await callback.answer()


@router.callback_query(F.data == "merchant_attack_records")
async def merchant_attack_records_callback(callback: CallbackQuery):
    """商户端：查看最近20个已确认（非“尝试预约”）的服务记录。"""
    try:
        # 校验商户身份
        merchant = await merchant_manager.get_merchant_by_chat_id(callback.from_user.id)
        if not merchant:
            await callback.answer("仅限商户使用", show_alert=True)
            return
        mid = merchant.get('id')
        sql = """
            SELECT 
                o.id as order_id,
                o.customer_user_id,
                u.username as customer_username,
                o.price,
                o.course_type,
                COALESCE(o.completion_time, o.created_at) as ts,
                r.report_post_url as u2m_link,
                mr.report_post_url as m2u_link
            FROM orders o
            LEFT JOIN users u ON u.user_id = o.customer_user_id
            LEFT JOIN reviews r ON r.order_id = o.id
            LEFT JOIN merchant_reviews mr ON mr.order_id = o.id
            WHERE o.merchant_id = ? AND o.status != '尝试预约'
            ORDER BY COALESCE(o.completion_time, o.created_at) DESC
            LIMIT 20
        """
        rows = await db_manager.fetch_all(sql, (mid,))
        if not rows:
            await callback.message.answer("暂无已确认的服务记录。")
            await callback.answer()
            return
        lines = ["🗒️ 最近服务记录（仅显示已确认）：\n"]
        for idx, row in enumerate(rows, 1):
            d = dict(row)
            price = d.get('price') or 0
            ct = (d.get('course_type') or '').upper()
            suffix = (ct.lower() if ct in ('P','PP') else '')
            ts = str(d.get('ts') or '')
            raw_un = d.get('customer_username')
            uname = f"@{raw_un}" if isinstance(raw_un, str) and raw_un else f"#{d.get('customer_user_id')}"
            link = d.get('u2m_link') or d.get('m2u_link') or '-'
            line = f"{idx}. {ts}  订单#{d['order_id']}  用户: {uname}  价格: ¥{price}{suffix}\n   报告: {link}"
            lines.append(line)
        text = "\n".join(lines)
        await callback.message.answer(text)
        await callback.answer()
    except Exception as e:
        logger.error(f"加载商户服务记录失败: {e}")
        await callback.message.answer("加载服务记录失败，请稍后再试。")
        await callback.answer()
