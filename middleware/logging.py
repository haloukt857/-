"""
日志记录中间件
记录用户交互、性能指标和系统事件
"""

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional
from datetime import datetime

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from database.db_logs import ActivityLogsDatabase
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    """
    日志记录中间件
    
    特性:
    - 记录所有用户交互
    - 性能监控和指标收集
    - 错误事件追踪
    - 管理员操作审计
    """
    
    def __init__(self, db: ActivityLogsDatabase):
        """
        初始化日志中间件
        
        Args:
            db: 日志数据库实例
        """
        self.db = db
        self.start_time = time.time()
        self.total_requests = 0
        self.error_count = 0
        
        logger.info("日志记录中间件初始化完成")
    
    def _get_user_info(self, event: TelegramObject) -> Dict[str, Any]:
        """
        提取用户信息
        
        Args:
            event: Telegram事件对象
            
        Returns:
            用户信息字典
        """
        user_info = {
            "user_id": None,
            "username": None,
            "first_name": None,
            "last_name": None,
            "is_admin": False
        }
        
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
            if user:
                user_info.update({
                    "user_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_admin": user.id in ADMIN_IDS
                })
        
        return user_info
    
    def _get_event_details(self, event: TelegramObject) -> Dict[str, Any]:
        """
        提取事件详细信息
        
        Args:
            event: Telegram事件对象
            
        Returns:
            事件详情字典
        """
        details = {
            "event_type": type(event).__name__,
            "chat_id": None,
            "message_text": None,
            "callback_data": None,
            "file_info": None
        }
        
        if isinstance(event, Message):
            details.update({
                "chat_id": event.chat.id,
                "message_text": event.text,
                "content_type": event.content_type,
                "chat_type": event.chat.type
            })
            
            # 检查附件信息
            if event.photo:
                details["file_info"] = f"photo:{len(event.photo)} sizes"
            elif event.document:
                details["file_info"] = f"document:{event.document.file_name}"
            elif event.voice:
                details["file_info"] = f"voice:{event.voice.duration}s"
                
        elif isinstance(event, CallbackQuery):
            details.update({
                "callback_data": event.data,
                "chat_id": event.message.chat.id if event.message else None,
                "message_text": event.message.text if event.message else None
            })
        
        return details
    
    async def _log_interaction(
        self, 
        user_info: Dict[str, Any], 
        event_details: Dict[str, Any],
        processing_time: float,
        error: Optional[str] = None
    ):
        """
        记录用户交互到数据库
        
        Args:
            user_info: 用户信息
            event_details: 事件详情
            processing_time: 处理时间
            error: 错误信息（可选）
        """
        try:
            # 确定操作类型
            if event_details["callback_data"]:
                if event_details["callback_data"].startswith("region_"):
                    action_type = "region_selection"
                elif event_details["callback_data"].startswith("cat_"):
                    action_type = "category_selection"  
                elif event_details["callback_data"].startswith("service_"):
                    action_type = "service_selection"
                elif event_details["callback_data"].startswith("stats_"):
                    action_type = "admin_stats"
                else:
                    action_type = "button_click"
            elif event_details["message_text"]:
                if event_details["message_text"].startswith("/"):
                    action_type = "command"
                elif "上榜流程" in event_details["message_text"]:
                    action_type = "merchant_registration"
                else:
                    action_type = "message"
            else:
                action_type = "other"
            
            # 构建详情字符串
            details = []
            if event_details["callback_data"]:
                details.append(f"callback:{event_details['callback_data']}")
            if event_details["message_text"]:
                # 截断长消息
                text = event_details["message_text"][:100]
                if len(event_details["message_text"]) > 100:
                    text += "..."
                details.append(f"text:{text}")
            if event_details["file_info"]:
                details.append(f"file:{event_details['file_info']}")
            if processing_time > 1.0:
                details.append(f"slow:{processing_time:.2f}s")
            if error:
                details.append(f"error:{error[:200]}")
            
            # 记录到数据库
            await self.db.log_user_interaction(
                user_id=user_info["user_id"],
                action=action_type,
                details={
                    "chat_id": event_details["chat_id"],
                    "details": " | ".join(details) if details else "no_details"
                }
            )
            
        except Exception as e:
            logger.error(f"记录用户交互失败: {e}")
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """中间件主要逻辑"""
        
        start_time = time.time()
        self.total_requests += 1
        
        # 提取用户和事件信息
        user_info = self._get_user_info(event)
        event_details = self._get_event_details(event)
        
        # 记录请求开始
        logger.info(
            f"处理请求 - 用户:{user_info['user_id']} "
            f"类型:{event_details['event_type']} "
            f"聊天:{event_details['chat_id']}"
        )
        
        error_msg = None
        result = None
        
        try:
            # 执行处理器
            result = await handler(event, data)
            
        except Exception as e:
            self.error_count += 1
            error_msg = str(e)
            logger.error(f"处理请求时发生错误: {e}", exc_info=True)
            raise
            
        finally:
            # 计算处理时间
            processing_time = time.time() - start_time
            
            # 异步记录交互（不阻塞主流程）
            if user_info["user_id"]:
                asyncio.create_task(
                    self._log_interaction(
                        user_info, 
                        event_details, 
                        processing_time,
                        error_msg
                    )
                )
            
            # 记录性能日志
            level = logging.WARNING if processing_time > 2.0 else logging.INFO
            logger.log(
                level,
                f"请求完成 - 用户:{user_info['user_id']} "
                f"时间:{processing_time:.3f}s "
                f"错误:{'是' if error_msg else '否'}"
            )
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取中间件统计信息
        
        Returns:
            统计信息字典
        """
        uptime = time.time() - self.start_time
        
        return {
            "uptime_seconds": uptime,
            "total_requests": self.total_requests,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.total_requests, 1),
            "requests_per_second": self.total_requests / max(uptime, 1),
            "start_time": datetime.fromtimestamp(self.start_time).isoformat()
        }