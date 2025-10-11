"""
频道/群组关注验证模块
实现 aiogram 3.x 标准中间件，基于 system_config 的“频道/群组强制关注”配置进行校验
"""

import json
import logging
from typing import Dict, List, Optional, Any, Callable, Awaitable

from aiogram import Bot, BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, TelegramObject
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

# 导入
from database.db_system_config import system_config_manager
from config import ADMIN_IDS
from utils.template_utils import get_template_async

logger = logging.getLogger(__name__)


class SubscriptionVerificationMiddleware(BaseMiddleware):
    """频道/群组关注验证中间件
    
    在处理用户消息前检查用户是否已关注必需的频道或加入必需的群组。
    基于 system_config 表的动态配置，支持管理员豁免。
    """
    
    def __init__(self):
        """初始化频道订阅验证中间件"""
        super().__init__()
        self._config_cache: Optional[Dict[str, Any]] = None
        logger.info("频道订阅验证中间件初始化完成")
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """中间件主入口点
        
        Args:
            handler: 下一个处理器
            event: Telegram事件对象  
            data: 处理器数据字典
            
        Returns:
            处理器执行结果或None（如果验证失败）
        """
        # 只处理消息和回调查询
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)
            
        # 获取用户信息
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            
        if not user:
            return await handler(event, data)
            
        # 取消 /start 和 /help 放行：首次 /start 也执行订阅校验
        # 如果需要放行，可在此处基于配置开关或白名单恢复

        # 检查是否需要验证
        if not await self.should_verify(user.id):
            return await handler(event, data)
            
        # 执行订阅验证
        bot = data.get('bot')
        if not bot:
            logger.error("Bot实例未找到，跳过订阅验证")
            return await handler(event, data)
            
        is_verified = await self.check_user_subscriptions(user.id, bot)
        
        if not is_verified:
            # 验证失败，发送提醒并中断处理
            # 对回调查询的特殊处理：若是“我已加入/重新检测”，给出针对性提示
            if isinstance(event, CallbackQuery):
                data_str = (event.data or '') if hasattr(event, 'data') else ''
                if data_str == 'subscription_check':
                    await event.answer("❌ 仍未检测到加入，请稍后再试", show_alert=True)
                    return None
                else:
                    await event.answer("❌ 请先关注必需频道后再试", show_alert=True)
                    return None

            # 普通消息：发送模板化的验证提示
            if isinstance(event, Message):
                await self._send_verification_failure_message(event)
                return None
            
        # 验证通过
        # 对“我已加入”检测按钮，直接给出成功提示并结束回调
        if isinstance(event, CallbackQuery):
            data_str = (event.data or '') if hasattr(event, 'data') else ''
            if data_str == 'subscription_check':
                try:
                    await event.answer("✅ 已检测到订阅，感谢加入！", show_alert=True)
                except Exception:
                    pass
                return None

        # 继续处理
        return await handler(event, data)
    
    async def _get_config(self) -> Dict[str, Any]:
        """从系统配置获取订阅/群组验证配置
        
        Returns:
            配置字典，包含enabled和required_subscriptions字段
        """
        try:
            # 使用 SystemConfigManager获取配置
            config = await system_config_manager.get_config(
                'subscription_verification_config', 
                {"enabled": False, "required_subscriptions": []}
            )
            
            logger.debug(f"频道订阅验证配置: enabled={config.get('enabled')}, channels={len(config.get('required_subscriptions', []))}")
            return config
                
        except Exception as e:
            logger.error(f"获取频道订阅验证配置失败: {e}")
            # 返回安全的默认配置
            return {"enabled": False, "required_subscriptions": []}
    
    async def should_verify(self, user_id: int) -> bool:
        """检查是否应该进行订阅验证
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: True需要验证，False无需验证
        """
        # 管理员豁免检查
        if user_id in ADMIN_IDS:
            logger.debug(f"管理员用户 {user_id} 豁免频道订阅验证")
            return False
            
        config = await self._get_config()
        enabled = config.get("enabled", False)
        has_channels = len(config.get("required_subscriptions", [])) > 0
        
        result = enabled and has_channels
        logger.debug(f"用户 {user_id} 频道订阅验证决策: enabled={enabled}, has_channels={has_channels}, result={result}")
        return result
    
    async def check_user_subscriptions(self, user_id: int, bot: Bot) -> bool:
        """检查用户频道订阅状态
        
        Args:
            user_id: 用户ID
            bot: Bot实例
            
        Returns:
            bool: True表示验证通过，False表示需要订阅
        """
        if not await self.should_verify(user_id):
            return True
            
        config = await self._get_config()
        
        # 检查每个必需的订阅
        subscription_results = []
        for subscription in config.get("required_subscriptions", []):
            is_subscribed = await self._check_single_subscription(
                bot, user_id, subscription
            )
            subscription_results.append({
                "subscription": subscription,
                "is_subscribed": is_subscribed
            })
        
        # 判断是否全部通过
        all_subscribed = all(result["is_subscribed"] for result in subscription_results)
        
        if all_subscribed:
            logger.info(f"用户 {user_id} 频道订阅验证通过")
        else:
            failed_channels = [r["subscription"]["display_name"] for r in subscription_results if not r["is_subscribed"]]
            logger.info(f"用户 {user_id} 频道订阅验证失败，未订阅: {failed_channels}")
        
        return all_subscribed
    
    async def _check_single_subscription(
        self, bot: Bot, user_id: int, subscription: Dict[str, Any]
    ) -> bool:
        """检查用户在单个频道/群组的订阅状态
        
        Args:
            bot: Bot实例
            user_id: 用户ID
            subscription: 频道配置字典
            
        Returns:
            bool: 是否已订阅
        """
        try:
            chat_id = subscription.get("chat_id")
            if not chat_id:
                logger.warning(f"订阅项缺少chat_id: {subscription}")
                return False
            
            # 调用Telegram API检查成员状态
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            
            # 检查用户状态是否为有效订阅状态
            valid_statuses = ["member", "administrator", "creator"]
            is_subscribed = member.status in valid_statuses
            
            logger.debug(f"用户 {user_id} 在频道 {chat_id} 的状态: {member.status}, 订阅状态: {is_subscribed}")
            return is_subscribed
            
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.warning(f"检查订阅失败 - 用户: {user_id}, 频道: {subscription.get('chat_id')}, 错误: {e}")
            # API调用失败时默认认为未订阅
            return False
        except Exception as e:
            logger.error(f"检查订阅时发生未知错误: {e}")
            return False
    
    async def _send_verification_failure_message(self, message: Message) -> None:
        """发送验证失败提醒消息
        
        Args:
            message: 用户消息对象
        """
        try:
            config = await self._get_config()
            subscriptions = config.get("required_subscriptions", [])

            # 渲染模板文本（从 templates 表获取，可在 Web -> 模板管理编辑）
            # 模板键：subscription_verification_prompt
            # 可用变量：channels_text（如：1. 名称\n2. 名称...）
            channels_lines = []
            for i, sub in enumerate(subscriptions, 1):
                display_name = sub.get("display_name", f"频道{i}")
                channels_lines.append(f"{i}. {display_name}")
            channels_text = "\n".join(channels_lines) if channels_lines else "（未配置频道）"

            try:
                message_text = await get_template_async(
                    "subscription_verification_prompt",
                    channels_text=channels_text
                )
            except Exception:
                # 若模板缺失，退回到简易提示（避免打断流程）
                message_text = (
                    f"❌ 使用功能前需要先关注以下频道或加入群组：\n\n{channels_text}\n\n"
                    f"关注/加入完成后点击下方“✅ 我已加入”进行检测。"
                )

            # 构建键盘：每个频道一个“加入”按钮 + 一个“✅ 我已加入”
            keyboard_rows = []
            for i, subscription in enumerate(subscriptions, 1):
                display_name = subscription.get("display_name", f"频道{i}")
                join_link = subscription.get("join_link")
                if join_link:
                    keyboard_rows.append([
                        InlineKeyboardButton(text=f"加入 {display_name}", url=join_link)
                    ])

            # 追加“我已加入”检测按钮
            keyboard_rows.append([
                InlineKeyboardButton(text="✅ 我已加入", callback_data="subscription_check")
            ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows) if keyboard_rows else None

            # 发送消息
            await message.answer(text=message_text, reply_markup=keyboard)
            logger.info(f"已向用户 {message.from_user.id} 发送频道订阅提醒")
            
        except Exception as e:
            logger.error(f"发送频道订阅提醒消息失败: {e}")
            # 发送简单的提醒消息作为fallback
            await message.answer("❌ 您需要先关注必需的频道才能使用机器人功能")


# 创建全局中间件实例
subscription_middleware = SubscriptionVerificationMiddleware()


# 向后兼容的包装函数（保留原有接口）
class SubscriptionGuard:
    """向后兼容的订阅守卫类"""
    
    def __init__(self):
        self._middleware = subscription_middleware
    
    async def check_user_subscriptions(self, message: Message) -> bool:
        """兼容性方法：检查用户订阅状态"""
        if not message.from_user:
            return True
            
        return await self._middleware.check_user_subscriptions(
            message.from_user.id, 
            message.bot
        )
    
    async def should_verify(self) -> bool:
        """兼容性方法：检查是否应该验证（简化版）"""
        config = await self._middleware._get_config()
        return (config.get("enabled", False) 
                and len(config.get("required_subscriptions", [])) > 0)


# 创建向后兼容实例
subscription_guard = SubscriptionGuard()
