"""
商家交互处理器
处理商家注册流程，包括"上榜流程"关键词检测、绑定码验证和注册流程管理
"""

import logging
import json
import re
from typing import Optional, Dict, Any, List
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from typing import Optional
from aiogram.filters import StateFilter
# from aiogram.filters import Text  # Text filter removed in aiogram 3.x

# 导入项目模块
from config import MESSAGE_TEMPLATES, BUTTON_TEMPLATES, ADMIN_IDS, USE_NEW_BINDING_FLOW, QUICK_REGISTRATION_MODE
from utils.template_utils import get_template_async
from utils.telegram_helpers import safe_edit_message
from database.db_templates import template_manager
from utils.enums import MERCHANT_STATUS
from dialogs.states import MerchantStates, StateData
from database.db_connection import db_manager
from database.db_fsm import create_fsm_db_manager
from database.db_merchants import MerchantManager
from web.services.merchant_mgmt_service import MerchantMgmtService
from database.db_binding_codes import BindingCodesDatabase, binding_codes_db
from database.db_logs import ActivityLogsDatabase, ActionType
from database.db_media import media_db

# 配置日志
logger = logging.getLogger(__name__)

# 根据配置选择流程管理器
if USE_NEW_BINDING_FLOW:
    # 新版绑定流程不需要导入类，只需要路由器
    logger.info("使用新版绑定流程")
else:
    # 使用经典绑定流程管理器（向后兼容）
    logger.info("使用经典绑定流程管理器")

# 创建路由器
merchant_router = Router()
fsm_db = create_fsm_db_manager(db_manager)

# 兜底：全局管理员用户名获取（避免类方法缺失导致的运行时错误）
async def _get_admin_username_fallback(bot: Bot) -> str:
    try:
        if ADMIN_IDS:
            admin_id = ADMIN_IDS[0]
            try:
                admin_user = await bot.get_chat(admin_id)
                if getattr(admin_user, 'username', None):
                    return f"@{admin_user.username}"
            except Exception:
                pass
        return "@admin"
    except Exception:
        return "@admin"

# 记录用户的资料面板消息ID，作为 FSM 的补充，防止清理状态后丢失
PANEL_MESSAGE_IDS: dict[int, int] = {}

# ========== 通用：编辑提示消息的记录与清理 ==========
async def _push_prompt_message(state: FSMContext, message_id: int) -> None:
    try:
        data = await state.get_data()
        ids = list(data.get('prompt_message_ids') or [])
        ids.append(int(message_id))
        await state.update_data(prompt_message_ids=ids)
    except Exception:
        pass

async def _clear_prompt_messages(state: FSMContext, bot: Bot, chat_id: int) -> None:
    try:
        data = await state.get_data()
        ids = list(data.get('prompt_message_ids') or [])
        for mid in ids:
            try:
                await bot.delete_message(chat_id, mid)
            except Exception:
                pass
        await state.update_data(prompt_message_ids=[])
    except Exception:
        pass

# ===== 管理员通知：商家资料修改 ===== #
async def _notify_admin_change(bot: Bot, before: dict, after: dict, changed_fields: list[str]) -> None:
    """向管理员推送“商家信息更新”通知（轻量，不抛异常）。"""
    try:
        if not ADMIN_IDS:
            return
        mid = (after or {}).get('id') or (before or {}).get('id')
        name = (after or {}).get('name') or (before or {}).get('name') or '-'

        # 工具：城市/区县/关键词名
        async def _city_name(cid):
            if not cid:
                return '-'
            try:
                from database.db_regions import region_manager as _rm
                c = await _rm.get_city_by_id(int(cid))
                return (c or {}).get('name') or '-'
            except Exception:
                return '-'

        async def _district_name(did):
            if not did:
                return '-'
            try:
                from database.db_regions import region_manager as _rm
                d = await _rm.get_district_by_id(int(did))
                return (d or {}).get('name') or '-'
            except Exception:
                return '-'

        async def _keyword_names(merchant_id: int) -> str:
            try:
                rows = await db_manager.fetch_all(
                    "SELECT k.name FROM merchant_keywords mk JOIN keywords k ON k.id = mk.keyword_id WHERE mk.merchant_id = ? ORDER BY k.display_order, k.id",
                    (merchant_id,)
                )
                return ', '.join([r['name'] for r in rows]) or '无'
            except Exception:
                return '无'

        labels = {
            'name': '名称', 'contact_info': '联系方式', 'p_price': 'P价格', 'pp_price': 'PP价格',
            'custom_description': '服务描述', 'adv_sentence': '优势一句话', 'merchant_type': '商户类型',
            'city_id': '城市', 'district_id': '地区', 'publish_time': '发布时间', 'keywords': '关键词'
        }

        lines = [f"📝 商家信息更新通知", f"商家：{name}（ID {mid}）", ""]
        for key in changed_fields:
            if key == 'keywords':
                new_v = await _keyword_names(mid)
                lines.append(f"• {labels[key]}：{new_v}")
                continue
            ov = (before or {}).get(key)
            nv = (after or {}).get(key)
            if key == 'city_id':
                ov, nv = await _city_name(ov), await _city_name(nv)
            if key == 'district_id':
                ov, nv = await _district_name(ov), await _district_name(nv)
            lines.append(f"• {labels.get(key, key)}：{ov or '-'} → {nv or '-'}")

        text = "\n".join(lines)
        for aid in ADMIN_IDS:
            try:
                await bot.send_message(int(aid), text)
            except Exception:
                continue
    except Exception:
        pass

async def _push_user_message(state: FSMContext, message_id: int) -> None:
    """记录用户输入的消息ID，便于统一清理。"""
    try:
        data = await state.get_data()
        ids = list(data.get('user_message_ids') or [])
        ids.append(int(message_id))
        await state.update_data(user_message_ids=ids)
    except Exception:
        pass

async def _finalize_and_back_to_menu(state: FSMContext, bot: Bot, chat_id: int, message_obj: Message, user_id: int) -> None:
    """标准化收尾：删除所有提示与用户输入消息，返回单面板。"""
    try:
        # 删除提示消息
        await _clear_prompt_messages(state, bot, chat_id)
        # 删除用户输入消息
        try:
            data = await state.get_data()
            uids = list(data.get('user_message_ids') or [])
            for mid in uids:
                try:
                    await bot.delete_message(chat_id, int(mid))
                except Exception:
                    pass
            await state.update_data(user_message_ids=[])
        except Exception:
            pass
        # 清空状态，确保主面板不等待任何输入
        try:
            await state.clear()
        except Exception:
            pass
        # 回到面板（原位编辑）
        await show_profile_panel_like_user(message_obj, user_id, state)
    except Exception:
        pass

# 绑定流程配置
BINDING_FLOW_STEPS = {
    1: {
        "title": "👥 步骤 1/7: 选择商户类型",
        "description": "请选择您提供的服务类型：",
        "options": [
            {"text": "👩‍🏫 老师", "value": "teacher"},
            {"text": "🏢 商家", "value": "business"}
        ],
        "field": "merchant_type"
    },
    2: {
        "title": "🏙️ 步骤 2/7: 选择城市", 
        "description": "请选择您所在的城市：",
        "options": "dynamic_cities",  # 从cities表加载
        "field": "city"
    },
    3: {
        "title": "🌆 步骤 3/7: 选择地区",
        "description": "请选择您所在的地区：", 
        "options": "dynamic_districts",  # 从districts表加载
        "field": "district"
    },
    4: {
        "title": "💰 步骤 4/7: 输入P价格",
        "description": "请输入您的P价格（数字）：",
        "input_type": "text",
        "field": "p_price"
    },
    5: {
        "title": "💎 步骤 5/7: 输入PP价格", 
        "description": "请输入您的PP价格（数字）：",
        "input_type": "text",
        "field": "pp_price"
    },
    6: {
        "title": "📝 步骤 6/8: 一句话优势",
        "description": "请输入你的一句话优势（建议≤30字）：",
        "input_type": "text",
        "field": "adv_sentence"
    },
    7: {
        "title": "📢 步骤 7/8: 发布频道用户名",
        "description": "请输入你的频道用户名（例如 @yourchannel）：",
        "input_type": "text",
        "field": "channel_username"
    },
    8: {
        "title": "🏷️ 步骤 8/8: 选择关键词",
        "description": "请选择相关的服务关键词（可多选）：",
        "options": "dynamic_keywords",  # 从数据库加载
        "field": "keywords"
    },
    9: {
        "title": "🗓️ 步骤 9/9: 选择发布时间",
        "description": "请选择希望发布的日期与固定时间（由管理员配置）",
        "options": "dynamic_time_slots",  # 从posting_time_slots表加载
        "field": "publish_time_str"
    },
    10: {
        "title": "📷 步骤 10/10: 上传媒体",
        "description": "请直接发送照片或视频给我（最多6个）。完成后点击下方“完成上传”。",
        "field": "media_upload"
    }
}

class BindingFlowManager:
    """7步绑定流程管理器"""
    
    def __init__(self, bot):
        self.bot = bot
        self.province_db = None
        self.region_db = None 
        self.keyword_db = None
        
    async def _ensure_db_initialized(self):
        """确保数据库组件已初始化"""
        if self.province_db is None:
            # 使用数据库管理器
            from database.db_regions import region_manager
            from database.db_keywords import KeywordManager
            self.region_manager = region_manager
            self.keyword_db = KeywordManager()
            # 数据库组件已初始化
    
    async def load_dynamic_options(self, step_number: int, context: dict = None):
        """根据步骤加载动态选项数据"""
        await self._ensure_db_initialized()
        
        if step_number == 2:  # 城市选择
            try:
                cities = await self.region_manager.get_active_cities()
                return [{"text": c["name"], "value": str(c["id"])} for c in cities]
            except Exception as e:
                logger.error(f"加载城市数据失败: {e}")
                # 返回备用数据
                return [
                    {"text": "北京市", "value": "1"},
                    {"text": "上海市", "value": "2"},  
                    {"text": "广东省", "value": "3"}
                ]
        
        elif step_number == 3:  # 地区选择
            if context and context.get("city"):
                try:
                    city_id = int(context["city"])
                    districts = await self.region_manager.get_districts_by_city(city_id)
                    return [{"text": d["name"], "value": str(d["id"])} for d in districts]
                except Exception as e:
                    logger.error(f"加载地区数据失败: {e}")
            
            # 返回备用数据
            return [
                {"text": "市区", "value": "1"},
                {"text": "郊区", "value": "2"}
            ]
        
            
        elif step_number == 8:  # 关键词选择
            try:
                keywords = await self.keyword_db.get_all_keywords()
                return [{"text": k["name"], "value": str(k["id"])} for k in keywords]
            except Exception as e:
                logger.error(f"加载关键词数据失败: {e}")
                # 返回备用数据
                return [
                    {"text": "📚 教育", "value": "education"},
                    {"text": "💼 商务", "value": "business"},
                    {"text": "🏠 家政", "value": "housekeeping"},
                    {"text": "🎨 艺术", "value": "art"}
                ]
        elif step_number == 9:  # 固定时间槽
            try:
                from database.db_scheduling import posting_time_slots_db
                slots = await posting_time_slots_db.get_active_slots()
                return [{"text": s["time_str"], "value": s["time_str"]} for s in slots]
            except Exception as e:
                logger.error(f"加载时间槽失败: {e}")
                return []
        
        elif step_number == 9:  # 固定时间槽
            try:
                from database.db_scheduling import posting_time_slots_db
                slots = await posting_time_slots_db.get_active_slots()
                return [{"text": s["time_str"], "value": s["time_str"]} for s in slots]
            except Exception as e:
                logger.error(f"加载时间槽失败: {e}")
                return []
        
        return []
    
    async def show_step(self, callback: CallbackQuery, user_choices: dict, step_number: int):
        """显示指定步骤"""
        try:
            logger.info(f"显示步骤 {step_number}")
            step_config = BINDING_FLOW_STEPS[step_number]
            text = f"{step_config['title']}\n\n{step_config['description']}"
            
            # 检查是否为文本输入步骤
            if step_config.get("input_type") == "text":
                # 文本输入步骤，显示输入提示 + 上一步
                btn_rows = [[InlineKeyboardButton(text="⬅️ 返回菜单", callback_data="merchant_back_to_menu")]]
                keyboard = InlineKeyboardMarkup(inline_keyboard=btn_rows)
                await safe_edit_message(callback.message, text, reply_markup=keyboard)
                return step_config["field"]  # 返回需要设置的FSM状态字段
            
            # 按钮选择步骤
            buttons = []
            
            if step_number == 1:
                # 商户类型 - 使用配置中的选项
                for option in step_config["options"]:
                    buttons.append([InlineKeyboardButton(
                        text=option["text"], 
                        callback_data=f"binding_step1_{option['value']}"
                    )])
            
            elif step_number in [2, 3, 8, 9, 10]:
                # 动态数据步骤
                options = await self.load_dynamic_options(step_number, user_choices)
                
                if step_number == 8:
                    # 关键词多选
                    current_keywords = user_choices.get("keywords", [])
                    for option in options:
                        prefix = "✅ " if option["value"] in current_keywords else ""
                        buttons.append([InlineKeyboardButton(
                            text=f"{prefix}{option['text']}",
                            callback_data=f"binding_step8_{option['value']}"
                        )])
                    # 进入“选择发布时间”（统一路径）
                    buttons.append([InlineKeyboardButton(text="➡️ 选择发布时间", callback_data="binding_confirm_step9")])
                    # 关键词保存（用于资料编辑，可选）
                    buttons.append([InlineKeyboardButton(text="💾 保存关键词", callback_data="binding_keywords_save")])
                elif step_number == 9:
                    # 先选择最近5天日期，再选择管理员配置的时间
                    from datetime import datetime, timedelta
                    # 使用中文星期显示，避免 %a 在不同系统上显示英文缩写
                    def _weekday_cn(dt: datetime) -> str:
                        names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
                        try:
                            return names[dt.weekday()]
                        except Exception:
                            return ''
                    days = []
                    for i in range(0, 5):
                        d = datetime.now() + timedelta(days=i)
                        days.append({
                            "text": f"{d.strftime('%m-%d')} ({_weekday_cn(d)})",
                            "value": d.strftime("%Y-%m-%d")
                        })
                    # 日期按钮
                    for d in days:
                        prefix = "✅ " if user_choices.get('publish_date') == d['value'] else ""
                        buttons.append([InlineKeyboardButton(text=f"{prefix}{d['text']}", callback_data=f"binding_pickdate_{d['value']}")])
                    # 时间槽
                    if user_choices.get('publish_date') and options:
                        buttons.append([InlineKeyboardButton(text="🔴 请选择具体时间", callback_data="noop")])
                        # 查询该日期已被占用的时间槽
                        try:
                            from database.db_merchants import MerchantManager as _MM
                            occupied = set(await _MM.get_occupied_time_slots_for_date(user_choices.get('publish_date') or ''))
                        except Exception:
                            occupied = set()
                        for option in options:
                            time_val = option['value']
                            sel = '✅ ' if user_choices.get('publish_time_str') == time_val else ''
                            if time_val in occupied and not sel:
                                # 已被他人占用且不是自己当前已选，标记并禁用
                                label = f"⛔ {option['text']}（已被选）"
                                buttons.append([InlineKeyboardButton(text=label, callback_data="noop")])
                            else:
                                buttons.append([InlineKeyboardButton(text=f"{sel}{option['text']}", callback_data=f"binding_step9_{time_val}")])
                    # 不在此处重复添加返回按钮，统一在下方追加
                elif step_number == 10:
                    # 上传媒体说明 + 完成按钮 + 返回菜单
                    # 统计已上传数量
                    try:
                        merchant = await MerchantManager.get_merchant_by_chat_id(callback.from_user.id)
                        count = 0
                        if merchant:
                            files = await media_db.get_media_by_merchant_id(merchant['id'])
                            count = len(files or [])
                    except Exception:
                        count = 0
                    text += f"\n\n当前已上传：{count}/6\n直接发送照片或视频即可（最多6个）。"
                    buttons.append([InlineKeyboardButton(text="✅ 完成上传", callback_data="binding_media_done")])
                else:
                    # 普通单选（步骤2,3）
                    for option in options:
                        buttons.append([InlineKeyboardButton(
                            text=option["text"], 
                            callback_data=f"binding_step{step_number}_{option['value']}"
                        )])
            
            # 添加返回菜单按钮（统一行为）
            buttons.append([InlineKeyboardButton(text="⬅️ 返回菜单", callback_data="merchant_back_to_menu")])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await safe_edit_message(callback.message, text, reply_markup=keyboard)
            return None
            
        except Exception as e:
            logger.error(f"显示步骤 {step_number} 失败: {e}")
            raise

class MerchantHandler:
    """商家交互处理器类"""
    
    def __init__(self, bot: Bot):
        """
        初始化商家处理器
        
        Args:
            bot: Telegram Bot实例
        """
        self.bot = bot
        # 使用重构后的绑定流程管理器
        self.binding_flow_manager = BindingFlowManager(bot)
        self.flow_state_name = "merchant_binding_flow"

    async def _persist_flow(self, user_id: int, data: Dict[str, Any]) -> None:
        try:
            await fsm_db.save_user_state(user_id, self.flow_state_name, data)
        except Exception as e:
            logger.warning(f"持久化绑定流程状态失败: {e}")

    async def _load_flow(self, user_id: int) -> Dict[str, Any]:
        try:
            _, data = await fsm_db.load_user_state(user_id)
            return data or {}
        except Exception as e:
            logger.warning(f"加载绑定流程状态失败: {e}")
            return {}

    async def _clear_flow(self, user_id: int) -> None:
        try:
            await fsm_db.clear_user_state(user_id)
        except Exception as e:
            logger.warning(f"清理绑定流程状态失败: {e}")

    async def _render_progress_overview(self, message_or_cb, user_choices: Dict[str, Any], current_step: int, state: Optional[FSMContext] = None):
        """渲染进度总览，提供跳转按钮。"""
        step_titles = {
            1: "👥 选择商户类型",
            2: "🏙️ 选择城市",
            3: "🌆 选择地区",
            4: "💰 输入P价格",
            5: "💎 输入PP价格",
            6: "📝 一句话优势",
            7: "📢 频道用户名",
            8: "🏷️ 选择关键词",
            9: "🗓️ 选择发布时间",
        }
        builder = InlineKeyboardBuilder()
        for i in range(1, 10):
            field = BINDING_FLOW_STEPS[i].get('field')
            filled = False
            if field == 'keywords':
                filled = bool(user_choices.get(field))
            elif field in ("p_price", "pp_price", "custom_description", "adv_sentence", "merchant_type", "city", "district"):
                filled = str(user_choices.get(field, "")).strip() != ""
            elif field == 'publish_time_str':
                filled = bool(user_choices.get('publish_date') and user_choices.get('publish_time_str'))
            text_prefix = "✅" if filled else ("➡️" if i == current_step else "•")
            builder.button(text=f"{text_prefix} 步骤{i}: {step_titles[i]}", callback_data=f"binding_goto_{i}")

        preview_btn_text = await template_manager.get_template('binding_btn_preview', '📋 预览信息')
        builder.button(text=preview_btn_text, callback_data="binding_preview")
        # 追加媒体上传入口
        builder.button(text="🖼️ 上传媒体(最多6)", callback_data="merchant_edit_media")

        builder.adjust(1)
        keyboard = builder.as_markup()
        # 统计已上传媒体数量
        media_count = 0
        try:
            merchant = await MerchantManager.get_merchant_by_chat_id(message_or_cb.from_user.id if hasattr(message_or_cb, 'from_user') else message_or_cb.message.from_user.id)
            if merchant:
                media_count = len(await media_db.get_media_by_merchant_id(merchant['id']))
        except Exception:
            media_count = 0

        overview_text = "📌 资料填写进度总览\n\n"
        overview_text += f"当前进度：第 {current_step}/8 步\n"
        overview_text += f"媒体上传：{media_count}/6（点击下方按钮上传）\n"
        overview_text += "可点击任一步骤进行修改或继续。"

        # 同步数据到FSM，以便后续回调可读取
        try:
            if state is not None:
                await state.update_data(user_choices=user_choices, current_step=current_step)
        except Exception:
            pass

        # 支持 Message 或 Callback 的统一发送
        if isinstance(message_or_cb, Message):
            await message_or_cb.answer(overview_text, reply_markup=keyboard)
        else:
            await safe_edit_message(message_or_cb.message, overview_text, reply_markup=keyboard)

    async def _update_merchant_draft(self, user_id: int, changes: Dict[str, Any]) -> None:
        """将未提交的信息实时写入 merchants 表，便于Web端动态展示。"""
        try:
            existing = await MerchantManager.get_merchant_by_chat_id(user_id)
            if not existing:
                return
            merchant_id = existing.get('id')
            if not merchant_id:
                return
            await MerchantManager.update_merchant(merchant_id, changes)
            # 若已发布且有post_url，尝试同步频道caption（用于草稿实时写入）
            try:
                m2 = await MerchantManager.get_merchant_by_id(merchant_id)
                if m2 and str(m2.get('status')) == 'published' and m2.get('post_url'):
                    await _refresh_post(merchant_id)
            except Exception:
                pass
            # 若已发布且有post_url，尝试同步频道caption
            try:
                m2 = await MerchantManager.get_merchant_by_id(merchant_id)
                if m2 and str(m2.get('status')) == 'published' and m2.get('post_url'):
                    await _refresh_post(merchant_id)
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"更新商户草稿信息失败: {e}")
    
    async def handle_registration_trigger(self, message: Message, state: FSMContext):
        """
        处理"上榜流程"关键词触发的注册流程
        
        Args:
            message: 用户消息
            state: FSM状态上下文
        """
        try:
            user_id = message.from_user.id
            
            # 检查用户是否已经是注册商家
            existing_merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
            if existing_merchant:
                if QUICK_REGISTRATION_MODE:
                    # 快速注册模式：用户已有记录就告诉绑定成功，管理员在后台操作
                    quick_bind_text = await template_manager.get_template('quick_bind_success')
                    await message.answer(quick_bind_text)
                else:
                    # 传统模式：根据状态给出不同提示
                    status = existing_merchant.get('status', 'unknown')
                    # 标准化状态值
                    normalized_status = MERCHANT_STATUS.normalize(status)
                    
                    if normalized_status == MERCHANT_STATUS.PENDING_SUBMISSION.value:
                        # 新交互：直接展示“我的资料”同款面板，用户按需逐项完善
                        try:
                            await show_profile_panel_like_user(message, user_id, state)
                        except Exception:
                            pass
                        return
                    elif MERCHANT_STATUS.is_active_status(normalized_status):
                        status_display = MERCHANT_STATUS.get_display_name(normalized_status)
                        merchant_status_text = await template_manager.get_template('merchant_already_registered')
                        await message.answer(merchant_status_text.format(status_display=status_display))
                    elif normalized_status == MERCHANT_STATUS.EXPIRED.value:
                        suspended_text = await template_manager.get_template('merchant_account_suspended')
                        await message.answer(suspended_text)
                    else:
                        pending_text = await template_manager.get_template('merchant_registration_pending')
                        await message.answer(pending_text)
                return
            
            # 记录注册请求日志
            await ActivityLogsDatabase.log_user_interaction(
                user_id=user_id,
                action=ActionType.USER_INTERACTION.value,
                details={
                    "action": "registration_trigger",
                    "username": message.from_user.username,
                    "full_name": message.from_user.full_name
                }
            )
            
            # 获取管理员用户名（用于联系信息）
            # 使用全局兜底函数，避免类方法缺失导致异常
            try:
                admin_username = await self._get_admin_username()  # 优先使用类方法（如存在）
            except Exception:
                admin_username = await _get_admin_username_fallback(self.bot)
            
            # 发送绑定码请求消息（强制从数据库获取最新模板）
            try:
                binding_request_text = await get_template_async(
                    "binding_code_request",
                    admin_username=admin_username or "管理员"
                )
                # 使用普通文本模式发送，避免Markdown解析错误
                await message.answer(binding_request_text, parse_mode=None)
            except Exception as e:
                logger.error(f"发送绑定码请求消息失败: {e}")
                # 发送简化的错误恢复消息
                fallback_text = await template_manager.get_template(
                    'binding_code_request',
                    '🔑 要注册为商户，您需要一个绑定码。请联系管理员获取您的绑定码。'
                )
                await message.answer(fallback_text, parse_mode=None)
            
            # 设置状态为等待绑定码输入
            await state.set_state(MerchantStates.entering_binding_code)
            state_data = StateData()
            state_data.set("registration_started", True)
            state_data.set("user_info", {
                "user_id": user_id,
                "username": message.from_user.username,
                "full_name": message.from_user.full_name
            })
            await state.set_data(state_data.data)
            
            # 发送绑定码输入提示
            prompt_text = await get_template_async("binding_code_prompt")
            await message.answer(prompt_text)
            # 持久化起始状态
            await self._persist_flow(user_id, {"user_choices": {}, "current_step": 0})
            
        except Exception as e:
            logger.error(f"处理注册触发失败: {e}", exc_info=True)
            error_text = await get_template_async("error_general")
            await message.answer(error_text)
    
    async def handle_binding_code_input(self, message: Message, state: FSMContext):
        """
        处理绑定码输入
        
        Args:
            message: 用户消息
            state: FSM状态上下文
        """
        try:
            user_id = message.from_user.id
            binding_code = message.text.strip().upper()
            
            # 验证绑定码格式（8位大写字母和数字）
            if not re.match(r'^[A-Z0-9]{8}$', binding_code):
                # 必须使用动态模板，不准降级
                invalid_format_text = await get_template_async("invalid_binding_code")
                invalid_text = await template_manager.get_template('invalid_binding_code')
                await message.answer(invalid_text, parse_mode=None)
                logger.info(f"用户 {user_id} 输入了无效格式的绑定码: {binding_code}")
                # 清除状态，允许用户退出验证模式
                await state.clear()
                return
            
            # 删除用户输入的绑定码消息（安全考虑）
            try:
                await message.delete()
            except Exception:
                pass
            
            # 一次性验证并处理绑定码
            result = await BindingCodesDatabase.validate_and_use_binding_code(binding_code, user_id)
            
            if not result['success']:
                error_prefix = await template_manager.get_template('error_system', '❌')
                await message.answer(f"{error_prefix} {result['message']}")
                # 记录失败日志
                await ActivityLogsDatabase.log_user_interaction(
                    user_id=user_id,
                    action=ActionType.ERROR_EVENT.value,
                    details={
                        "action": "binding_code_failed",
                        "code": binding_code,
                        "error": result['message']
                    }
                )
                # 清除状态，允许用户退出验证模式
                await state.clear()
                return
            
            # 成功：立即通过检测器获取并写入 Telegram 用户信息（DB为唯一真源）
            try:
                merchant_id = result.get('merchant_id')
                if merchant_id:
                    await MerchantMgmtService.refresh_telegram_user_info(merchant_id)
            except Exception as _e:
                logger.warning(f"自动检测用户信息失败: { _e }")

            # 成功后改为直接进入“我的资料”同款面板，统一交互
            await message.answer(result['message'])
            try:
                await show_profile_panel_like_user(message, user_id, state)
            except Exception as flow_e:
                logger.error(f"展示资料面板失败: {flow_e}")
            finally:
                try:
                    data = await state.get_data(); panel_id = data.get('panel_message_id')
                    await state.clear()
                    if panel_id:
                        await state.update_data(panel_message_id=panel_id)
                except Exception:
                    pass
            
            # 记录成功日志
                await ActivityLogsDatabase.log_user_interaction(
                    user_id=user_id,
                    action=ActionType.MERCHANT_REGISTRATION.value,
                    details={
                        "action": "quick_registration_success",
                        "merchant_id": result['merchant_id'],
                        "code": binding_code
                    }
                )
            
            logger.info(f"用户 {user_id} 快速注册成功，商户ID: {result['merchant_id']}")
            
            
        except Exception as e:
            logger.error(f"处理绑定码输入失败: {e}", exc_info=True)
            system_error_text = await template_manager.get_template('error_general')
            await message.answer(system_error_text)

async def show_profile_panel_like_user(message: Message, user_id: int, state: FSMContext | None = None) -> int | None:
    """展示与“/start → 我的资料”相同的资料面板与交互。
    若提供 state，则优先编辑已记录的面板消息，避免多条菜单叠加。
    返回用于展示面板的 message_id。
    """
    try:
        from database.db_merchants import MerchantManager as _MM
        from database.db_regions import region_manager as _region
        from config import DEEPLINK_BOT_USERNAME as _BOTU
        from utils.caption_renderer import render_channel_caption_md as _render_md
        from services.review_publish_service import refresh_merchant_post_reviews as _refresh_post

        merchant = await _MM.get_merchant_by_chat_id(user_id)
        if not merchant:
            await message.answer("未找到商户信息，请重试")
            return

        name = merchant.get('name') or (message.from_user.full_name or '-')
        p_price = merchant.get('p_price') or '-'
        pp_price = merchant.get('pp_price') or '-'
        channel = merchant.get('channel_chat_id') or '-'

        city_name = '-'
        district_name = '-'
        try:
            district_id = merchant.get('district_id')
            if district_id:
                d = await _region.get_district_by_id(int(district_id))
                if d:
                    district_name = d.get('name') or '-'
                    city_id = d.get('city_id')
                    if city_id:
                        c = await _region.get_city_by_id(int(city_id))
                        if c:
                            city_name = c.get('name') or '-'
        except Exception:
            pass

        md = await _render_md({
            **merchant,
            'name': name,
            'p_price': p_price,
            'pp_price': pp_price,
            'city_name': city_name,
            'district_name': district_name,
            'channel_chat_id': channel,
        }, (_BOTU or '').lstrip('@'))

        def _short(s: str, n: int = 18) -> str:
            s = str(s or '-')
            return s if len(s) <= n else (s[: n - 1] + '…')

        tmap = {'teacher': '老师', 'business': '商家'}
        type_txt = tmap.get((merchant.get('merchant_type') or '').lower(), '-')
        channel_val = merchant.get('channel_chat_id') or ''
        channel_label = f"修改频道：{_short(channel_val, 16)}" if channel_val else "修改频道"

        # 媒体数量
        media_count = 0
        try:
            from database.db_media import media_db as _media_db
            existing_media = await _media_db.get_media_by_merchant_id(merchant['id'])
            media_count = len(existing_media or [])
        except Exception:
            media_count = 0

        # 只在已审核/已发布时禁用提交按钮；待审核也允许“重新提交”
        submit_label = "✅ 提交审核" if (merchant.get('status') not in ("approved","published")) else "已提交审核"

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
            [InlineKeyboardButton(text="修改一句话优势", callback_data="merchant_edit_desc"),
             InlineKeyboardButton(text=channel_label, callback_data="merchant_edit_channel")],
            [InlineKeyboardButton(text=f"联系方式：{_short(merchant.get('contact_info') or '-', 16)}", callback_data="merchant_edit_contact")],
            [InlineKeyboardButton(text=f"发布时间：{_short(pub_disp, 16)}", callback_data="merchant_edit_publish_time")],
            [InlineKeyboardButton(text=("管理媒体（已有6张）" if media_count >= 6 else f"管理媒体（{media_count}/6）"), callback_data="merchant_edit_media")],
            [InlineKeyboardButton(text=submit_label, callback_data="merchant_submit_review")],
        ])
        # 优先编辑已有面板消息
        panel_id = None
        try:
            if state is not None:
                data = await state.get_data()
                panel_id = data.get('panel_message_id')
        except Exception:
            panel_id = None
        # FSM持久化补位（来自其他处理器例如 /start→我的资料 首次打开时写入）
        if not panel_id:
            try:
                _, persisted = await fsm_db.load_user_state(user_id)
                if isinstance(persisted, dict):
                    panel_id = persisted.get('panel_message_id') or panel_id
            except Exception:
                pass
        # 全局内存补位
        if not panel_id:
            panel_id = PANEL_MESSAGE_IDS.get(user_id)

        sent_msg = None
        if panel_id:
            try:
                await message.bot.edit_message_text(md, chat_id=message.chat.id, message_id=int(panel_id), reply_markup=kb, parse_mode='MarkdownV2')
            except Exception:
                sent_msg = await message.answer(md, reply_markup=kb, parse_mode='MarkdownV2')
                panel_id = sent_msg.message_id
        else:
            sent_msg = await message.answer(md, reply_markup=kb, parse_mode='MarkdownV2')
            panel_id = sent_msg.message_id

        if panel_id:
            # 写回到FSM（若有）与全局映射
            try:
                if state is not None:
                    await state.update_data(panel_message_id=int(panel_id))
                else:
                    # 在没有传入state时，也把面板ID写入持久化FSM，便于后续读取
                    _st, _data = await fsm_db.load_user_state(user_id)
                    new_data = (_data or {})
                    new_data['panel_message_id'] = int(panel_id)
                    await fsm_db.save_user_state(user_id, 'merchant_binding_flow', new_data)
            except Exception:
                pass
        if panel_id:
            PANEL_MESSAGE_IDS[user_id] = int(panel_id)
        return panel_id
    except Exception as e:
        logger.error(f"show_profile_panel_like_user 失败: {e}")
        await message.answer("打开资料面板失败，请稍后重试")
        return None
    
    async def handle_binding_flow_callback(self, callback: CallbackQuery, state: FSMContext):
        """
        处理绑定流程中的回调查询
        
        Args:
            callback: 回调查询对象
            state: FSM状态上下文
        """
        try:
            # 将回调处理委托给绑定流程管理器
            await self.binding_flow_manager.handle_callback(callback, state)
            
        except Exception as e:
            logger.error(f"处理绑定流程回调失败: {e}", exc_info=True)
            processing_failed_text = await template_manager.get_template('binding_callback_failed')
            await callback.answer(processing_failed_text, show_alert=True)
    
    async def handle_binding_completion(self, user_id: int, merchant_data: Dict[str, Any], state: FSMContext = None):
        """
        处理绑定流程完成
        
        Args:
            user_id: 用户ID
            merchant_data: 商家数据
            state: FSM状态上下文（用于清理状态）
        """
        try:
            # 创建商家记录
            merchant_id = await MerchantManager.create_merchant(merchant_data)
            
            if merchant_id:
                # 标记绑定码为已使用并关联商户
                binding_code = merchant_data.get("binding_code")
                if binding_code:
                    try:
                        success = await BindingCodesDatabase.use_binding_code(binding_code, merchant_id)
                        if not success:
                            logger.error(f"标记绑定码为已使用失败: {binding_code}")
                    except Exception as e:
                        logger.error(f"使用绑定码失败: {e}")
                
                # 记录商家注册完成日志
                await ActivityLogsDatabase.log_user_interaction(
                    user_id=user_id,
                    action=ActionType.MERCHANT_REGISTRATION.value,
                    details={
                        "merchant_id": merchant_id,
                        "name": merchant_data.get("name"),
                        "merchant_type": merchant_data.get("merchant_type"),
                        "city_id": merchant_data.get("city_id"),
                        "district_id": merchant_data.get("district_id")
                    }
                )
                
                # 清理FSM状态 - 重要！防止用户继续处于绑定流程中
                if state:
                    await state.clear()
                    logger.info(f"用户 {user_id} 的FSM状态已清理")
                
                # 发送成功消息
                success_text = await get_template_async("binding_success")
                await self.bot.send_message(user_id, success_text)
                
                # 通知管理员新商家注册
                await self._notify_admin_new_merchant(merchant_id, merchant_data)
                
                logger.info(f"商家注册成功: 用户 {user_id}, 商家ID {merchant_id}")
            else:
                registration_failed_text = await template_manager.get_template('error_general', '注册失败，请联系管理员。')
                await self.bot.send_message(user_id, registration_failed_text)
                logger.error(f"创建商家记录失败: 用户 {user_id}")
            
        except Exception as e:
            logger.error(f"处理绑定完成失败: {e}", exc_info=True)
            error_text = await get_template_async("error_general")
            await self.bot.send_message(user_id, error_text)
    
    async def handle_merchant_message(self, message: Message, state: FSMContext):
        """
        处理商家的一般消息
        
        Args:
            message: 消息对象
            state: FSM状态上下文
        """
        try:
            current_state = await state.get_state()
            
            # 根据当前状态处理消息
            if current_state == MerchantStates.entering_binding_code:
                await self.handle_binding_code_input(message, state)
            elif current_state in [
                MerchantStates.selecting_region,
                MerchantStates.selecting_category,
                MerchantStates.entering_name,
                MerchantStates.entering_contact_info,
                MerchantStates.confirming_profile
            ]:
                # 绑定流程中的文本输入处理
                await self.binding_flow_manager.handle_text_input(message, state)
            else:
                # 默认消息处理
                await self._handle_default_merchant_message(message, state)
                
        except Exception as e:
            logger.error(f"处理商家消息失败: {e}", exc_info=True)
            error_text = await get_template_async("error_general")
            await message.answer(error_text)
    
    async def _get_admin_username(self) -> str:
        """
        获取管理员用户名
        
        Returns:
            管理员用户名字符串
        """
        try:
            if ADMIN_IDS:
                # 尝试获取第一个管理员的用户名
                admin_id = ADMIN_IDS[0]
                try:
                    admin_user = await self.bot.get_chat(admin_id)
                    if admin_user.username:
                        return f"@{admin_user.username}"
                except Exception:
                    pass
            
            return "@admin"  # 默认返回值
            
        except Exception as e:
            logger.error(f"获取管理员用户名失败: {e}")
            return "@admin"
    
    async def _notify_admin_new_merchant(self, merchant_id: int, merchant_data: Dict[str, Any]):
        """
        通知管理员有新商家注册
        
        Args:
            merchant_id: 商家ID
            merchant_data: 商家数据
        """
        try:
            city_display = '-'
            district_display = '-'
            try:
                from database.db_regions import region_manager as _region_mgr
                if str(merchant_data.get('city_id', '')).isdigit():
                    c = await _region_mgr.get_city_by_id(int(merchant_data['city_id']))
                    if c:
                        city_display = c.get('name') or '-'
                if str(merchant_data.get('district_id', '')).isdigit():
                    d = await _region_mgr.get_district_by_id(int(merchant_data['district_id']))
                    if d:
                        district_display = d.get('name') or '-'
            except Exception:
                pass

            notification_text = f"""
🎉 新商家注册

👤 商家信息:
• ID: {merchant_id}
• 名称: {merchant_data.get('name', '未知')}
• 地区: {city_display} - {district_display}
• 类型: {merchant_data.get('merchant_type', 'teacher')}
• 联系方式: {merchant_data.get('contact_info', '未提供')}

⏰ 注册时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            # 发送给所有管理员
            for admin_id in ADMIN_IDS:
                try:
                    await self.bot.send_message(admin_id, notification_text)
                except Exception as e:
                    logger.warning(f"向管理员 {admin_id} 发送通知失败: {e}")
            
        except Exception as e:
            logger.error(f"通知管理员失败: {e}")
    
    async def handle_merchant_panel(self, message: Message, state: FSMContext):
        """
        处理商家面板命令
        
        Args:
            message: 消息对象
            state: FSM状态上下文
        """
        try:
            user_id = message.from_user.id
            
            # 获取商户信息
            merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
            if not merchant:
                not_registered_text = await template_manager.get_template('merchant_not_registered')
                await message.answer(not_registered_text)
                return
            
            # 标准化状态
            status = merchant.get('status', 'unknown')
            normalized_status = MERCHANT_STATUS.normalize(status)
            status_display = MERCHANT_STATUS.get_display_name(normalized_status)
            
            # 构建面板信息
            merchant_id = merchant['id']
            name = merchant.get('name', '待完善')
            created_at = merchant.get('created_at', '未知')
            
            panel_title = await template_manager.get_template('merchant_panel_title')
            basic_info = await template_manager.get_template('merchant_panel_basic_info')
            status_desc = await template_manager.get_template('merchant_panel_status_desc')
            
            panel_text = f"""{panel_title}

{basic_info}
• 商户ID: {merchant_id}
• 名称: {name}
• 状态: {status_display}
• 注册时间: {created_at[:19] if created_at else '未知'}

{status_desc}
"""
            
            # 根据状态添加不同的说明和操作选项
            if normalized_status == MERCHANT_STATUS.PENDING_SUBMISSION.value:
                pending_submission_text = await template_manager.get_template('merchant_panel_status_pending_submission')
                panel_text += pending_submission_text
            elif normalized_status == MERCHANT_STATUS.PENDING_APPROVAL.value:
                pending_approval_text = await template_manager.get_template('merchant_panel_status_pending_approval')
                panel_text += pending_approval_text
            elif normalized_status == MERCHANT_STATUS.APPROVED.value:
                approved_text = await template_manager.get_template('merchant_panel_status_approved')
                panel_text += approved_text
            elif normalized_status == MERCHANT_STATUS.PUBLISHED.value:
                published_text = await template_manager.get_template('merchant_panel_status_published')
                panel_text += published_text
            elif normalized_status == MERCHANT_STATUS.EXPIRED.value:
                expired_text = await template_manager.get_template('merchant_panel_status_expired')
                panel_text += expired_text
            else:
                panel_text += f"• 状态：{status_display}"
            
            await message.answer(panel_text, parse_mode=None)
            
        except Exception as e:
            logger.error(f"处理商户面板失败: {e}", exc_info=True)
            panel_error_text = await template_manager.get_template('merchant_panel_error')
            await message.answer(panel_error_text)

    async def _handle_default_merchant_message(self, message: Message, state: FSMContext):
        """
        处理商家的默认消息
        
        Args:
            message: 消息对象
            state: FSM状态上下文
        """
        # 检查是否是注册触发关键词
        if message.text and "上榜流程" in message.text:
            await self.handle_registration_trigger(message, state)
        else:
            # 提供帮助信息
            welcome = await template_manager.get_template('merchant_help_welcome')
            register_info = await template_manager.get_template('merchant_help_register')
            existing_info = await template_manager.get_template('merchant_help_existing')
            # 兼容旧模板文案：将“/panel/商户面板”引导改为点击“我的资料”
            try:
                existing_info = (existing_info or '').replace('/panel', '点击“我的资料”').replace('商户面板', '“我的资料”')
            except Exception:
                pass
            
            help_text = f"""{welcome}

{register_info}

{existing_info}
            """
            await message.answer(help_text)


# 创建处理器实例（需要在bot初始化后创建）
merchant_handler = None

def init_merchant_handler(bot: Bot):
    """
    初始化商家处理器
    
    Args:
        bot: Telegram Bot实例
    """
    global merchant_handler
    merchant_handler = MerchantHandler(bot)

# ====== 商家“我的资料”快速编辑入口 ======
@merchant_router.callback_query(F.data == "merchant_edit_p")
async def merchant_edit_p(callback: CallbackQuery, state: FSMContext):
    try:
        await state.update_data(editing_mode="profile")
        await state.set_state(MerchantStates.entering_p_price)
        m = await callback.message.answer("请输入新的 P 价格（数字，例如 88 或 88.00）：", parse_mode=None)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入P价格编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_edit_pp")
async def merchant_edit_pp(callback: CallbackQuery, state: FSMContext):
    try:
        await state.update_data(editing_mode="profile")
        await state.set_state(MerchantStates.entering_pp_price)
        m = await callback.message.answer("请输入新的 PP 价格（数字，例如 188 或 188.00）：", parse_mode=None)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入PP价格编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_edit_desc")
async def merchant_edit_desc(callback: CallbackQuery, state: FSMContext):
    try:
        await state.update_data(editing_mode="profile")
        # 将“修改描述”入口替换为编辑“一句话优势”
        await state.set_state(MerchantStates.entering_adv_sentence)
        m = await callback.message.answer("请输入新的优势一句话（建议≤30字）：", parse_mode=None)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入描述编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_edit_channel")
async def merchant_edit_channel(callback: CallbackQuery, state: FSMContext):
    try:
        await state.update_data(editing_mode="profile")
        await state.set_state(MerchantStates.entering_channel_username)
        m = await callback.message.answer("请输入新的频道用户名（@yourchannel 或 https://t.me/yourchannel）：", parse_mode=None)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入频道编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_edit_name")
async def merchant_edit_name(callback: CallbackQuery, state: FSMContext):
    try:
        await state.update_data(editing_mode="profile")
        await state.set_state(MerchantStates.entering_name)
        m = await callback.message.answer("请输入新的商户名称：", parse_mode=None)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入名称编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_edit_contact")
async def merchant_edit_contact(callback: CallbackQuery, state: FSMContext):
    try:
        await state.update_data(editing_mode="profile")
        await state.set_state(MerchantStates.entering_contact_info)
        m = await callback.message.answer("请输入新的联系方式（可填 @username 或其他说明）：", parse_mode=None)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入联系方式编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_edit_type")
async def merchant_edit_type(callback: CallbackQuery, state: FSMContext):
    try:
        await state.update_data(editing_mode="profile")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👩‍🏫 老师", callback_data="binding_step1_teacher")],
            [InlineKeyboardButton(text="🏢 商家", callback_data="binding_step1_business")],
        ])
        m = await callback.message.answer("请选择新的商户类型：", reply_markup=kb)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入类型编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_edit_region")
async def merchant_edit_region(callback: CallbackQuery, state: FSMContext):
    """进入地区编辑：先选城市，再选区县。"""
    try:
        await state.update_data(editing_mode="profile")
        # 动态加载城市（不进入7步流程，不显示步骤文案）
        options = await merchant_handler.binding_flow_manager.load_dynamic_options(2, {}) if merchant_handler else []
        buttons = [[InlineKeyboardButton(text=o["text"], callback_data=f"edit_region_city_{o['value']}")] for o in options]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        m = await callback.message.answer("📌 选择城市：", reply_markup=kb)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入地区编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data.startswith("edit_region_city_"))
async def merchant_edit_region_pick_city(callback: CallbackQuery, state: FSMContext):
    try:
        city_id = int(callback.data.replace("edit_region_city_", ""))
        await state.update_data(editing_mode="profile", edit_city_id=city_id)
        # 加载该城市下的区县
        from database.db_regions import region_manager
        districts = await region_manager.get_districts_by_city(city_id)
        if not districts:
            await callback.answer("该城市暂无可选地区", show_alert=True)
            return
        buttons = [[InlineKeyboardButton(text=d['name'], callback_data=f"edit_region_district_{d['id']}")] for d in districts]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons + [[InlineKeyboardButton(text="⬅️ 返回城市", callback_data="merchant_edit_region")]])
        m = await callback.message.answer("📌 选择区域：", reply_markup=kb)
        await _push_prompt_message(state, m.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"选择城市失败: {e}")
        await callback.answer("操作失败", show_alert=True)

@merchant_router.callback_query(F.data.startswith("edit_region_district_"))
async def merchant_edit_region_pick_district(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        did = int(callback.data.replace("edit_region_district_", ""))
        data = await state.get_data()
        cid = int(data.get('edit_city_id') or 0)
        # 容错：若未存城市，从区县反查
        if not cid:
            from database.db_regions import region_manager
            d = await region_manager.get_district_by_id(did)
            cid = int(d.get('city_id') or 0) if d else 0
        merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
        if not merchant:
            await callback.answer("未找到商户信息", show_alert=True)
            return
        updates = {'city_id': cid or None, 'district_id': did}
        await MerchantManager.update_merchant(merchant['id'], updates)
        # 若已发布且有post_url，尝试同步频道caption
        try:
            m2 = await MerchantManager.get_merchant_by_id(merchant['id'])
            if m2 and str(m2.get('status')) == 'published' and m2.get('post_url'):
                await _refresh_post(merchant['id'])
        except Exception:
            pass
        await _finalize_and_back_to_menu(state, callback.bot, callback.message.chat.id, callback.message, user_id)
        await callback.answer("已保存")
    except Exception as e:
        logger.error(f"保存地区失败: {e}")
        await callback.answer("保存失败", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_edit_keywords")
async def merchant_edit_keywords(callback: CallbackQuery, state: FSMContext):
    """进入关键词编辑：多选并支持保存。"""
    try:
        user_id = callback.from_user.id
        await state.update_data(editing_mode="profile")
        # 预填当前关键词
        try:
            merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
            current_ids = []
            if merchant:
                rows = await db_manager.fetch_all("SELECT keyword_id FROM merchant_keywords WHERE merchant_id = ?", (merchant['id'],))
                current_ids = [str(r['keyword_id']) for r in rows]
        except Exception:
            current_ids = []
        await state.update_data(user_choices={"keywords": current_ids}, current_step=8)

        # 构建多选键盘（沿用binding_step8_前缀）
        options = await merchant_handler.binding_flow_manager.load_dynamic_options(8, {"keywords": current_ids}) if merchant_handler else []
        inline = []
        for o in options:
            prefix = "✅ " if o['value'] in current_ids else ""
            inline.append([InlineKeyboardButton(text=f"{prefix}{o['text']}", callback_data=f"binding_step8_{o['value']}")])
        # 保存按钮
        inline.append([InlineKeyboardButton(text="💾 保存关键词", callback_data="binding_keywords_save")])
        kb = InlineKeyboardMarkup(inline_keyboard=inline)
        await callback.message.answer("请选择/取消选择关键词，完成后点击“保存关键词”：", reply_markup=kb)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入关键词编辑失败: {e}")
        await callback.answer("进入编辑失败，请重试", show_alert=True)

# 注册路由处理器
@merchant_router.message(F.text.contains("上榜流程"))
async def handle_registration_trigger(message: Message, state: FSMContext):
    """处理注册触发关键词"""
    if merchant_handler is None:
        init_text = await template_manager.get_template('system_initializing')
        await message.answer(init_text)
        return
    await merchant_handler.handle_registration_trigger(message, state)

@merchant_router.message(MerchantStates.entering_binding_code)
async def handle_binding_code(message: Message, state: FSMContext):
    """处理绑定码输入"""
    if merchant_handler is None:
        init_text = await template_manager.get_template('system_initializing')
        await message.answer(init_text)
        return
    await merchant_handler.handle_binding_code_input(message, state)

# 已废弃的“/panel 商户面板”命令入口：
# 根据最新设计，商户通过“/start → 我的资料”查看与编辑，无需手动输入命令。

# ============== 7步流程处理器（已注释，可恢复） ==============
# 恢复7步流程时，取消以下代码的注释即可
#

@merchant_router.callback_query(F.data.startswith("binding_"))
async def handle_binding_callbacks(callback: CallbackQuery, state: FSMContext):
    """处理绑定流程回调 - 使用新的BindingFlowManager"""
    try:
        callback_data = callback.data
        user_id = callback.from_user.id
        logger.info(f"处理回调: {callback_data}, 用户: {user_id}")
        # 串联式上榜流程已停用：仅在编辑模式下使用少量binding_*回调（类型、关键词、日期时间）
        try:
            data = await state.get_data()
            editing_mode = data.get("editing_mode")
        except Exception:
            editing_mode = None
        if editing_mode != "profile":
            # 直接返回资料面板
            try:
                await show_profile_panel_like_user(callback.message, user_id, state)
            except Exception:
                pass
            await callback.answer("上榜引导已停用，请在“我的资料”中编辑")
            return
        
        # 获取或初始化用户数据（优先从持久化FSM读取，避免此前clear()导致的数据丢失）
        try:
            _state_name, _persist = await fsm_db.load_user_state(user_id)
            user_choices = (_persist or {}).get("user_choices", {})
            current_step = (_persist or {}).get("current_step", 1)
        except Exception:
            state_data = await state.get_data()
            user_choices = state_data.get("user_choices", {})
            current_step = state_data.get("current_step", 1)
        logger.info(f"当前用户选择: {user_choices}, 当前步骤: {current_step}")
        
        # 已移除取消注册功能
        
        # 处理预览操作
        if callback_data == "binding_preview":
            # 显示最终预览页面（竖排列出所有关键信息）
            from config import MESSAGE_TEMPLATES
            # 读取草稿中的商户资料（名称、联系方式、用户信息）
            try:
                merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
            except Exception:
                merchant = None
            merchant_name = (merchant or {}).get('name') or '未设置'
            contact_info = (merchant or {}).get('contact_info') or '-'
            tg_username = '-'
            try:
                import json as _json
                ui = (merchant or {}).get('user_info')
                if isinstance(ui, str) and ui:
                    ui = _json.loads(ui)
                if isinstance(ui, dict):
                    u = ui.get('username')
                    if u:
                        tg_username = f"@{u}"
            except Exception:
                pass

            # 处理地区名称
            city_display = user_choices.get('city', '未填写')
            district_display = user_choices.get('district', '未填写')
            try:
                from database.db_regions import region_manager as _region_mgr
                if str(user_choices.get('city', '')).isdigit():
                    c = await _region_mgr.get_city_by_id(int(user_choices['city']))
                    if c:
                        city_display = c.get('name', city_display)
                if str(user_choices.get('district', '')).isdigit():
                    d = await _region_mgr.get_district_by_id(int(user_choices['district']))
                    if d:
                        district_display = d.get('name', district_display)
            except Exception:
                pass

            # 频道信息（用户名与可点击链接）
            ch_username = user_choices.get('channel_username') or (merchant or {}).get('channel_chat_id') or '-'
            ch_username = ch_username if isinstance(ch_username, str) else '-'
            username_core = ch_username.lstrip('@') if ch_username and ch_username != '-' else None
            ch_link = None
            if username_core:
                ch_link = f"https://t.me/{username_core}"
            # 如果草稿已写入 channel_link，以它为准
            if (merchant or {}).get('channel_link'):
                ch_link = (merchant or {}).get('channel_link')

            # 关键词
            try:
                # 允许keywords以list或逗号分隔字符串存在
                kws = user_choices.get('keywords', [])
                if isinstance(kws, str):
                    kws = [s.strip() for s in kws.split(',') if s.strip()]
                keywords_text = ', '.join(kws) or '无'
            except Exception:
                keywords_text = '无'

            # 竖排预览文本
            pub_preview = '-'
            if user_choices.get('publish_date') and user_choices.get('publish_time_str'):
                pub_preview = f"{user_choices['publish_date']} {user_choices['publish_time_str']}"

            preview_text = (
                f"名称：{merchant_name}\n"
                f"商户类型：{user_choices.get('merchant_type', '未填写')}\n"
                f"地区：{city_display} - {district_display}\n"
                f"频道用户名：{ch_username}\n"
                f"频道链接：{ch_link or '-'}\n"
                f"Telegram 用户名：{tg_username}\n"
                f"联系方式：{contact_info}\n"
                f"价格：P {user_choices.get('p_price', '未填写')} | PP {user_choices.get('pp_price', '未填写')}\n"
                f"一句话优势：{user_choices.get('adv_sentence', '无')}\n"
                f"关键词：{keywords_text}\n"
                f"发布时间：{pub_preview}"
            )

            # 添加预览页面的操作按钮
            preview_buttons = [
                [InlineKeyboardButton(text="✅ 确认注册", callback_data="binding_confirm_final")],
                [InlineKeyboardButton(text="🔄 重新填写", callback_data="binding_restart")]
            ]
            
            preview_keyboard = InlineKeyboardMarkup(inline_keyboard=preview_buttons)
            await safe_edit_message(
                callback.message,
                f"📋 注册信息预览\n\n{preview_text}",
                reply_markup=preview_keyboard,
                parse_mode=None
            )
            await callback.answer("请确认您的注册信息")
            return

        # 关键词保存（仅编辑模式使用）
        if callback_data == "binding_keywords_save":
            try:
                data = await state.get_data()
                if data.get("editing_mode") != "profile":
                    await callback.answer("请完成注册确认以保存关键词", show_alert=True)
                    return
                kw_ids = []
                for v in (data.get("user_choices", {}).get("keywords", []) or []):
                    if str(v).isdigit():
                        kw_ids.append(int(v))
                # 统一限制：最多3个
                kw_ids = kw_ids[:3]
                merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
                if not merchant:
                    await callback.answer("未找到商户信息", show_alert=True)
                    return
                # 替换保存
                await db_manager.execute_query("DELETE FROM merchant_keywords WHERE merchant_id = ?", (merchant['id'],))
                for kid in kw_ids:
                    await db_manager.execute_query(
                        "INSERT INTO merchant_keywords (merchant_id, keyword_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                        (merchant['id'], kid)
                    )
                await state.clear()
                # 若已发布且有post_url，尝试同步频道caption（标签可能影响caption）
                try:
                    m2 = await MerchantManager.get_merchant_by_id(merchant['id'])
                    if m2 and str(m2.get('status')) == 'published' and m2.get('post_url'):
                        from services.telegram_tasks import enqueue_edit_caption
                        enqueue_edit_caption(merchant['id'])
                    # 管理员通知（关键词更新）
                    before_stub = { 'id': merchant['id'], 'name': m2.get('name') if m2 else '-', 'keywords': None }
                    await _notify_admin_change(callback.bot, before_stub, m2, ['keywords'])
                except Exception:
                    pass
                try:
                    await show_profile_panel_like_user(callback.message, user_id, state)
                except Exception:
                    pass
                await callback.answer("已保存")
            except Exception as e:
                logger.error(f"保存关键词失败: {e}")
                await callback.answer("保存失败，请重试", show_alert=True)
            return
        
        # 处理最终确认操作
        if callback_data == "binding_confirm_final":
            # 完成所有步骤
            # 先强制校验：商户发布频道必须为公开用户名（@channel），否则不允许提交
            try:
                merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
            except Exception:
                merchant = None
            channel_ok = False
            ch = merchant.get('channel_chat_id') if merchant else None
            if isinstance(ch, str) and ch.startswith('@') and len(ch) > 1:
                channel_ok = True
            if not channel_ok:
                await callback.answer("请先设置频道用户名（步骤7）", show_alert=True)
                await callback.message.answer(
                    "⚠️ 发布频道未设置为公开用户名。请在“频道用户名”步骤输入 @yourchannel（仅允许字母/数字/下划线，5–32位）",
                    parse_mode=None
                )
                return

            # 强制要求：必须先选择发布日期+时间（步骤9）
            if not (user_choices.get('publish_date') and user_choices.get('publish_time_str')):
                await callback.answer("请先选择发布时间（步骤9）", show_alert=True)
                if merchant_handler and merchant_handler.binding_flow_manager:
                    await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 9)
                return

            # 生成最终确认的可读摘要（显示名称/用户名/地区名等）
            try:
                from database.db_regions import region_manager as _rm
                city_name = '-'
                district_name = '-'
                if str(user_choices.get('city', '')).isdigit():
                    c = await _rm.get_city_by_id(int(user_choices['city']))
                    if c:
                        city_name = c.get('name') or '-'
                if str(user_choices.get('district', '')).isdigit():
                    d = await _rm.get_district_by_id(int(user_choices['district']))
                    if d:
                        district_name = d.get('name') or '-'
            except Exception:
                city_name = user_choices.get('city', '-')
                district_name = user_choices.get('district', '-')

            # 最终提交前再次校验时间槽未被占用（避免竞态）
            try:
                from database.db_merchants import MerchantManager as _MM
                merchant_self = await MerchantManager.get_merchant_by_chat_id(user_id)
                date_str = user_choices.get('publish_date')
                time_str = user_choices.get('publish_time_str')
                if date_str and time_str:
                    if not await _MM.is_time_slot_available(date_str, time_str, exclude_merchant_id=(merchant_self or {}).get('id')):
                        await callback.answer("该时间已被其他商家占用，请重新选择", show_alert=True)
                        if merchant_handler and merchant_handler.binding_flow_manager:
                            await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 9)
                        return
            except Exception:
                pass

            # 解析用户名
            tg_username = '-'
            try:
                ui = (merchant or {}).get('user_info')
                if isinstance(ui, str) and ui:
                    ui = json.loads(ui)
                if isinstance(ui, dict):
                    u = ui.get('username') or (ui.get('raw_info', {}) if isinstance(ui, dict) else {}).get('username')
                    if u:
                        tg_username = f"@{u}"
            except Exception:
                pass

            ch_username = (merchant or {}).get('channel_chat_id') or user_choices.get('channel_username') or '-'
            contact_info = (merchant or {}).get('contact_info') or '-'
            # 名称展示：优先用DB的name；若为空/待完善则读user_info.full_name
            name_display = (merchant or {}).get('name')
            if not name_display or str(name_display).strip() in ('', '待完善'):
                try:
                    ui2 = (merchant or {}).get('user_info')
                    if isinstance(ui2, str) and ui2:
                        ui2 = json.loads(ui2)
                    if isinstance(ui2, dict):
                        name_display = ui2.get('full_name') or name_display
                except Exception:
                    pass
            name_display = name_display or '-'

            # 关键词（如果是ID列表，转成数量或留空）
            kw_vals = user_choices.get('keywords', []) or []
            keywords_text = ', '.join([str(v) for v in kw_vals]) if kw_vals else '无'

            # 发布时间预览
            pub_text = '-'
            if user_choices.get('publish_date') and user_choices.get('publish_time_str'):
                pub_text = f"{user_choices['publish_date']} {user_choices['publish_time_str']}"

            choices_text = "\n".join([
                f"名称: {name_display}",
                f"用户名: {tg_username}",
                f"商户类型: {user_choices.get('merchant_type', '-')}",
                f"地区: {city_name} - {district_name}",
                f"频道用户名: {ch_username}",
                f"联系方式: {contact_info}",
                f"P价格: {user_choices.get('p_price', '-')}",
                f"PP价格: {user_choices.get('pp_price', '-')}",
                f"优势: {user_choices.get('adv_sentence', '-')}",
                f"关键词: {keywords_text}",
                f"发布时间: {pub_text}"
            ])
            
            # 按唯一真源写入：商户类型、城市/区县、关键词、状态
            try:
                updates = {}
                if user_choices.get('merchant_type'):
                    updates['merchant_type'] = user_choices['merchant_type']
                if str(user_choices.get('city', '')).isdigit():
                    updates['city_id'] = int(user_choices['city'])
                if str(user_choices.get('district', '')).isdigit():
                    updates['district_id'] = int(user_choices['district'])
                if user_choices.get('p_price') is not None:
                    updates['p_price'] = user_choices.get('p_price')
                if user_choices.get('pp_price') is not None:
                    updates['pp_price'] = user_choices.get('pp_price')
                if user_choices.get('custom_description') is not None:
                    updates['custom_description'] = user_choices.get('custom_description')
                if user_choices.get('adv_sentence') is not None:
                    updates['adv_sentence'] = user_choices.get('adv_sentence')
                # 选择了日期与时间 → 预先写入计划发布的时间
                if user_choices.get('publish_date') and user_choices.get('publish_time_str'):
                    updates['publish_time'] = f"{user_choices['publish_date']} {user_choices['publish_time_str']}:00"
                # 状态进入待审核
                updates['status'] = 'pending_approval'
                await MerchantManager.update_merchant(merchant['id'], updates)

                # 同步关键词（允许为空）
                kw_vals = user_choices.get('keywords', []) or []
                # 将字符串逗号分隔形式规整为空列表
                try:
                    _kw_ids = [int(v) for v in kw_vals if str(v).isdigit()]
                except Exception:
                    _kw_ids = []
                # 统一限制：最多3个
                _kw_ids = _kw_ids[:3]
                await db_manager.execute_query("DELETE FROM merchant_keywords WHERE merchant_id = ?", (merchant['id'],))
                for kid in _kw_ids:
                    await db_manager.execute_query(
                        "INSERT INTO merchant_keywords (merchant_id, keyword_id, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                        (merchant['id'], kid)
                    )
            except Exception as e:
                logger.error(f"最终写入失败: {e}")
                await callback.answer("保存失败，请重试", show_alert=True)
                return

            await safe_edit_message(callback.message, f"🎉 注册信息收集完成！\n\n{choices_text}\n\n注册成功！")
            await callback.answer("注册完成！")
            await state.clear()
            await fsm_db.clear_user_state(user_id)
            return
        
        # 处理重新填写操作
        if callback_data == "binding_restart":
            # 重置所有数据，回到第一步
            await state.clear()
            initial_choices = {}
            await state.update_data(user_choices=initial_choices, current_step=1)
            await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": initial_choices, "current_step": 1})
            
            # 显示第一步
            if merchant_handler and merchant_handler.binding_flow_manager:
                await merchant_handler.binding_flow_manager.show_step(callback, initial_choices, 1)
            
            await callback.answer("已重置，请重新填写")
            return
        
        # 选择日期（步骤9）：binding_pickdate_YYYY-MM-DD
        if callback_data.startswith("binding_pickdate_"):
            try:
                date_str = callback_data.replace("binding_pickdate_", "")
                user_choices['publish_date'] = date_str
                await state.update_data(user_choices=user_choices)
                await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": user_choices, "current_step": 9})
                if merchant_handler and merchant_handler.binding_flow_manager:
                    await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 9)
                await state.set_state(MerchantStates.selecting_publish_time)
                await callback.answer("已选择日期")
                return
            except Exception as e:
                logger.error(f"选择日期失败: {e}")
                await callback.answer("选择失败", show_alert=True)
                return

        # 完成媒体上传
        if callback_data == "binding_media_done":
            try:
                merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
                count = 0
                if merchant:
                    files = await media_db.get_media_by_merchant_id(merchant['id'])
                    count = len(files or [])
                if count != 6:
                    await callback.answer(f"还差 {6 - count if count < 6 else 0} 个媒体，需正好6个", show_alert=True)
                    if merchant_handler and merchant_handler.binding_flow_manager:
                        await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 10)
                        # 进入媒体上传状态
                        try:
                            await state.set_state(MerchantStates.uploading_media)
                            await state.update_data(media_status_mid=int(callback.message.message_id))
                        except Exception:
                            pass
                    return
                # 已满足媒体要求：若已选择日期时间，回到步骤9供确认；否则提示先选择时间
                if user_choices.get('publish_date') and user_choices.get('publish_time_str'):
                    if merchant_handler and merchant_handler.binding_flow_manager:
                        await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 9)
                    await callback.answer("媒体已就绪，请确认注册")
                else:
                    await callback.answer("媒体已就绪，请先选择发布时间（步骤9）", show_alert=True)
                    if merchant_handler and merchant_handler.binding_flow_manager:
                        await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 9)
                return
            except Exception as e:
                logger.error(f"检查媒体完成失败: {e}")
                await callback.answer("操作失败，请重试", show_alert=True)
                return

        # 处理确认按钮（文本输入步骤的确认）
        if callback_data.startswith("binding_confirm_step"):
            try:
                confirm_step = int(callback_data.replace("binding_confirm_step", ""))
                logger.info(f"确认进入步骤: {confirm_step}")
                
                # 确认后继续到下一步
                next_step = confirm_step
                await state.update_data(user_choices=user_choices, current_step=next_step)
                
                if next_step <= 9:
                    # 显示下一步
                    if merchant_handler and merchant_handler.binding_flow_manager:
                        # 如果是步骤7（关键词选择），需要先清除FSM状态，但保留用户数据
                        display_user_choices = user_choices
                        if next_step == 8:
                            logger.info("清除FSM状态，准备显示关键词选择")
                            # 保存用户数据
                            display_user_choices = user_choices.copy()
                            await state.clear()
                            await state.update_data(user_choices=display_user_choices, current_step=next_step)
                        
                        logger.info(f"显示步骤 {next_step}")
                        fsm_field = await merchant_handler.binding_flow_manager.show_step(callback, display_user_choices, next_step)
                        
                        # 如果是文本输入步骤，设置FSM状态
                        if fsm_field:
                            if fsm_field == "p_price":
                                await state.set_state(MerchantStates.entering_p_price)
                            elif fsm_field == "pp_price":
                                await state.set_state(MerchantStates.entering_pp_price)
                            elif fsm_field == "custom_description":
                                await state.set_state(MerchantStates.entering_custom_description)
                            elif fsm_field == "adv_sentence":
                                await state.set_state(MerchantStates.entering_adv_sentence)
                            elif fsm_field == "channel_username":
                                await state.set_state(MerchantStates.entering_channel_username)
                        elif next_step == 9:
                            await state.set_state(MerchantStates.selecting_publish_time)
                    
                    await callback.answer(f"已确认，进入下一步")
                else:
                    # 若是时间步骤完成（step 9），回显时间选择并提供确认
                    if confirm_step == 9:
                        if merchant_handler and merchant_handler.binding_flow_manager:
                            await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 9)
                        await callback.answer("已选择时间，请确认注册")
                    else:
                        await callback.answer("所有步骤已完成！")
                
                return
            except Exception as confirm_error:
                logger.error(f"处理确认步骤失败: {confirm_error}", exc_info=True)
                await callback.answer("确认处理失败，请重试", show_alert=True)
                return
        
        # 旧的“跳转步骤”改为返回菜单
        if callback_data.startswith("binding_goto_"):
            await merchant_back_to_menu(callback, state)
            return

        # 解析步骤和值（包含步骤9：选择发布时间）
        for step_num in range(1, 11):
            step_prefix = f"binding_step{step_num}_"
            if callback_data.startswith(step_prefix):
                selected_value = callback_data.replace(step_prefix, "")
                logger.info(f"步骤{step_num}选择: {selected_value}")
                
                # 获取步骤配置
                step_config = BINDING_FLOW_STEPS[step_num]
                field_name = step_config["field"]
                
                # 处理多选（只有关键词是多选）
                if step_num == 8:  # 关键词多选（限制最多3个）
                    current_selection = user_choices.get(field_name, []) or []
                    # 取消选择
                    if selected_value in current_selection:
                        current_selection.remove(selected_value)
                    else:
                        # 限制最多3个
                        if len(current_selection) >= 3:
                            await callback.answer("最多选择3个关键词", show_alert=True)
                            # 重新渲染以保留提示后的当前视图
                            await state.update_data(user_choices=user_choices, current_step=step_num)
                            if merchant_handler and merchant_handler.binding_flow_manager:
                                await merchant_handler.binding_flow_manager.show_step(callback, user_choices, step_num)
                            return
                        current_selection.append(selected_value)
                    user_choices[field_name] = current_selection
                    
                    # 重新显示步骤7，显示当前选择
                    await state.update_data(user_choices=user_choices, current_step=step_num)
                    await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": user_choices, "current_step": step_num})
                    if merchant_handler and merchant_handler.binding_flow_manager:
                        await merchant_handler.binding_flow_manager.show_step(callback, user_choices, step_num)
                    await callback.answer(f"已更新关键词选择")
                    return
                    
                else:
                    # 单选步骤
                    # 步骤9选择时间前，先检查该时间槽是否已被占用
                    if step_num == 9 and user_choices.get('publish_date'):
                        try:
                            from database.db_merchants import MerchantManager as _MM
                            date_str = user_choices.get('publish_date')
                            if not await _MM.is_time_slot_available(date_str, selected_value):
                                await callback.answer("该时间已被选，请选择其他时间", show_alert=True)
                                if merchant_handler and merchant_handler.binding_flow_manager:
                                    await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 9)
                                return
                        except Exception:
                            pass
                    user_choices[field_name] = selected_value
                    next_step = step_num + 1

                    # 判断是否是“我的资料”编辑模式
                    try:
                        data = await state.get_data()
                        editing_mode = data.get("editing_mode")
                    except Exception:
                        editing_mode = None

                    if editing_mode == "profile":
                        try:
                            merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
                            if merchant:
                                if step_num == 1:
                                    await MerchantManager.update_merchant(merchant['id'], {'merchant_type': selected_value})
                                    # 若已发布且有post_url，尝试同步频道caption
                                    try:
                                        m2 = await MerchantManager.get_merchant_by_id(merchant['id'])
                                        if m2 and str(m2.get('status')) == 'published' and m2.get('post_url'):
                                            await _refresh_post(merchant['id'])
                                    except Exception:
                                        pass
                                    await _finalize_and_back_to_menu(state, callback.bot, callback.message.chat.id, callback.message, user_id)
                                    await callback.answer("已保存")
                                    return
                                if step_num == 9:
                                    # 在编辑模式下，选择具体时间后即保存发布时间并返回菜单
                                    date_str = user_choices.get('publish_date')
                                    time_str = selected_value if selected_value else user_choices.get('publish_time_str')
                                    if date_str and time_str:
                                        await MerchantManager.update_merchant(merchant['id'], {
                                            'publish_time': f"{date_str} {time_str}:00"
                                        })
                                        await _clear_prompt_messages(state, callback.bot, callback.message.chat.id)
                                        try:
                                            await show_profile_panel_like_user(callback.message, user_id, state)
                                        except Exception:
                                            pass
                                        # 软清理，仅保留面板ID
                                        try:
                                            data2 = await state.get_data(); pid = data2.get('panel_message_id'); await state.clear();
                                            if pid: await state.update_data(panel_message_id=pid)
                                        except Exception:
                                            pass
                                        await callback.answer("已保存")
                                        return
                                if step_num == 2:
                                    # 选城市后进入地区选择
                                    await state.update_data(user_choices=user_choices, current_step=next_step, editing_mode=editing_mode)
                                    await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": user_choices, "current_step": next_step})
                                    if merchant_handler and merchant_handler.binding_flow_manager:
                                        fsm_field = await merchant_handler.binding_flow_manager.show_step(callback, user_choices, next_step)
                                        if fsm_field == "p_price":
                                            await state.set_state(MerchantStates.entering_p_price)
                                        elif fsm_field == "pp_price":
                                            await state.set_state(MerchantStates.entering_pp_price)
                                        elif fsm_field == "custom_description":
                                            await state.set_state(MerchantStates.entering_custom_description)
                                        elif fsm_field == "channel_username":
                                            await state.set_state(MerchantStates.entering_channel_username)
                                    await callback.answer("请选择地区")
                                    return
                                if step_num == 3:
                                    updates = {
                                        'city_id': int(user_choices.get('city')) if str(user_choices.get('city','')).isdigit() else None,
                                        'district_id': int(selected_value) if str(selected_value).isdigit() else None,
                                    }
                                    await MerchantManager.update_merchant(merchant['id'], updates)
                                    try:
                                        m2 = await MerchantManager.get_merchant_by_id(merchant['id'])
                                        if m2 and str(m2.get('status')) == 'published' and m2.get('post_url'):
                                            await _refresh_post(merchant['id'])
                                    except Exception:
                                        pass
                                    await _finalize_and_back_to_menu(state, callback.bot, callback.message.chat.id, callback.message, user_id)
                                    await callback.answer("已保存")
                                    return
                        except Exception as _e:
                            logger.debug(f"编辑模式保存失败: {_e}")

                    # 非编辑模式：更新状态，继续下一步
                    await state.update_data(user_choices=user_choices, current_step=next_step)
                    await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": user_choices, "current_step": next_step})
                    # 将关键选择实时写入数据库，便于Web端展示
                    if field_name == 'city':
                        try:
                            await merchant_handler._update_merchant_draft(user_id, {'city_id': int(selected_value)})
                        except Exception:
                            pass
                    elif field_name == 'district':
                        try:
                            await merchant_handler._update_merchant_draft(user_id, {'district_id': int(selected_value)})
                        except Exception:
                            pass

                    # 如果当前是步骤9（选择时间），选择后直接保存并返回资料面板
                    if step_num == 9:
                        try:
                            date_str = user_choices.get('publish_date')
                            time_str = selected_value or user_choices.get('publish_time_str')
                            if date_str and time_str:
                                merchant_self = await MerchantManager.get_merchant_by_chat_id(user_id)
                                if merchant_self:
                                    await MerchantManager.update_merchant(merchant_self['id'], {
                                        'publish_time': f"{date_str} {time_str}:00"
                                    })
                                    try:
                                        m2 = await MerchantManager.get_merchant_by_id(merchant_self['id'])
                                        if m2 and str(m2.get('status')) == 'published' and m2.get('post_url'):
                                            await _refresh_post(merchant_self['id'])
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        # 清理步骤状态并返回资料面板
                        try:
                            await state.clear()
                        except Exception:
                            pass
                        await callback.answer(f"已选择时间: {selected_value}")
                        try:
                            await show_profile_panel_like_user(callback.message, user_id, state)
                        except Exception:
                            pass
                        return

                    if next_step <= 9:
                        # 显示下一步
                        if merchant_handler and merchant_handler.binding_flow_manager:
                            fsm_field = await merchant_handler.binding_flow_manager.show_step(callback, user_choices, next_step)
                            # 如果是文本输入步骤，设置FSM状态
                            if fsm_field:
                                if fsm_field == "p_price":
                                    await state.set_state(MerchantStates.entering_p_price)
                                elif fsm_field == "pp_price":
                                    await state.set_state(MerchantStates.entering_pp_price)
                                elif fsm_field == "custom_description":
                                    await state.set_state(MerchantStates.entering_custom_description)
                                elif fsm_field == "adv_sentence":
                                    await state.set_state(MerchantStates.entering_adv_sentence)
                                elif fsm_field == "channel_username":
                                    await state.set_state(MerchantStates.entering_channel_username)

                        await callback.answer(f"已选择: {selected_value}")
                    else:
                        # 所有步骤完成
                        await callback.answer("所有步骤已完成！")

                    logger.info(f"步骤{step_num}处理完成")
                    return
        
        # 未匹配的回调数据
        logger.warning(f"未知的回调数据: {callback_data}")
        await callback.answer("未知操作", show_alert=True)
        
    except Exception as e:
        logger.error(f"处理回调失败: {e}", exc_info=True)
        await callback.answer("处理失败，请重试", show_alert=True)

@merchant_router.message(F.text, StateFilter(
    MerchantStates.entering_name,
    MerchantStates.entering_contact_info,
    MerchantStates.entering_p_price,
    MerchantStates.entering_pp_price,
    MerchantStates.entering_custom_description,
    MerchantStates.entering_adv_sentence,
    MerchantStates.entering_channel_username
))
async def handle_binding_text_input(message: Message, state: FSMContext):
    """处理绑定流程中的文本输入（步骤4/5/6）。
    逻辑尽量最小改动：保存输入 -> 前进到下一步 -> 推送下一步提示/按钮。
    """
    try:
        user_id = message.from_user.id
        # 记录用户输入消息，确保统一清理
        await _push_user_message(state, message.message_id)
        text = (message.text or "").strip()
        current_state = await state.get_state()

        # 取得用户已有选择
        state_data = await state.get_data()
        user_choices = state_data.get("user_choices", {})

        # 基本字段与流转
        if current_state == MerchantStates.entering_name:
            # 名称直接保存
            if not text:
                await message.answer("名称不能为空")
                return
            try:
                merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
                if merchant:
                    before = await MerchantManager.get_merchant_by_id(merchant['id'])
                    await MerchantManager.update_merchant(merchant['id'], {'name': text})
                    try:
                        after = await MerchantManager.get_merchant_by_id(merchant['id'])
                        if after and str(after.get('status')) == 'published' and after.get('post_url'):
                            from services.telegram_tasks import enqueue_edit_caption
                            enqueue_edit_caption(merchant['id'])
                        await _notify_admin_change(message.bot, before, after, ['name'])
                    except Exception:
                        pass
            except Exception:
                pass
            await _clear_prompt_messages(state, message.bot, message.chat.id)
            await _finalize_and_back_to_menu(state, message.bot, message.chat.id, message, user_id)
            return

        if current_state == MerchantStates.entering_contact_info:
            # 联系方式直接保存
            try:
                merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
                if merchant:
                    before = await MerchantManager.get_merchant_by_id(merchant['id'])
                    await MerchantManager.update_merchant(merchant['id'], {'contact_info': text})
                    try:
                        after = await MerchantManager.get_merchant_by_id(merchant['id'])
                        if after and str(after.get('status')) == 'published' and after.get('post_url'):
                            from services.telegram_tasks import enqueue_edit_caption
                            enqueue_edit_caption(merchant['id'])
                        await _notify_admin_change(message.bot, before, after, ['contact_info'])
                    except Exception:
                        pass
            except Exception:
                pass
            await _clear_prompt_messages(state, message.bot, message.chat.id)
            await _finalize_and_back_to_menu(state, message.bot, message.chat.id, message, user_id)
            return
        if current_state == MerchantStates.entering_p_price:
            # 验证数字（允许小数，最多两位）
            if not re.fullmatch(r"\d+(?:\.\d{1,2})?", text):
                await message.answer("请输入合法的数字价格，例如 88 或 88.00")
                return
            user_choices["p_price"] = text
            await state.update_data(user_choices=user_choices)
            await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": user_choices, "current_step": 4})

            # 不再需要“确认并继续”，直接跳到下一步
            # 实时写入草稿
            try:
                await merchant_handler._update_merchant_draft(user_id, {'p_price': text})
            except Exception:
                pass

            # 若来自“我的资料”编辑模式，直接完成并提示
            if (await state.get_data()).get("editing_mode") == "profile":
                await _clear_prompt_messages(state, message.bot, message.chat.id)
                await state.clear()
            try:
                await show_profile_panel_like_user(message, user_id, state)
            except Exception:
                pass
                return

            # 统一交互：不自动导航，直接回资料面板（并清理用户输入与提示）
            await _finalize_and_back_to_menu(state, message.bot, message.chat.id, message, user_id)
            return

        if current_state == MerchantStates.entering_pp_price:
            if not re.fullmatch(r"\d+(?:\.\d{1,2})?", text):
                await message.answer("请输入合法的数字价格，例如 188 或 188.00")
                return
            user_choices["pp_price"] = text
            await state.update_data(user_choices=user_choices)
            await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": user_choices, "current_step": 5})

            # 不再需要“确认并继续”，直接跳到下一步
            # 实时写入草稿
            try:
                await merchant_handler._update_merchant_draft(user_id, {'pp_price': text})
            except Exception:
                pass

            # 编辑模式：直接完成
            if (await state.get_data()).get("editing_mode") == "profile":
                await _clear_prompt_messages(state, message.bot, message.chat.id)
                await state.clear()
            try:
                await show_profile_panel_like_user(message, user_id, state)
            except Exception:
                pass
                return

            await _finalize_and_back_to_menu(state, message.bot, message.chat.id, message, user_id)
            return

        if current_state == MerchantStates.entering_custom_description:
            # 描述文本可直接保存
            user_choices["custom_description"] = text
            await state.update_data(user_choices=user_choices)
            await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": user_choices, "current_step": 6})
            # 实时写入草稿
            try:
                await merchant_handler._update_merchant_draft(user_id, {'custom_description': text})
            except Exception:
                pass
            # 若来自“我的资料”编辑模式：只改描述，直接完成
            if (await state.get_data()).get("editing_mode") == "profile":
                try:
                    merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
                    if merchant:
                        before = await MerchantManager.get_merchant_by_id(merchant['id'])
                        await MerchantManager.update_merchant(merchant['id'], {'custom_description': text})
                        try:
                            after = await MerchantManager.get_merchant_by_id(merchant['id'])
                            if after and str(after.get('status')) == 'published' and after.get('post_url'):
                                from services.telegram_tasks import enqueue_edit_caption
                                enqueue_edit_caption(merchant['id'])
                            await _notify_admin_change(message.bot, before, after, ['custom_description'])
                        except Exception:
                            pass
                except Exception:
                    pass
                await _clear_prompt_messages(state, message.bot, message.chat.id)
                await state.clear()
            try:
                await show_profile_panel_like_user(message, user_id, state)
            except Exception:
                pass
                return
            await _finalize_and_back_to_menu(state, message.bot, message.chat.id, message, user_id)
            return

        if current_state == MerchantStates.entering_adv_sentence:
            # 一句话优势：记录后给出确认继续按钮（与第7步衔接）
            user_choices["adv_sentence"] = text
            await state.update_data(user_choices=user_choices)
            await fsm_db.save_user_state(
                user_id,
                merchant_handler.flow_state_name,
                {"user_choices": user_choices, "current_step": 6}
            )
            # 实时写入草稿
            try:
                await merchant_handler._update_merchant_draft(user_id, {'adv_sentence': text})
            except Exception:
                pass
            # 若来自“我的资料”编辑模式：直接保存并返回面板
            if (await state.get_data()).get("editing_mode") == "profile":
                try:
                    merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
                    if merchant:
                        before = await MerchantManager.get_merchant_by_id(merchant['id'])
                        await MerchantManager.update_merchant(merchant['id'], {'adv_sentence': text})
                        try:
                            after = await MerchantManager.get_merchant_by_id(merchant['id'])
                            if after and str(after.get('status')) == 'published' and after.get('post_url'):
                                from services.telegram_tasks import enqueue_edit_caption
                                enqueue_edit_caption(merchant['id'])
                            await _notify_admin_change(message.bot, before, after, ['adv_sentence'])
                        except Exception:
                            pass
                except Exception:
                    pass
                await _clear_prompt_messages(state, message.bot, message.chat.id)
                await state.clear()
                try:
                    await show_profile_panel_like_user(message, user_id, state)
                except Exception:
                    pass
                return

            # 非编辑场景：提示“确认并继续”进入步骤7
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="确认并继续", callback_data="binding_confirm_step7")]
            ])
            await message.answer(f"已记录优势：{text}\n请点击“确认并继续”进入下一步。", reply_markup=kb, parse_mode=None)
            return

        if current_state == MerchantStates.entering_channel_username:
            # 频道用户名输入标准化：支持 @username / username / https://t.me/username
            raw = text
            username = None
            if raw.startswith('http://') or raw.startswith('https://'):
                try:
                    # 简单解析URL，提取 t.me/<username>
                    from urllib.parse import urlparse
                    p = urlparse(raw)
                    if p.netloc.endswith('t.me') and p.path:
                        username = p.path.strip('/').split('/')[0]
                except Exception:
                    username = None
            elif raw.startswith('@'):
                username = raw[1:]
            else:
                username = raw

            # 校验用户名：Telegram 要求 5-32 位，字母/数字/下划线
            if not username or not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
                await message.answer("请输入合法的频道用户名，例如 @yourchannel 或 https://t.me/yourchannel", parse_mode=None)
                return

            normalized_username = f"@{username}"
            user_choices["channel_username"] = normalized_username
            await state.update_data(user_choices=user_choices)
            await fsm_db.save_user_state(user_id, merchant_handler.flow_state_name, {"user_choices": user_choices, "current_step": 7})

            # 实时写入草稿
            try:
                await merchant_handler._update_merchant_draft(
                    user_id,
                    {
                        'channel_chat_id': normalized_username,
                        'channel_link': f"https://t.me/{username}"
                    }
                )
            except Exception:
                pass

            # 统一交互：清理并回资料面板（同时清空状态）
            await _finalize_and_back_to_menu(state, message.bot, message.chat.id, message, user_id)
            return

        # 未匹配：兜底
        await message.answer("处理失败，请重试")

    except Exception as e:
        logger.error(f"处理文本输入失败: {e}", exc_info=True)
        await message.answer("处理失败，请重试")

# 其他商家消息处理器（已注释）
@merchant_router.message(F.text, StateFilter(
    MerchantStates.entering_binding_code,
    MerchantStates.selecting_region,
    MerchantStates.selecting_category,
    MerchantStates.entering_name,
    MerchantStates.entering_contact_info,
    MerchantStates.confirming_profile,
    MerchantStates.editing_profile
))
async def handle_merchant_messages(message: Message, state: FSMContext):
    # 处理商家状态下的消息
    if merchant_handler:
        await merchant_handler.handle_merchant_message(message, state)

@merchant_router.callback_query(F.data.in_([
    "back", "confirm", "cancel", "edit_profile"
]))
async def handle_merchant_navigation(callback: CallbackQuery, state: FSMContext):
    # 处理商家导航回调
    if merchant_handler:
        await merchant_handler.handle_binding_flow_callback(callback, state)
# ============== 7步流程处理器注释结束 ============== 


def get_merchant_router() -> Router:
    """获取商家路由器"""
    return merchant_router

# ====== 辅助：商户上传媒体与设置频道 ======

@merchant_router.message(F.photo, StateFilter(MerchantStates.uploading_media))
async def handle_merchant_photo_upload(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
        if not merchant:
            await message.answer("您还不是商户，发送“上榜流程”完成绑定后再上传媒体。")
            return
        file_id = message.photo[-1].file_id
        existing = await media_db.get_media_by_merchant_id(merchant['id'])
        if len(existing) >= 6:
            # 环形覆盖：用最早的一个替换为新文件，并把顺序放在末尾
            try:
                oldest = min(existing, key=lambda x: x.get('sort_order', 0))
                max_order = max([m.get('sort_order', 0) for m in existing]) if existing else 0
                await db_manager.execute_query(
                    "UPDATE media SET telegram_file_id = ?, media_type = ?, sort_order = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (file_id, 'photo', max_order + 1, oldest['id'])
                )
            except Exception:
                pass
        else:
            sort_order = len(existing)
            await media_db.add_media(merchant['id'], file_id, 'photo', sort_order)
        # 归一化：确保最多6条，删除更早的
        try:
            lst = await media_db.get_media_by_merchant_id(merchant['id'])
            if len(lst) > 6:
                to_del = lst[: len(lst) - 6]
                for row in to_del:
                    await db_manager.execute_query("DELETE FROM media WHERE id = ?", (row['id'],))
        except Exception:
            pass
        # 更新状态消息而不是反复弹提示
        try:
            total = len(await media_db.get_media_by_merchant_id(merchant['id']))
        except Exception:
            total = 0
        try:
            data = await state.get_data()
            mid = int(data.get('media_status_mid') or 0)
            if mid:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ 完成上传", callback_data="merchant_media_done")],
                    [InlineKeyboardButton(text="⬅️ 返回菜单", callback_data="merchant_back_to_menu")]
                ])
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=mid,
                    text=(
                        f"请直接发送照片或视频给我（当前已有 {total} 个）。\n"
                        f"最多保存6个，超出将覆盖旧排序。完成后点击“完成上传”。"
                    ),
                    reply_markup=kb
                )
        except Exception:
            pass

        if total >= 6:
            # 自动完成并返回主面板（不再额外发送提示消息）
            await _finalize_and_back_to_menu(state, message.bot, message.chat.id, message, user_id)
    except Exception as e:
        logger.error(f"保存图片失败: {e}")
        await message.answer("保存图片失败，请重试")

@merchant_router.message(F.video, StateFilter(MerchantStates.uploading_media))
async def handle_merchant_video_upload(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
        if not merchant:
            await message.answer("您还不是商户，发送“上榜流程”完成绑定后再上传媒体。")
            return
        file_id = message.video.file_id
        existing = await media_db.get_media_by_merchant_id(merchant['id'])
        if len(existing) >= 6:
            try:
                oldest = min(existing, key=lambda x: x.get('sort_order', 0))
                max_order = max([m.get('sort_order', 0) for m in existing]) if existing else 0
                await db_manager.execute_query(
                    "UPDATE media SET telegram_file_id = ?, media_type = ?, sort_order = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (file_id, 'video', max_order + 1, oldest['id'])
                )
            except Exception:
                pass
        else:
            sort_order = len(existing)
            await media_db.add_media(merchant['id'], file_id, 'video', sort_order)
        # 归一化：确保最多6条
        try:
            lst = await media_db.get_media_by_merchant_id(merchant['id'])
            if len(lst) > 6:
                to_del = lst[: len(lst) - 6]
                for row in to_del:
                    await db_manager.execute_query("DELETE FROM media WHERE id = ?", (row['id'],))
        except Exception:
            pass
        # 更新状态消息而不是反复弹提示
        try:
            total = len(await media_db.get_media_by_merchant_id(merchant['id']))
        except Exception:
            total = 0
        try:
            data = await state.get_data()
            mid = int(data.get('media_status_mid') or 0)
            if mid:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ 完成上传", callback_data="merchant_media_done")],
                    [InlineKeyboardButton(text="⬅️ 返回菜单", callback_data="merchant_back_to_menu")]
                ])
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=mid,
                    text=(
                        f"请直接发送照片或视频给我（当前已有 {total} 个）。\n"
                        f"最多保存6个，超出将覆盖旧排序。完成后点击“完成上传”。"
                    ),
                    reply_markup=kb
                )
        except Exception:
            pass

        if total >= 6:
            await _finalize_and_back_to_menu(state, message.bot, message.chat.id, message, user_id)
    except Exception as e:
        logger.error(f"保存视频失败: {e}")
        await message.answer("保存视频失败，请重试")

@merchant_router.callback_query(F.data == "merchant_edit_media")
async def merchant_edit_media(callback: CallbackQuery, state: FSMContext):
    """进入媒体管理，提示直接发送照片/视频。"""
    try:
        user_id = callback.from_user.id
        merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
        if not merchant:
            await callback.answer("未找到商户信息", show_alert=True)
            return
        existing = await media_db.get_media_by_merchant_id(merchant['id'])
        count = len(existing)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ 完成上传", callback_data="merchant_media_done")],
            [InlineKeyboardButton(text="⬅️ 返回菜单", callback_data="merchant_back_to_menu")]
        ])
        # 进入媒体上传状态
        await state.set_state(MerchantStates.uploading_media)
        m = await callback.message.answer(
            f"请直接发送照片或视频给我（当前已有 {count} 个）。\n最多保存6个，超出将覆盖旧排序。完成后点击“完成上传”。",
            reply_markup=kb
        )
        # 记录状态消息ID，后续编辑；并加入可清理的提示列表
        try:
            await state.update_data(media_status_mid=int(m.message_id))
            await _push_prompt_message(state, m.message_id)
        except Exception:
            pass
        await callback.answer()
    except Exception as e:
        logger.error(f"进入媒体管理失败: {e}")
        await callback.answer("进入失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_media_done")
async def merchant_media_done(callback: CallbackQuery, state: FSMContext):
    try:
        user_id = callback.from_user.id
        merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
        existing = await media_db.get_media_by_merchant_id(merchant['id']) if merchant else []
        try:
            await state.clear()
        except Exception:
            pass
        try:
            await show_profile_panel_like_user(callback.message, user_id, state)
        except Exception:
            pass
        await callback.answer("已保存")
    except Exception as e:
        logger.error(f"完成媒体上传确认失败: {e}")
        await callback.answer("操作失败", show_alert=True)

# 已移除 /set_channel 命令入口：统一通过“频道用户名”步骤或“我的资料→修改频道”设置

@merchant_router.callback_query(F.data == "merchant_edit_publish_time")
async def merchant_edit_publish_time(callback: CallbackQuery, state: FSMContext):
    """进入发布时间选择：复用步骤9的日期+时间槽界面。"""
    try:
        user_id = callback.from_user.id
        await state.update_data(editing_mode="profile")
        # 预填当前发布时间
        user_choices = {}
        try:
            merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
            pt = merchant.get('publish_time') if merchant else None
            if pt and isinstance(pt, str) and len(pt) >= 16:
                # 期望格式 'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD HH:MM'
                date_part = pt[:10]
                time_part = pt[11:16]
                user_choices['publish_date'] = date_part
                user_choices['publish_time_str'] = time_part
        except Exception:
            pass
        await state.update_data(user_choices=user_choices, current_step=9)
        # 渲染日期/时间槽
        if merchant_handler and merchant_handler.binding_flow_manager:
            await merchant_handler.binding_flow_manager.show_step(callback, user_choices, 9)
        await state.set_state(MerchantStates.selecting_publish_time)
        await callback.answer()
    except Exception as e:
        logger.error(f"进入发布时间选择失败: {e}")
        await callback.answer("进入失败，请重试", show_alert=True)

@merchant_router.callback_query(F.data == "merchant_submit_review")
async def merchant_submit_review(callback: CallbackQuery, state: FSMContext):
    """提交资料进行审核：将状态设为 pending_approval。"""
    try:
        await callback.answer()
        user_id = callback.from_user.id
        merchant = await MerchantManager.get_merchant_by_chat_id(user_id)
        if not merchant:
            await callback.message.answer("未找到商户信息，请先完成绑定。")
            return

        status = (merchant.get('status') or '').lower()
        # 仅当已审核/已发布时禁止重复提交；待审核允许“重新提交”
        if status in ("approved", "published"):
            await callback.message.answer("当前已通过或已发布，无需重复操作。")
            return

        # 简单必填校验
        missing = []
        if not merchant.get('merchant_type'):
            missing.append('类型')
        if not merchant.get('district_id'):
            missing.append('地区')
        if not str(merchant.get('p_price') or '').strip():
            missing.append('P价格')
        if not str(merchant.get('pp_price') or '').strip():
            missing.append('PP价格')
        if not (merchant.get('name') or '').strip():
            missing.append('名称')
        if not (merchant.get('publish_time') or ''):
            missing.append('发布时间')
        # 媒体数量必须正好 6 张（照片/视频均可）
        try:
            from database.db_media import media_db as _media_db
            media_list = await _media_db.get_media_by_merchant_id(merchant['id'])
            if not media_list or len(media_list) != 6:
                missing.append('媒体（需6个）')
        except Exception:
            missing.append('媒体（校验失败）')

        if missing:
            await callback.message.answer("请先完善：" + "、".join(missing))
            return

        ok = await MerchantManager.update_merchant_status(merchant['id'], MERCHANT_STATUS.PENDING_APPROVAL.value)
        if ok:
            await callback.message.answer("✅ 已提交审核，管理员会尽快处理。")
            # 立即重绘资料面板，让底部按钮变为“已提交审核”
            try:
                await show_profile_panel_like_user(callback.message, user_id, state)
            except Exception:
                pass
        else:
            await callback.message.answer("提交审核失败，请稍后重试。")
    except Exception as e:
        logger.error(f"提交审核失败: {e}")
        await callback.message.answer("提交审核失败，请稍后重试。")

@merchant_router.callback_query(F.data == "merchant_back_to_menu")
async def merchant_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """统一返回资料面板，并清理提示消息。"""
    try:
        await _clear_prompt_messages(state, callback.bot, callback.message.chat.id)
        await state.clear()
        await show_profile_panel_like_user(callback.message, callback.from_user.id, state)
        await callback.answer()
    except Exception as e:
        logger.error(f"返回菜单失败: {e}")
        await callback.answer("返回失败", show_alert=True)

    
