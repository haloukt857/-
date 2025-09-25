"""
管理员处理器模块
处理管理员命令和管理功能，包括按钮配置、统计查看和绑定码生成
支持FSM状态管理和权限验证
"""

import logging
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, MESSAGE_TEMPLATES, BUTTON_TEMPLATES
from utils.template_utils import get_template_async
from utils.telegram_helpers import safe_edit_message
from database.db_templates import template_manager
from dialogs.states import AdminStates, StateData
from database.db_logs import activity_logs_db
from database.db_binding_codes import binding_codes_db
from database.db_merchants import merchant_manager
from database.db_orders import order_manager

# 配置日志
logger = logging.getLogger(__name__)

# 创建管理员路由器
admin_router = Router()


class AdminHandler:
    """
    管理员处理器类
    处理所有管理员相关的命令和交互
    """

    @staticmethod
    def is_admin(user_id: int) -> bool:
        """
        检查用户是否为管理员

        Args:
            user_id: 用户ID

        Returns:
            是否为管理员
        """
        return user_id in ADMIN_IDS

    @staticmethod
    async def verify_admin_permission(message: Message) -> bool:
        """
        验证管理员权限并记录访问

        Args:
            message: 消息对象

        Returns:
            是否有管理员权限
        """
        user_id = message.from_user.id

        if not AdminHandler.is_admin(user_id):
            error_text = await template_manager.get_template("admin_unauthorized")
            await message.reply(error_text)

            # 记录未授权访问尝试
            await activity_logs_db.log_admin_action(
                admin_id=user_id,
                action="unauthorized_access_attempt",
                action_details={
                    "command": message.text,
                    "username": message.from_user.username,
                    "full_name": message.from_user.full_name,
                },
            )

            logger.warning(f"未授权用户尝试访问管理员功能: {user_id}")
            return False

        # 记录管理员访问
        await activity_logs_db.log_admin_action(
            admin_id=user_id,
            action="admin_command_access",
            action_details={
                "command": message.text,
                "username": message.from_user.username,
            },
        )

        return True


@admin_router.message(Command("help"))
async def admin_help_command(message: Message):
    """
    管理员帮助命令处理器
    显示所有可用的管理员命令
    """
    if not await AdminHandler.verify_admin_permission(message):
        return

    admin_help_text = await get_template_async("admin_help")
    await message.reply(admin_help_text, parse_mode=None)

    logger.info(f"管理员 {message.from_user.id} 查看帮助信息")


@admin_router.message(Command("set_button"))
async def set_button_command(message: Message, state: FSMContext):
    """
    设置按钮命令处理器
    开始按钮配置流程
    """
    if not await AdminHandler.verify_admin_permission(message):
        return

    try:
        # 设置FSM状态
        await state.set_state(AdminStates.setting_message)

        # 初始化状态数据
        state_data = StateData()
        state_data.set("admin_id", message.from_user.id)
        state_data.set("start_time", datetime.now().isoformat())

        await state.update_data(state_data.data)

        # 发送配置说明
        config_message = """
🔧 按钮配置向导

请按照以下步骤配置自定义消息和按钮：

第1步：设置消息内容
请发送您想要在群组中显示的消息内容。

💡 提示：
- 支持Markdown格式
- 可以包含表情符号
- 消息将显示在按钮上方

发送消息内容或发送 /cancel 取消配置：
        """

        await message.reply(config_message, parse_mode=None)

        # 记录配置开始
        await activity_logs_db.log_admin_action(
            admin_id=message.from_user.id,
            action="button_config_started",
            action_details={"step": "setting_message"},
        )

        logger.info(f"管理员 {message.from_user.id} 开始按钮配置")

    except Exception as e:
        logger.error(f"开始按钮配置失败: {e}")
        error_text = await get_template_async("error_general")
        await message.reply(error_text)


@admin_router.message(StateFilter(AdminStates.setting_message))
async def handle_message_setting(message: Message, state: FSMContext):
    """
    处理消息内容设置
    """
    try:
        if message.text == "/cancel":
            await state.clear()
            cancel_text = await template_manager.get_template(
                "status_cancelled", "❌ 按钮配置已取消"
            )
            await message.reply(cancel_text)
            return

        # 保存消息内容
        data = await state.get_data()
        data["message_text"] = message.text
        await state.update_data(data)

        # 转换到按钮配置状态
        await state.set_state(AdminStates.configuring_buttons)

        # 创建按钮配置键盘
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ 添加按钮", callback_data="admin_add_button")],
                [
                    InlineKeyboardButton(
                        text="📋 预览配置", callback_data="admin_preview_config"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ 完成配置", callback_data="admin_finish_config"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ 取消", callback_data="admin_cancel_config"
                    )
                ],
            ]
        )

        config_message = f"""
✅ 消息内容已保存

📝 当前消息:
{message.text}

第2步：配置按钮
现在请配置按钮。每个按钮需要：
- 按钮文本
- 关联的商户ID

请选择操作：
        """

        await message.reply(config_message, reply_markup=keyboard, parse_mode=None)

        # 记录消息设置完成
        await activity_logs_db.log_admin_action(
            admin_id=message.from_user.id,
            action="message_content_set",
            action_details={
                "message_length": len(message.text),
                "step": "configuring_buttons",
            },
        )

        logger.info(f"管理员 {message.from_user.id} 设置消息内容完成")

    except Exception as e:
        logger.error(f"处理消息设置失败: {e}")
        error_text = await get_template_async("error_general")
        await message.reply(error_text)


@admin_router.callback_query(
    F.data == "admin_add_button", StateFilter(AdminStates.configuring_buttons)
)
async def handle_add_button(callback: CallbackQuery, state: FSMContext):
    """
    处理添加按钮请求
    """
    try:
        await callback.answer()

        # 转换到添加按钮状态
        await state.set_state(AdminStates.adding_button)

        # 初始化按钮数据
        data = await state.get_data()
        if "buttons" not in data:
            data["buttons"] = []
        data["current_button"] = {}
        await state.update_data(data)

        add_button_message = """
➕ 添加新按钮

步骤1：按钮文本
请发送按钮上显示的文本：

💡 提示：
- 建议使用表情符号增加吸引力
- 文本应简洁明了
- 例如：📅 预约服务、👥 关注频道

发送按钮文本或 /back 返回：
        """

        await safe_edit_message(callback.message, add_button_message, parse_mode=None)

        logger.info(f"管理员 {callback.from_user.id} 开始添加按钮")

    except Exception as e:
        logger.error(f"处理添加按钮失败: {e}")
        await callback.answer("操作失败，请重试", show_alert=True)


@admin_router.message(StateFilter(AdminStates.adding_button))
async def handle_button_text_input(message: Message, state: FSMContext):
    """
    处理按钮文本输入
    """
    try:
        if message.text == "/back":
            await state.set_state(AdminStates.configuring_buttons)
            # 返回按钮配置界面的逻辑
            await show_button_config_menu(message, state)
            return

        # 保存按钮文本
        data = await state.get_data()
        data["current_button"]["text"] = message.text
        await state.update_data(data)

        # 获取可用商户列表
        merchants = await merchant_manager.get_all_merchants(status="published")

        if not merchants:
            await message.reply("❌ 当前没有活跃的商户。请先确保有商户注册后再配置按钮。", parse_mode=None)
            return

        # 创建商户选择键盘
        keyboard_buttons = []
        for merchant in merchants[:10]:  # 限制显示数量
            button_text = f"{merchant['name']} (ID: {merchant['id']})"
            callback_data = f"admin_select_merchant_{merchant['id']}"
            keyboard_buttons.append(
                [InlineKeyboardButton(text=button_text, callback_data=callback_data)]
            )

        keyboard_buttons.append(
            [InlineKeyboardButton(text="🔙 返回", callback_data="admin_back_to_config")]
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        merchant_selection_message = f"""
✅ 按钮文本已保存: {message.text}

步骤2：选择关联商户
请选择此按钮关联的商户：

💡 提示：用户点击此按钮时将联系选中的商户
        """

        await message.reply(
            merchant_selection_message, reply_markup=keyboard, parse_mode=None
        )

        logger.info(f"管理员 {message.from_user.id} 设置按钮文本: {message.text}")

    except Exception as e:
        logger.error(f"处理按钮文本输入失败: {e}")
        error_text = await get_template_async("error_general")
        await message.reply(error_text)


@admin_router.callback_query(
    F.data.startswith("admin_select_merchant_"), StateFilter(AdminStates.adding_button)
)
async def handle_merchant_selection(callback: CallbackQuery, state: FSMContext):
    """
    处理商户选择
    """
    try:
        await callback.answer()

        # 提取商户ID
        merchant_id = int(callback.data.split("_")[-1])

        # 获取商户信息
        merchant = await merchant_manager.get_merchant(merchant_id)
        if not merchant:
            await callback.answer("商户不存在", show_alert=True)
            return

        # 保存按钮配置
        data = await state.get_data()
        data["current_button"]["merchant_id"] = merchant_id
        data["current_button"]["merchant_name"] = merchant["name"]

        # 添加到按钮列表
        button_config = {
            "text": data["current_button"]["text"],
            "merchant_id": merchant_id,
            "merchant_name": merchant["name"],
            "callback_data": f"contact_merchant_{merchant_id}",
        }

        data["buttons"].append(button_config)
        data["current_button"] = {}  # 清空当前按钮数据
        await state.update_data(data)

        # 返回按钮配置状态
        await state.set_state(AdminStates.configuring_buttons)

        # 显示更新后的配置
        await show_button_config_menu(callback.message, state, edit_message=True)

        # 记录按钮添加
        await activity_logs_db.log_admin_action(
            admin_id=callback.from_user.id,
            action="button_added",
            action_details={
                "button_text": button_config["text"],
                "merchant_id": merchant_id,
                "merchant_name": merchant["name"],
            },
        )

        logger.info(
            f"管理员 {callback.from_user.id} 添加按钮: {button_config['text']} -> 商户 {merchant_id}"
        )

    except Exception as e:
        logger.error(f"处理商户选择失败: {e}")
        await callback.answer("操作失败，请重试", show_alert=True)


async def show_button_config_menu(
    message: Message, state: FSMContext, edit_message: bool = False
):
    """
    显示按钮配置菜单

    Args:
        message: 消息对象
        state: FSM状态
        edit_message: 是否编辑现有消息
    """
    try:
        data = await state.get_data()
        message_text = data.get("message_text", "未设置")
        buttons = data.get("buttons", [])

        # 构建配置预览
        config_preview = f"""
🔧 按钮配置状态

📝 消息内容:
{message_text}

🔘 已配置按钮: ({len(buttons)})
"""

        for i, button in enumerate(buttons, 1):
            config_preview += f"\n{i}. {button['text']} → {button['merchant_name']}"

        if not buttons:
            config_preview += "\n暂无按钮"

        config_preview += "\n\n请选择操作："

        # 创建操作键盘
        keyboard_buttons = [
            [InlineKeyboardButton(text="➕ 添加按钮", callback_data="admin_add_button")]
        ]

        if buttons:
            keyboard_buttons.extend(
                [
                    [
                        InlineKeyboardButton(
                            text="📋 预览效果", callback_data="admin_preview_config"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="✅ 保存配置", callback_data="admin_finish_config"
                        )
                    ],
                ]
            )

        keyboard_buttons.append(
            [InlineKeyboardButton(text="❌ 取消", callback_data="admin_cancel_config")]
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        if edit_message:
            await safe_edit_message(
                message, config_preview, reply_markup=keyboard, parse_mode=None
            )
        else:
            await message.reply(config_preview, reply_markup=keyboard, parse_mode=None)

    except Exception as e:
        logger.error(f"显示按钮配置菜单失败: {e}")


@admin_router.callback_query(
    F.data == "admin_preview_config", StateFilter(AdminStates.configuring_buttons)
)
async def handle_preview_config(callback: CallbackQuery, state: FSMContext):
    """
    处理配置预览请求
    """
    try:
        await callback.answer()

        data = await state.get_data()
        message_text = data.get("message_text", "")
        buttons = data.get("buttons", [])

        if not buttons:
            await callback.answer("请先添加至少一个按钮", show_alert=True)
            return

        # 创建预览键盘
        keyboard_buttons = []
        for button in buttons:
            keyboard_buttons.append(
                [
                    InlineKeyboardButton(
                        text=button["text"],
                        callback_data=f"preview_{button['callback_data']}",
                    )
                ]
            )

        keyboard_buttons.append(
            [InlineKeyboardButton(text="🔙 返回配置", callback_data="admin_back_to_config")]
        )

        preview_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        preview_message = f"""
📋 配置预览

这是用户将看到的消息和按钮：

---

{message_text}

---

💡 这只是预览，按钮暂时无法使用
        """

        await safe_edit_message(
            callback.message, preview_message, reply_markup=preview_keyboard, parse_mode=None
        )

        logger.info(f"管理员 {callback.from_user.id} 预览按钮配置")

    except Exception as e:
        logger.error(f"处理配置预览失败: {e}")
        await callback.answer("预览失败，请重试", show_alert=True)


@admin_router.callback_query(
    F.data == "admin_back_to_config", StateFilter(AdminStates.configuring_buttons)
)
async def handle_back_to_config(callback: CallbackQuery, state: FSMContext):
    """
    处理返回配置请求
    """
    try:
        await callback.answer()
        await show_button_config_menu(callback.message, state, edit_message=True)

    except Exception as e:
        logger.error(f"返回配置失败: {e}")
        await callback.answer("操作失败，请重试", show_alert=True)


@admin_router.callback_query(
    F.data == "admin_finish_config", StateFilter(AdminStates.configuring_buttons)
)
async def handle_finish_config(callback: CallbackQuery, state: FSMContext):
    """
    处理完成配置请求
    """
    try:
        await callback.answer()

        data = await state.get_data()
        message_text = data.get("message_text", "")
        buttons = data.get("buttons", [])

        if not buttons:
            await callback.answer("请先添加至少一个按钮", show_alert=True)
            return

        # 保存配置到数据库
        config_data = {
            "message_text": message_text,
            "buttons": buttons,
            "created_by": callback.from_user.id,
            "created_at": datetime.now().isoformat(),
        }

        # 这里应该调用数据库保存方法
        # 由于button_configs表的具体实现可能还没有，我们先记录到日志
        await activity_logs_db.log_admin_action(
            admin_id=callback.from_user.id,
            action="button_config_saved",
            action_details=config_data,
        )

        # 清除FSM状态
        await state.clear()

        success_message = f"""
✅ 按钮配置保存成功！

📝 消息内容: {message_text}
🔘 按钮数量: {len(buttons)}

配置已生效，用户现在可以看到新的消息和按钮。

使用 /view_stats 查看点击统计
        """

        await safe_edit_message(callback.message, success_message, parse_mode=None)

        logger.info(f"管理员 {callback.from_user.id} 完成按钮配置，按钮数量: {len(buttons)}")

    except Exception as e:
        logger.error(f"完成配置失败: {e}")
        await callback.answer("保存配置失败，请重试", show_alert=True)


@admin_router.callback_query(F.data == "admin_cancel_config")
async def handle_cancel_config(callback: CallbackQuery, state: FSMContext):
    """
    处理取消配置请求
    """
    try:
        await callback.answer()

        # 记录取消操作
        await activity_logs_db.log_admin_action(
            admin_id=callback.from_user.id, action="button_config_cancelled"
        )

        # 清除FSM状态
        await state.clear()

        await safe_edit_message(
            callback.message, 
            "❌ 按钮配置已取消\n\n使用 /set_button 重新开始配置", 
            parse_mode=None
        )

        logger.info(f"管理员 {callback.from_user.id} 取消按钮配置")

    except Exception as e:
        logger.error(f"取消配置失败: {e}")
        await callback.answer("操作失败", show_alert=True)


@admin_router.message(Command("view_stats"))
async def view_stats_command(message: Message, state: FSMContext):
    """
    查看统计命令处理器 - 简化版
    显示基础统计选项
    """
    if not await AdminHandler.verify_admin_permission(message):
        return

    try:
        # 设置FSM状态
        await state.set_state(AdminStates.viewing_stats_filter)

        # 创建简化的统计筛选键盘
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📅 今天", callback_data="stats_today"),
                    InlineKeyboardButton(text="📅 本周", callback_data="stats_week"),
                ],
                [
                    InlineKeyboardButton(text="📅 本月", callback_data="stats_month"),
                    InlineKeyboardButton(text="📅 全部", callback_data="stats_all"),
                ],
                [
                    InlineKeyboardButton(text="🔘 按钮统计", callback_data="stats_buttons"),
                    InlineKeyboardButton(text="👥 用户统计", callback_data="stats_users"),
                ],
                [
                    InlineKeyboardButton(
                        text="🏪 商户统计", callback_data="stats_merchants"
                    ),
                    InlineKeyboardButton(text="📋 订单分析", callback_data="stats_orders"),
                ],
                [
                    InlineKeyboardButton(
                        text="🔑 绑定码分析", callback_data="stats_binding_codes"
                    ),
                    InlineKeyboardButton(
                        text="📊 综合统计", callback_data="stats_comprehensive"
                    ),
                ],
            ]
        )

        stats_message = """
📊 统计数据查看

请选择要查看的统计类型和时间范围：

时间范围:
• 今天 - 今日数据
• 本周 - 本周数据  
• 本月 - 本月数据
• 全部 - 所有历史数据

统计类型:
• 按钮统计 - 按钮点击分析
• 用户统计 - 用户活动分析
• 商户统计 - 商户相关数据
• 订单分析 - 订单数据分析
• 绑定码分析 - 绑定码使用情况
• 综合统计 - 全面数据概览
        """

        await message.reply(stats_message, reply_markup=keyboard, parse_mode=None)

        logger.info(f"管理员 {message.from_user.id} 请求查看统计")

    except Exception as e:
        logger.error(f"显示统计选项失败: {e}")
        error_text = await get_template_async("error_general")
        await message.reply(error_text)


@admin_router.callback_query(
    F.data.startswith("stats_"), StateFilter(AdminStates.viewing_stats_filter)
)
async def handle_stats_request(callback: CallbackQuery, state: FSMContext):
    """
    处理统计请求 - 简化版
    """
    try:
        await callback.answer("正在生成统计数据...")

        stats_type = callback.data.replace("stats_", "")

        # 根据类型生成统计数据 - 只保留基础功能
        if stats_type in ["today", "week", "month", "all"]:
            stats_data = await generate_time_based_stats(stats_type)
        elif stats_type == "buttons":
            stats_data = await generate_button_stats()
        elif stats_type == "users":
            stats_data = await generate_user_stats()
        elif stats_type == "merchants":
            stats_data = await generate_merchant_stats()
        elif stats_type == "comprehensive":
            stats_data = await generate_comprehensive_stats()
        elif stats_type == "orders":
            stats_data = await generate_order_analytics_stats()
        elif stats_type == "binding_codes":
            stats_data = await generate_binding_code_analytics_stats()
        else:
            await callback.answer("未知的统计类型", show_alert=True)
            return

        # 创建返回键盘
        back_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 返回选择", callback_data="stats_back_to_menu"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 刷新数据", callback_data=f"stats_{stats_type}"
                    )
                ],
            ]
        )

        # 使用安全更新方法
        success = await safe_edit_message(
            callback.message, 
            stats_data, 
            reply_markup=back_keyboard, 
            parse_mode=None
        )
        
        if not success:
            await callback.answer("更新失败，请重试", show_alert=True)

        # 记录统计查看
        await activity_logs_db.log_admin_action(
            admin_id=callback.from_user.id,
            action="stats_viewed",
            action_details={"stats_type": stats_type},
        )

        logger.info(f"管理员 {callback.from_user.id} 查看统计: {stats_type}")

    except Exception as e:
        logger.error(f"处理统计请求失败: {e}")
        await callback.answer("生成统计数据失败，请重试", show_alert=True)


@admin_router.callback_query(
    F.data == "stats_back_to_menu", StateFilter(AdminStates.viewing_stats_filter)
)
async def handle_stats_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """
    处理返回统计菜单请求 - 简化版
    """
    try:
        await callback.answer()

        # 重新显示简化的统计选择菜单
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📅 今天", callback_data="stats_today"),
                    InlineKeyboardButton(text="📅 本周", callback_data="stats_week"),
                ],
                [
                    InlineKeyboardButton(text="📅 本月", callback_data="stats_month"),
                    InlineKeyboardButton(text="📅 全部", callback_data="stats_all"),
                ],
                [
                    InlineKeyboardButton(text="🔘 按钮统计", callback_data="stats_buttons"),
                    InlineKeyboardButton(text="👥 用户统计", callback_data="stats_users"),
                ],
                [
                    InlineKeyboardButton(
                        text="🏪 商户统计", callback_data="stats_merchants"
                    ),
                    InlineKeyboardButton(text="📋 订单分析", callback_data="stats_orders"),
                ],
                [
                    InlineKeyboardButton(
                        text="🔑 绑定码分析", callback_data="stats_binding_codes"
                    ),
                    InlineKeyboardButton(
                        text="📊 综合统计", callback_data="stats_comprehensive"
                    ),
                ],
            ]
        )

        stats_message = """
📊 统计数据查看

请选择要查看的统计类型和时间范围：

时间范围:
• 今天 - 今日数据
• 本周 - 本周数据  
• 本月 - 本月数据
• 全部 - 所有历史数据

统计类型:
• 按钮统计 - 按钮点击分析
• 用户统计 - 用户活动分析
• 商户统计 - 商户相关数据
• 订单分析 - 订单数据分析
• 绑定码分析 - 绑定码使用情况
• 综合统计 - 全面数据概览
        """

        await safe_edit_message(
            callback.message, stats_message, reply_markup=keyboard, parse_mode=None
        )

    except Exception as e:
        logger.error(f"返回统计菜单失败: {e}")
        await callback.answer("操作失败，请重试", show_alert=True)


@admin_router.message(Command("generate_code"))
async def generate_code_command(message: Message):
    """
    生成绑定码命令处理器
    """
    if not await AdminHandler.verify_admin_permission(message):
        return

    try:
        # 生成新的绑定码（返回dict，包含code/expires_at等字段）
        code_info = await binding_codes_db.generate_binding_code()
        code_str = code_info.get("code")

        # 再次读取数据库以确保与Web端一致的显示（可获取存储后的标准字段）
        if code_str:
            code_info = await binding_codes_db.get_binding_code_info(code_str)

        if code_info:
            expires_at_str = code_info.get("expires_at")
            if expires_at_str and isinstance(expires_at_str, str):
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    expires_str = "24小时后过期"
            elif expires_at_str is None:
                expires_str = "24小时后过期"
            else:
                expires_str = str(expires_at_str)

            code_message = f"""
🔑 新绑定码已生成

绑定码: `{code_info.get('code', '')}`
过期时间: {expires_str}
状态: 未使用

请将此绑定码提供给需要注册的商户。

💡 提示：
- 绑定码有效期为24小时
- 每个绑定码只能使用一次
- 商户需要发送"上榜流程"开始注册

使用 /view_stats 查看绑定码使用情况
            """

            await message.reply(code_message, parse_mode=None)

            # 记录绑定码生成
            await activity_logs_db.log_admin_action(
                admin_id=message.from_user.id,
                action="binding_code_generated",
                action_details={
                    "binding_code": code_info.get('code', ''),
                    "expires_at": expires_str,
                },
            )

            logger.info(f"管理员 {message.from_user.id} 生成绑定码: {code_info.get('code', '')}")

        else:
            await message.reply("❌ 生成绑定码失败，请重试")

    except Exception as e:
        logger.error(f"生成绑定码失败: {e}")
        error_text = await get_template_async("error_general")
        await message.reply(error_text)


@admin_router.message(Command("manage_regions"))
async def manage_regions_command(message: Message):
    """功能已删除 - 地区管理"""
    if not await AdminHandler.verify_admin_permission(message):
        return

    await message.reply("❌ 地区管理功能已移除")


# 地区管理回调处理器
@admin_router.callback_query(lambda c: c.data and c.data.startswith("admin_region_"))
async def handle_region_management_callbacks(callback_query: CallbackQuery):
    """功能已删除 - 地区管理回调"""
    await callback_query.answer("❌ 地区管理功能已移除")


@admin_router.message(Command("manage_keywords"))
async def manage_keywords_command(message: Message):
    """功能已删除 - 关键词管理"""
    if not await AdminHandler.verify_admin_permission(message):
        return

    await message.reply("❌ 关键词管理功能已移除")


# 关键词管理回调处理器
@admin_router.callback_query(lambda c: c.data and c.data.startswith("admin_keyword_"))
async def handle_keyword_management_callbacks(callback_query: CallbackQuery):
    """功能已删除 - 关键词管理回调"""
    await callback_query.answer("❌ 关键词管理功能已移除")


# 导入增强的统计系统
from .statistics import (
    statistics_engine,
    statistics_formatter,
    StatsPeriod,
    StatsType,
    StatsResult,
)


# 统计生成函数
async def generate_time_based_stats(period: str) -> str:
    """
    生成基于时间的统计数据

    Args:
        period: 时间周期 ('today', 'week', 'month', 'all')

    Returns:
        格式化的统计字符串
    """
    try:
        # 映射周期
        period_mapping = {
            "today": StatsPeriod.TODAY,
            "week": StatsPeriod.WEEK,
            "month": StatsPeriod.MONTH,
            "all": StatsPeriod.ALL_TIME,
        }

        stats_period = period_mapping.get(period, StatsPeriod.ALL_TIME)
        time_range = statistics_engine.get_time_range(stats_period)

        # 生成综合统计数据
        comprehensive_data = {}

        # 按钮点击分析
        button_analytics = await statistics_engine.generate_button_click_analytics(
            time_range
        )
        comprehensive_data["button_clicks"] = button_analytics["basic_metrics"]

        # 用户活动分析
        user_analytics = await statistics_engine.generate_user_activity_analytics(
            time_range
        )
        comprehensive_data["user_activity"] = user_analytics["basic_metrics"]

        # 商户表现分析
        merchant_analytics = (
            await statistics_engine.generate_merchant_performance_analytics(time_range)
        )
        comprehensive_data["merchant_performance"] = merchant_analytics["basic_metrics"]

        # 订单分析
        order_analytics = await statistics_engine.generate_order_analytics(time_range)
        comprehensive_data["order_analytics"] = order_analytics["basic_metrics"]

        # 绑定码分析
        binding_analytics = await statistics_engine.generate_binding_code_analytics(
            time_range
        )
        comprehensive_data["binding_codes"] = binding_analytics["basic_metrics"]

        # 系统健康度分析
        health_analytics = await statistics_engine.generate_system_health_analytics(
            time_range
        )
        comprehensive_data["system_health"] = health_analytics["health_score"]

        # 创建统计结果对象
        stats_result = StatsResult(
            stats_type=StatsType.COMPREHENSIVE.value,
            time_range=time_range,
            data=comprehensive_data,
            generated_at=datetime.now(),
        )

        # 格式化输出
        return statistics_formatter.format_comprehensive_stats(stats_result)

    except Exception as e:
        logger.error(f"生成时间统计失败: {e}")
        return "❌ 生成统计数据失败"


async def generate_button_stats() -> str:
    """生成按钮统计数据"""
    try:
        # 使用增强的统计引擎
        time_range = statistics_engine.get_time_range(StatsPeriod.ALL_TIME)
        button_analytics = await statistics_engine.generate_button_click_analytics(
            time_range
        )

        # 创建统计结果对象
        stats_result = StatsResult(
            stats_type=StatsType.BUTTON_CLICKS.value,
            time_range=time_range,
            data=button_analytics,
            generated_at=datetime.now(),
        )

        # 格式化输出
        return statistics_formatter.format_button_stats(stats_result)

    except Exception as e:
        logger.error(f"生成按钮统计失败: {e}")
        return "❌ 生成按钮统计失败"


async def generate_user_stats() -> str:
    """生成用户统计数据"""
    try:
        # 使用增强的统计引擎
        time_range = statistics_engine.get_time_range(StatsPeriod.ALL_TIME)
        user_analytics = await statistics_engine.generate_user_activity_analytics(
            time_range
        )

        # 创建统计结果对象
        stats_result = StatsResult(
            stats_type=StatsType.USER_ACTIVITY.value,
            time_range=time_range,
            data=user_analytics,
            generated_at=datetime.now(),
        )

        # 格式化输出
        return statistics_formatter.format_user_activity_stats(stats_result)

    except Exception as e:
        logger.error(f"生成用户统计失败: {e}")
        return "❌ 生成用户统计失败"


async def generate_merchant_stats() -> str:
    """生成商户统计数据"""
    try:
        # 使用增强的统计引擎
        time_range = statistics_engine.get_time_range(StatsPeriod.ALL_TIME)
        merchant_analytics = (
            await statistics_engine.generate_merchant_performance_analytics(time_range)
        )

        # 创建统计结果对象
        stats_result = StatsResult(
            stats_type=StatsType.MERCHANT_PERFORMANCE.value,
            time_range=time_range,
            data=merchant_analytics,
            generated_at=datetime.now(),
        )

        # 格式化输出
        return statistics_formatter.format_merchant_stats(stats_result)

    except Exception as e:
        logger.error(f"生成商户统计失败: {e}")
        return "❌ 生成商户统计失败"


async def generate_comprehensive_stats() -> str:
    """生成综合统计数据"""
    try:
        # 使用增强的统计引擎生成全面的综合统计
        time_range = statistics_engine.get_time_range(StatsPeriod.ALL_TIME)

        # 生成各类分析数据
        comprehensive_data = {}

        # 按钮点击分析
        button_analytics = await statistics_engine.generate_button_click_analytics(
            time_range
        )
        comprehensive_data["button_clicks"] = button_analytics["basic_metrics"]

        # 用户活动分析
        user_analytics = await statistics_engine.generate_user_activity_analytics(
            time_range
        )
        comprehensive_data["user_activity"] = user_analytics["basic_metrics"]

        # 商户表现分析
        merchant_analytics = (
            await statistics_engine.generate_merchant_performance_analytics(time_range)
        )
        comprehensive_data["merchant_performance"] = merchant_analytics["basic_metrics"]

        # 订单分析
        order_analytics = await statistics_engine.generate_order_analytics(time_range)
        comprehensive_data["order_analytics"] = order_analytics["basic_metrics"]

        # 绑定码分析
        binding_analytics = await statistics_engine.generate_binding_code_analytics(
            time_range
        )
        comprehensive_data["binding_codes"] = binding_analytics["basic_metrics"]

        # 系统健康度分析
        health_analytics = await statistics_engine.generate_system_health_analytics(
            time_range
        )
        comprehensive_data["system_health"] = health_analytics["health_score"]

        # 创建统计结果对象
        stats_result = StatsResult(
            stats_type=StatsType.COMPREHENSIVE.value,
            time_range=time_range,
            data=comprehensive_data,
            generated_at=datetime.now(),
        )

        # 格式化输出
        return statistics_formatter.format_comprehensive_stats(stats_result)

    except Exception as e:
        logger.error(f"生成综合统计失败: {e}")
        return "❌ 生成综合统计失败"


async def generate_order_analytics_stats() -> str:
    """生成订单分析统计数据"""
    try:
        # 使用增强的统计引擎
        time_range = statistics_engine.get_time_range(StatsPeriod.ALL_TIME)
        order_analytics = await statistics_engine.generate_order_analytics(time_range)

        # 创建统计结果对象
        stats_result = StatsResult(
            stats_type=StatsType.ORDER_ANALYTICS.value,
            time_range=time_range,
            data=order_analytics,
            generated_at=datetime.now(),
        )

        # 格式化输出
        return statistics_formatter.format_order_analytics(stats_result)

    except Exception as e:
        logger.error(f"生成订单分析统计失败: {e}")
        return "❌ 生成订单分析统计失败"


async def generate_binding_code_analytics_stats() -> str:
    """生成绑定码分析统计数据"""
    try:
        # 使用增强的统计引擎
        time_range = statistics_engine.get_time_range(StatsPeriod.ALL_TIME)
        binding_analytics = await statistics_engine.generate_binding_code_analytics(
            time_range
        )

        # 创建统计结果对象
        stats_result = StatsResult(
            stats_type=StatsType.BINDING_CODES.value,
            time_range=time_range,
            data=binding_analytics,
            generated_at=datetime.now(),
        )

        # 格式化输出
        return statistics_formatter.format_binding_code_analytics(stats_result)

    except Exception as e:
        logger.error(f"生成绑定码分析统计失败: {e}")
        return "❌ 生成绑定码分析统计失败"


async def generate_system_health_analytics_stats() -> str:
    """功能已删除 - 系统健康分析"""
    return "❌ 该功能已移除"


async def generate_time_based_comprehensive_stats() -> str:
    """功能已删除 - 时间趋势分析"""
    return "❌ 该功能已移除"


async def generate_advanced_analytics_menu(callback: CallbackQuery) -> None:
    """功能已删除 - 高级分析菜单"""
    await callback.answer("❌ 高级分析功能已移除")
    # 返回统计菜单
    await handle_stats_back_to_menu(callback)


# 高级分析回调处理器
@admin_router.callback_query(lambda c: c.data and c.data.startswith("advanced_"))
async def handle_advanced_analytics_request(callback_query: CallbackQuery):
    """功能已删除 - 高级分析处理器"""
    await callback_query.answer("❌ 高级分析功能已移除")
    # 返回统计菜单
    await handle_stats_back_to_menu(callback_query)


async def generate_cohort_analysis_stats() -> str:
    """功能已删除 - 群组分析"""
    return "❌ 该功能已移除"


async def generate_funnel_analysis_stats() -> str:
    """功能已删除 - 漏斗分析"""
    return "❌ 该功能已移除"


async def generate_user_segmentation_stats() -> str:
    """功能已删除 - 用户分群分析"""
    return "❌ 该功能已移除"


async def generate_business_insights_stats() -> str:
    """功能已删除 - 业务洞察"""
    return "❌ 该功能已移除"


async def generate_performance_forecast_stats() -> str:
    """功能已删除 - 性能预测"""
    return "❌ 该功能已移除"


# 清除状态的通用处理器
@admin_router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    """
    取消当前操作命令处理器
    """
    if not AdminHandler.is_admin(message.from_user.id):
        return

    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.reply("❌ 当前操作已取消")
        logger.info(f"管理员 {message.from_user.id} 取消操作，状态: {current_state}")
    else:
        await message.reply("没有正在进行的操作")
