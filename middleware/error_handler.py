"""
错误处理中间件
提供统一的错误处理、用户友好的错误消息和错误恢复机制
"""

import asyncio
import logging
import traceback
from typing import Any, Awaitable, Callable, Dict, Optional
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramServerError

from config import MESSAGE_TEMPLATES, ADMIN_IDS

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseMiddleware):
    """
    错误处理中间件
    
    特性:
    - 统一错误处理和恢复
    - 用户友好的错误消息
    - 管理员错误通知
    - 重试机制和降级处理
    """
    
    def __init__(self, notify_admins: bool = True, max_retries: int = 3):
        """
        初始化错误处理中间件
        
        Args:
            notify_admins: 是否通知管理员严重错误
            max_retries: 最大重试次数
        """
        self.notify_admins = notify_admins
        self.max_retries = max_retries
        
        # 错误统计
        self.error_counts = {}
        self.last_error_notification = {}
        self.notification_cooldown = 300  # 5分钟冷却期
        
        logger.info(f"错误处理中间件初始化完成 - 管理员通知:{'开启' if notify_admins else '关闭'}")
    
    def _classify_error(self, error: Exception) -> str:
        """
        分类错误类型
        
        Args:
            error: 异常对象
            
        Returns:
            错误分类字符串
        """
        if isinstance(error, TelegramRetryAfter):
            return "rate_limit"
        elif isinstance(error, TelegramBadRequest):
            return "bad_request"
        elif isinstance(error, TelegramServerError):
            return "server_error"
        elif isinstance(error, asyncio.TimeoutError):
            return "timeout"
        elif isinstance(error, ConnectionError):
            return "connection"
        elif isinstance(error, PermissionError):
            return "permission"
        elif isinstance(error, ValueError):
            return "validation"
        else:
            return "unknown"
    
    def _get_user_friendly_message(self, error_type: str, error: Exception) -> str:
        """
        获取用户友好的错误消息
        
        Args:
            error_type: 错误类型
            error: 异常对象
            
        Returns:
            用户友好的错误消息
        """
        messages = {
            "rate_limit": "⏰ 请求过于频繁，请稍后再试。",
            "bad_request": "❌ 请求格式有误，请重新操作。",
            "server_error": "🔧 服务器暂时出现问题，请稍后重试。",
            "timeout": "⏱️ 操作超时，请重新尝试。",
            "connection": "📡 网络连接异常，请检查网络后重试。",
            "permission": "🚫 权限不足，无法执行此操作。",
            "validation": "📝 输入格式不正确，请检查后重新输入。",
            "unknown": MESSAGE_TEMPLATES.get("error_general", "❌ 出现了未知错误，请稍后重试。")
        }
        
        # 对于特定错误，添加更详细的信息
        if error_type == "rate_limit" and isinstance(error, TelegramRetryAfter):
            return f"⏰ 请求过于频繁，请等待 {error.retry_after} 秒后重试。"
        
        return messages.get(error_type, messages["unknown"])
    
    async def _notify_admin_if_needed(self, error: Exception, user_id: Optional[int], context: str):
        """
        在需要时通知管理员
        
        Args:
            error: 异常对象
            user_id: 用户ID
            context: 错误上下文
        """
        if not self.notify_admins or not ADMIN_IDS:
            return
        
        error_type = self._classify_error(error)
        
        # 只对严重错误发送通知
        if error_type not in ["server_error", "unknown", "connection"]:
            return
        
        # 检查冷却期
        now = datetime.now()
        last_notification = self.last_error_notification.get(error_type)
        
        if (last_notification and 
            now - last_notification < timedelta(seconds=self.notification_cooldown)):
            return
        
        # 构建管理员通知消息
        error_msg = f"""
🚨 系统错误报告

⏰ 时间: {now.strftime('%Y-%m-%d %H:%M:%S')}
👤 用户: {user_id or '未知'}
🔍 类型: {error_type}
📍 上下文: {context}
❌ 错误: {str(error)[:500]}

请检查系统状态并采取必要措施。
        """
        
        # 发送给所有管理员（异步，不阻塞主流程）
        for admin_id in ADMIN_IDS:
            try:
                # 这里需要bot实例，实际使用时从data中获取
                # await bot.send_message(admin_id, error_msg, parse_mode="Markdown")
                logger.warning(f"需要通知管理员 {admin_id}: {error_msg}")
            except Exception as e:
                logger.error(f"通知管理员失败: {e}")
        
        # 更新通知时间
        self.last_error_notification[error_type] = now
    
    async def _send_error_response(self, event: TelegramObject, message: str):
        """
        向用户发送错误响应
        
        Args:
            event: Telegram事件对象
            message: 错误消息
        """
        try:
            if isinstance(event, Message):
                await event.reply(message)
            elif isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
        except Exception as e:
            logger.error(f"发送错误响应失败: {e}")
    
    async def _handle_retry_after(self, error: TelegramRetryAfter, event: TelegramObject):
        """
        处理速率限制错误
        
        Args:
            error: 速率限制异常
            event: Telegram事件对象
        """
        wait_time = error.retry_after
        logger.warning(f"遇到速率限制，需要等待 {wait_time} 秒")
        
        # 通知用户等待时间
        await self._send_error_response(
            event, 
            f"⏰ 请求过于频繁，请等待 {wait_time} 秒后重试。"
        )
        
        # 如果等待时间合理，可以自动重试
        if wait_time <= 5:
            logger.info(f"自动等待 {wait_time} 秒后重试")
            await asyncio.sleep(wait_time)
            return True  # 表示可以重试
        
        return False  # 等待时间过长，不重试
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """中间件主要逻辑"""
        
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
        
        # 获取上下文信息
        context = f"{type(event).__name__}"
        if isinstance(event, Message) and event.text:
            context += f":{event.text[:50]}"
        elif isinstance(event, CallbackQuery) and event.data:
            context += f":{event.data}"
        
        retry_count = 0
        
        while retry_count <= self.max_retries:
            try:
                # 执行处理器
                result = await handler(event, data)
                return result
                
            except TelegramRetryAfter as e:
                # 处理速率限制
                logger.warning(f"用户 {user_id} 触发速率限制: {e}")
                
                # 尝试自动处理
                should_retry = await self._handle_retry_after(e, event)
                if should_retry and retry_count < self.max_retries:
                    retry_count += 1
                    continue
                else:
                    break
                    
            except TelegramBadRequest as e:
                # 客户端请求错误，通常不需要重试
                logger.warning(f"用户 {user_id} 发送了无效请求: {e}")
                await self._send_error_response(
                    event, 
                    self._get_user_friendly_message("bad_request", e)
                )
                break
                
            except TelegramServerError as e:
                # 服务器错误，可以重试
                logger.error(f"Telegram服务器错误: {e}")
                
                if retry_count < self.max_retries:
                    retry_count += 1
                    wait_time = min(2 ** retry_count, 10)  # 指数退避，最大10秒
                    logger.info(f"等待 {wait_time} 秒后重试 (第 {retry_count} 次)")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    await self._send_error_response(
                        event, 
                        self._get_user_friendly_message("server_error", e)
                    )
                    await self._notify_admin_if_needed(e, user_id, context)
                    break
                    
            except Exception as e:
                # 其他未预期的错误
                error_type = self._classify_error(e)
                logger.error(f"未处理的错误 - 用户:{user_id} 类型:{error_type} 错误:{e}", exc_info=True)
                
                # 统计错误
                self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
                
                # 发送用户友好消息
                await self._send_error_response(
                    event, 
                    self._get_user_friendly_message(error_type, e)
                )
                
                # 通知管理员
                await self._notify_admin_if_needed(e, user_id, context)
                
                # 对于某些错误类型可以重试
                if error_type in ["timeout", "connection"] and retry_count < self.max_retries:
                    retry_count += 1
                    wait_time = min(2 ** retry_count, 5)
                    logger.info(f"连接错误，等待 {wait_time} 秒后重试 (第 {retry_count} 次)")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    break
        
        return None
    
    def get_error_stats(self) -> Dict[str, Any]:
        """
        获取错误统计信息
        
        Returns:
            错误统计字典
        """
        total_errors = sum(self.error_counts.values())
        
        return {
            "total_errors": total_errors,
            "error_breakdown": dict(self.error_counts),
            "last_notifications": {
                error_type: timestamp.isoformat() 
                for error_type, timestamp in self.last_error_notification.items()
            },
            "notification_cooldown": self.notification_cooldown,
            "max_retries": self.max_retries
        }