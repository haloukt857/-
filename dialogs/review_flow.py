# -*- coding: utf-8 -*-
"""
评价流程处理器
实现完整的双向评价系统：用户评价 -> 商家确认 -> 积分奖励闭环

OPERATION REVIEW FLOW - 核心实现
"""

import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from aiogram import Router, F, Bot

# 导入工具函数
from utils.telegram_helpers import safe_edit_message
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# 项目模块导入
from config import ADMIN_IDS
from database.db_reviews import ReviewManager
from database.db_users import UserManager
from database.db_orders import OrderManager
from database.db_merchants import MerchantManager
from database.db_system_config import SystemConfigManager

logger = logging.getLogger(__name__)

# 创建评价流程路由器
review_router = Router()


class ReviewStates(StatesGroup):
    """评价流程FSM状态组"""
    
    # 用户评价阶段
    awaiting_rating = State()          # 等待用户评分
    awaiting_text_review = State()     # 等待用户文字评价
    
    # 商家确认阶段
    merchant_confirming = State()      # 商家确认评价有效性


class ReviewFlowManager:
    """评价流程管理器 - 核心业务协调器"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        
    async def trigger_review_flow(self, order_id: int, merchant_id: int, customer_user_id: int) -> bool:
        """
        触发评价流程 - 订单完成后的入口点
        
        Args:
            order_id: 订单ID
            merchant_id: 商家ID (永久ID)
            customer_user_id: 用户ID (Telegram ID)
            
        Returns:
            bool: 流程启动是否成功
        """
        try:
            # 验证订单状态
            order = await OrderManager.get_order(order_id)
            if not order or order['status'] != 'completed':
                logger.error(f"订单状态无效，无法启动评价流程: order_id={order_id}, status={order.get('status') if order else 'None'}")
                return False
            
            # 检查是否已经评价过
            existing_review = await ReviewManager.get_review_by_order_id(order_id)
            if existing_review:
                logger.warning(f"订单已存在评价记录: order_id={order_id}")
                return False
            
            # 获取商家信息
            merchant = await MerchantManager.get_merchant(merchant_id)
            if not merchant:
                logger.error(f"商家不存在: merchant_id={merchant_id}")
                return False
            
            # 启动用户评价FSM
            await self._start_user_rating_flow(order_id, merchant_id, customer_user_id, merchant['name'])
            
            logger.info(f"评价流程启动成功: order_id={order_id}, merchant_id={merchant_id}, user_id={customer_user_id}")
            return True
            
        except Exception as e:
            logger.error(f"启动评价流程失败: {e}")
            return False
    
    async def _start_user_rating_flow(self, order_id: int, merchant_id: int, customer_user_id: int, merchant_name: str):
        """启动用户评价流程"""
        try:
            # 构建评价界面
            keyboard = self._build_rating_keyboard()
            
            message_text = f"""
🌟 服务体验评价

您刚完成了与 **{merchant_name}** 的服务订单。
请为本次服务进行评价：

📊 **请选择各维度的评分** (1-10分)：
• 颜值外观 • 身材体型 • 服务质量 • 服务态度 • 环境条件

点击下方按钮开始评分 👇
            """
            
            # 发送评价消息
            sent_message = await self.bot.send_message(
                chat_id=customer_user_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # TODO: 在实际项目中，这里需要设置FSM状态
            # state = FSMContext(...)
            # await state.set_state(ReviewStates.awaiting_rating)
            # await state.update_data(order_id=order_id, merchant_id=merchant_id, merchant_name=merchant_name)
            
            logger.info(f"用户评价界面已发送: user_id={customer_user_id}")
            
        except Exception as e:
            logger.error(f"启动用户评价流程失败: {e}")
            
    def _build_rating_keyboard(self) -> InlineKeyboardMarkup:
        """构建评分键盘"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌟 开始评价", callback_data="review_start_rating")
            ]
        ])
        return keyboard
    
    def _build_dimension_rating_keyboard(self, dimension: str) -> InlineKeyboardMarkup:
        """构建单维度评分键盘"""
        buttons = []
        # 创建1-10分按钮，每行5个
        for i in range(2):
            row = []
            for j in range(5):
                score = i * 5 + j + 1
                if score <= 10:
                    callback_data = f"rating_{dimension}_{score}"
                    row.append(InlineKeyboardButton(text=f"{score}", callback_data=callback_data))
            buttons.append(row)
        
        # 添加跳过按钮
        buttons.append([InlineKeyboardButton(text="⏭️ 跳过此项", callback_data=f"rating_{dimension}_skip")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    async def notify_merchant_for_confirmation(self, review_id: int, order_id: int, merchant_id: int, ratings: Dict[str, int], text_review: str = None) -> bool:
        """通知商家确认评价"""
        try:
            # 获取商家信息
            merchant = await MerchantManager.get_merchant(merchant_id)
            if not merchant:
                logger.error(f"商家不存在: merchant_id={merchant_id}")
                return False
            
            # 获取订单信息
            order = await OrderManager.get_order(order_id)
            if not order:
                logger.error(f"订单不存在: order_id={order_id}")
                return False
            
            # 计算平均分
            avg_rating = sum(ratings.values()) / len(ratings)
            
            # 构建确认消息
            message_text = f"""
📝 **收到新的服务评价**

**订单信息：**
订单编号：#{order_id}
服务价格：{order.get('price', 'N/A')}
完成时间：{order.get('completed_at', 'N/A')}

**评价详情：**
• 颜值外观：{ratings.get('appearance', 'N/A')}/10
• 身材体型：{ratings.get('figure', 'N/A')}/10  
• 服务质量：{ratings.get('service', 'N/A')}/10
• 服务态度：{ratings.get('attitude', 'N/A')}/10
• 环境条件：{ratings.get('environment', 'N/A')}/10

**综合评分：{avg_rating:.1f}/10**
            """
            
            if text_review:
                message_text += f"\n**文字评价：**\n{text_review}\n"
            
            message_text += "\n请确认此评价的真实性："
            
            # 构建确认键盘
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ 确认真实有效", callback_data=f"confirm_review_{review_id}"),
                    InlineKeyboardButton(text="❌ 存在问题", callback_data=f"dispute_review_{review_id}")
                ]
            ])
            
            # 发送给商家
            merchant_chat_id = merchant['telegram_chat_id']
            await self.bot.send_message(
                chat_id=merchant_chat_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            logger.info(f"商家确认通知已发送: merchant_id={merchant_id}, review_id={review_id}")
            return True
            
        except Exception as e:
            logger.error(f"发送商家确认通知失败: {e}")
            return False
    
    async def process_merchant_confirmation(self, review_id: int, merchant_id: int, confirmed: bool) -> bool:
        """处理商家确认结果"""
        try:
            if not confirmed:
                # 商家标记存在问题，需要人工介入
                logger.warning(f"商家标记评价存在问题: review_id={review_id}")
                await self._handle_disputed_review(review_id, merchant_id)
                return False
            
            # 商家确认评价有效
            success = await ReviewManager.confirm_review(review_id)
            if not success:
                logger.error(f"确认评价失败: review_id={review_id}")
                return False
            
            # 获取评价详情
            review = await ReviewManager.get_review_details(review_id)
            if not review:
                logger.error(f"获取评价详情失败: review_id={review_id}")
                return False
            
            # 触发积分奖励流程
            await self._process_review_rewards(review['customer_user_id'], review_id, review)
            
            # 发送报告到频道
            await self._send_review_report_to_channel(review)
            
            # 通知商家确认成功
            await self._notify_merchant_confirmation_success(merchant_id, review_id)
            
            # 通知用户获得奖励
            await self._notify_user_rewards(review['customer_user_id'], review_id)
            
            logger.info(f"评价确认流程完成: review_id={review_id}")
            return True
            
        except Exception as e:
            logger.error(f"处理商家确认失败: {e}")
            return False
    
    async def _process_review_rewards(self, user_id: int, review_id: int, review: Dict[str, Any]):
        """处理评价奖励"""
        try:
            # 获取积分配置
            points_config = await SystemConfigManager.get_config('points_config', {
                'review_completion': 50,
                'review_xp': 20
            })
            
            # 发放积分和经验
            reward_points = points_config.get('review_completion', 50)
            reward_xp = points_config.get('review_xp', 20)
            
            success = await UserManager.grant_rewards(
                user_id=user_id,
                points=reward_points,
                xp=reward_xp,
                reason=f"完成服务评价 (评价ID: {review_id})"
            )
            
            if success:
                logger.info(f"评价奖励发放成功: user_id={user_id}, points={reward_points}, xp={reward_xp}")
            else:
                logger.error(f"评价奖励发放失败: user_id={user_id}")
                
        except Exception as e:
            logger.error(f"处理评价奖励失败: {e}")
    
    async def _send_review_report_to_channel(self, review: Dict[str, Any]):
        """发送评价报告到频道"""
        try:
            # 获取报告频道ID
            channel_id = await SystemConfigManager.get_config('report_channel_id')
            if not channel_id:
                logger.warning("未配置报告频道ID，跳过频道报告")
                return
            
            # 构建报告消息
            ratings_text = f"""
📊 **服务评价报告**

**商家：** {review.get('merchant_name', 'N/A')}
**订单：** #{review['order_id']}
**用户：** @{review.get('customer_username', '匿名用户')}

**评分详情：**
• 颜值外观：{review['rating_appearance']}/10
• 身材体型：{review['rating_figure']}/10
• 服务质量：{review['rating_service']}/10
• 服务态度：{review['rating_attitude']}/10
• 环境条件：{review['rating_environment']}/10

**综合评分：** {(review['rating_appearance'] + review['rating_figure'] + review['rating_service'] + review['rating_attitude'] + review['rating_environment'])/5:.1f}/10
            """
            
            if review.get('text_review_by_user'):
                ratings_text += f"\n**用户评价：**\n{review['text_review_by_user']}"
            
            ratings_text += f"\n\n⏰ 评价时间：{review['created_at']}"
            
            await self.bot.send_message(
                chat_id=channel_id,
                text=ratings_text,
                parse_mode="Markdown"
            )
            
            logger.info(f"评价报告已发送到频道: review_id={review['id']}")
            
        except Exception as e:
            logger.error(f"发送频道报告失败: {e}")
    
    async def _notify_merchant_confirmation_success(self, merchant_id: int, review_id: int):
        """通知商家确认成功"""
        try:
            merchant = await MerchantManager.get_merchant(merchant_id)
            if not merchant:
                return
            
            message_text = f"""
✅ **评价确认成功**

您已成功确认评价 #{review_id} 的真实性。
该评价将计入您的服务评分统计。

感谢您维护平台的评价质量！
            """
            
            await self.bot.send_message(
                chat_id=merchant['telegram_chat_id'],
                text=message_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"通知商家确认成功失败: {e}")
    
    async def _notify_user_rewards(self, user_id: int, review_id: int):
        """通知用户获得奖励"""
        try:
            # 获取用户当前状态
            user = await UserManager.get_user(user_id)
            if not user:
                return
            
            message_text = f"""
🎉 **评价奖励已发放**

您的服务评价已被商家确认为真实有效！

**奖励详情：**
• 积分 +50
• 经验值 +20
• 当前等级：{user.get('level_name', '新手')}
• 总积分：{user.get('points', 0)}

感谢您的宝贵评价，继续使用我们的服务吧！
            """
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"通知用户奖励失败: {e}")
    
    async def _handle_disputed_review(self, review_id: int, merchant_id: int):
        """处理争议评价"""
        try:
            # 发送给管理员处理
            for admin_id in ADMIN_IDS:
                message_text = f"""
⚠️ **评价争议报告**

商家对评价 #{review_id} 提出异议。
请及时介入处理此争议。

/review_dispute_{review_id} 查看详情
                """
                
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message_text,
                    parse_mode="Markdown"
                )
            
            logger.info(f"评价争议已报告给管理员: review_id={review_id}")
            
        except Exception as e:
            logger.error(f"处理评价争议失败: {e}")


# =============================================================================
# 回调处理器注册
# =============================================================================

review_flow_manager = None  # 全局实例，需要在bot初始化时设置


@review_router.callback_query(F.data == "review_start_rating")
async def handle_start_rating(callback: CallbackQuery, state: FSMContext):
    """处理开始评价回调"""
    try:
        await callback.answer()
        
        # 获取状态数据
        data = await state.get_data()
        order_id = data.get('order_id')
        merchant_id = data.get('merchant_id')
        merchant_name = data.get('merchant_name')
        
        if not all([order_id, merchant_id]):
            await safe_edit_message(callback.message, "❌ 评价数据异常，请联系客服")
            return
        
        # 开始第一个维度评分
        await _show_dimension_rating(callback.message, "appearance", "颜值外观", state)
        
    except Exception as e:
        logger.error(f"处理开始评价失败: {e}")
        await safe_edit_message(callback.message, "❌ 系统错误，请稍后重试")


async def _show_dimension_rating(message: Message, dimension: str, dimension_name: str, state: FSMContext):
    """显示单维度评分界面"""
    try:
        text = f"""
🌟 **{dimension_name}评分**

请为本次服务的 **{dimension_name}** 进行评分：

选择 1-10 分 (1分最低，10分最高)
        """
        
        keyboard = review_flow_manager._build_dimension_rating_keyboard(dimension)
        
        await safe_edit_message(message, text=text, reply_markup=keyboard, parse_mode="Markdown")
        await state.set_state(ReviewStates.awaiting_rating)
        await state.update_data(current_dimension=dimension)
        
    except Exception as e:
        logger.error(f"显示维度评分界面失败: {e}")


@review_router.callback_query(F.data.startswith("rating_"))
async def handle_rating_callback(callback: CallbackQuery, state: FSMContext):
    """处理评分回调"""
    try:
        await callback.answer()
        
        # 解析回调数据
        parts = callback.data.split('_')
        if len(parts) < 3:
            return
        
        dimension = parts[1]
        score_str = parts[2]
        
        # 获取当前数据
        data = await state.get_data()
        ratings = data.get('ratings', {})
        
        # 记录评分
        if score_str != "skip":
            try:
                score = int(score_str)
                ratings[dimension] = score
            except ValueError:
                return
        
        await state.update_data(ratings=ratings)
        
        # 确定下一个维度
        dimensions = [
            ("appearance", "颜值外观"),
            ("figure", "身材体型"), 
            ("service", "服务质量"),
            ("attitude", "服务态度"),
            ("environment", "环境条件")
        ]
        
        current_index = next((i for i, (d, _) in enumerate(dimensions) if d == dimension), -1)
        
        if current_index < len(dimensions) - 1:
            # 继续下一个维度
            next_dimension, next_name = dimensions[current_index + 1]
            await _show_dimension_rating(callback.message, next_dimension, next_name, state)
        else:
            # 所有维度完成，询问文字评价
            await _show_text_review_prompt(callback.message, state)
        
    except Exception as e:
        logger.error(f"处理评分回调失败: {e}")


async def _show_text_review_prompt(message: Message, state: FSMContext):
    """显示文字评价提示"""
    try:
        text = """
📝 **文字评价 (可选)**

您已完成所有维度的评分！
是否愿意分享更详细的服务体验？

文字评价将帮助其他用户更好地了解服务质量。
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 写评价", callback_data="review_write_text"),
                InlineKeyboardButton(text="⏭️ 跳过", callback_data="review_skip_text")
            ]
        ])
        
        await safe_edit_message(message, text=text, reply_markup=keyboard, parse_mode="Markdown")
        await state.set_state(ReviewStates.awaiting_text_review)
        
    except Exception as e:
        logger.error(f"显示文字评价提示失败: {e}")


@review_router.callback_query(F.data.in_(["review_write_text", "review_skip_text"]))
async def handle_text_review_choice(callback: CallbackQuery, state: FSMContext):
    """处理文字评价选择"""
    try:
        await callback.answer()
        
        if callback.data == "review_write_text":
            # 等待用户输入文字评价
            await safe_edit_message(callback.message, 
                "📝 请输入您的文字评价 (50-500字)：",
                parse_mode="Markdown"
            )
            # 保持在当前状态，等待文本消息
        else:
            # 跳过文字评价，直接提交
            await _submit_review(callback.message, state, text_review=None)
        
    except Exception as e:
        logger.error(f"处理文字评价选择失败: {e}")


@review_router.message(ReviewStates.awaiting_text_review)
async def handle_text_review_input(message: Message, state: FSMContext):
    """处理文字评价输入"""
    try:
        text_review = message.text.strip()
        
        # 验证文字长度
        if len(text_review) < 10:
            await message.reply("📝 评价内容太短，请至少输入10个字符")
            return
        
        if len(text_review) > 500:
            await message.reply("📝 评价内容太长，请控制在500字以内")
            return
        
        await _submit_review(message, state, text_review=text_review)
        
    except Exception as e:
        logger.error(f"处理文字评价输入失败: {e}")


async def _submit_review(message: Message, state: FSMContext, text_review: Optional[str] = None):
    """提交评价到数据库"""
    try:
        # 获取所有数据
        data = await state.get_data()
        order_id = data.get('order_id')
        merchant_id = data.get('merchant_id')
        ratings = data.get('ratings', {})
        customer_user_id = message.from_user.id
        
        if not all([order_id, merchant_id, ratings]):
            await message.reply("❌ 评价数据不完整，请重新开始")
            return
        
        # 提交评价到数据库
        review_id = await ReviewManager.create_review(
            order_id=order_id,
            merchant_id=merchant_id,
            customer_user_id=customer_user_id,
            ratings=ratings,
            text_review=text_review
        )
        
        if not review_id:
            await message.reply("❌ 评价提交失败，请联系客服")
            return
        
        # 发送成功消息
        await message.reply(
            "✅ **评价提交成功**\n\n您的评价已发送给商家确认。\n确认后将为您发放积分奖励！",
            parse_mode="Markdown"
        )
        
        # 通知商家确认
        if review_flow_manager:
            await review_flow_manager.notify_merchant_for_confirmation(
                review_id=review_id,
                order_id=order_id,
                merchant_id=merchant_id,
                ratings=ratings,
                text_review=text_review
            )
        
        # 清除状态
        await state.clear()
        
        logger.info(f"评价提交成功: review_id={review_id}, order_id={order_id}")
        
    except Exception as e:
        logger.error(f"提交评价失败: {e}")
        await message.reply("❌ 系统错误，请稍后重试")


@review_router.callback_query(F.data.startswith("confirm_review_"))
async def handle_merchant_confirmation(callback: CallbackQuery):
    """处理商家确认评价"""
    try:
        await callback.answer("正在处理确认...")
        
        # 解析评价ID
        review_id = int(callback.data.split('_')[-1])
        merchant_id = callback.from_user.id
        
        # 验证商家权限
        merchant = await MerchantManager.get_merchant_by_chat_id(merchant_id)
        if not merchant:
            await safe_edit_message(callback.message, "❌ 您没有商家权限")
            return
        
        # 处理确认
        if review_flow_manager:
            success = await review_flow_manager.process_merchant_confirmation(
                review_id=review_id,
                merchant_id=merchant['id'],
                confirmed=True
            )
            
            if success:
                await safe_edit_message(callback.message, "✅ 评价确认成功！用户奖励已发放。")
            else:
                await safe_edit_message(callback.message, "❌ 确认处理失败，请联系管理员")
        
    except Exception as e:
        logger.error(f"处理商家确认失败: {e}")
        await safe_edit_message(callback.message, "❌ 系统错误，请稍后重试")


@review_router.callback_query(F.data.startswith("dispute_review_"))
async def handle_merchant_dispute(callback: CallbackQuery):
    """处理商家争议评价"""
    try:
        await callback.answer("已报告争议...")
        
        # 解析评价ID
        review_id = int(callback.data.split('_')[-1])
        merchant_id = callback.from_user.id
        
        # 验证商家权限
        merchant = await MerchantManager.get_merchant_by_chat_id(merchant_id)
        if not merchant:
            await safe_edit_message(callback.message, "❌ 您没有商家权限")
            return
        
        # 处理争议
        if review_flow_manager:
            await review_flow_manager._handle_disputed_review(review_id, merchant['id'])
            await safe_edit_message(callback.message, "⚠️ 争议已报告，管理员将及时处理")
        
    except Exception as e:
        logger.error(f"处理争议评价失败: {e}")
        await safe_edit_message(callback.message, "❌ 系统错误，请稍后重试")


# =============================================================================
# 外部API接口
# =============================================================================

async def initialize_review_flow(bot: Bot):
    """初始化评价流程管理器"""
    global review_flow_manager
    review_flow_manager = ReviewFlowManager(bot)
    logger.info("评价流程管理器初始化完成")


async def trigger_review_flow_from_order_completion(order_id: int) -> bool:
    """
    订单完成触发评价流程的外部接口
    
    Args:
        order_id: 完成的订单ID
        
    Returns:
        bool: 流程启动是否成功
    """
    try:
        if not review_flow_manager:
            logger.error("评价流程管理器未初始化")
            return False
        
        # 获取订单信息
        order = await OrderManager.get_order(order_id)
        if not order:
            logger.error(f"订单不存在: order_id={order_id}")
            return False
        
        # 启动评价流程
        return await review_flow_manager.trigger_review_flow(
            order_id=order_id,
            merchant_id=order['merchant_id'],
            customer_user_id=order['customer_user_id']
        )
        
    except Exception as e:
        logger.error(f"从订单完成触发评价流程失败: {e}")
        return False