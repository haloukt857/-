"""
限流中间件
防止用户频繁操作，避免触发Telegram API限制
"""

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from config import ADMIN_IDS

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    """
    限流中间件
    
    特性:
    - 按用户ID限制操作频率
    - 管理员免疫限流
    - 可配置的限流规则
    - 自动清理过期记录
    """
    
    def __init__(
        self,
        default_rate: float = 1.0,  # 默认每秒允许的操作次数
        default_burst: int = 3,      # 默认突发请求数
        admin_rate: float = 10.0,    # 管理员限制（更宽松）
        cleanup_interval: int = 300   # 清理间隔（秒）
    ):
        """
        初始化限流中间件
        
        Args:
            default_rate: 普通用户每秒允许的操作次数
            default_burst: 普通用户允许的突发请求数
            admin_rate: 管理员每秒允许的操作次数
            cleanup_interval: 清理过期记录的间隔
        """
        self.default_rate = default_rate
        self.default_burst = default_burst
        self.admin_rate = admin_rate
        self.cleanup_interval = cleanup_interval
        
        # 用户操作记录: {user_id: [timestamp1, timestamp2, ...]}
        self.user_requests: Dict[int, list] = defaultdict(list)
        
        # 最后清理时间
        self.last_cleanup = time.time()
        
        # 自定义限流规则: {user_id: (rate, burst)}
        self.custom_rules: Dict[int, tuple] = {}
        
        logger.info(f"限流中间件初始化完成 - 默认限制: {default_rate}/s, 突发: {default_burst}")
    
    def get_user_limits(self, user_id: int) -> tuple:
        """
        获取用户的限流参数
        
        Args:
            user_id: 用户ID
            
        Returns:
            (rate, burst) 元组
        """
        # 管理员特殊处理
        if user_id in ADMIN_IDS:
            return self.admin_rate, self.default_burst * 2
        
        # 自定义规则
        if user_id in self.custom_rules:
            return self.custom_rules[user_id]
        
        # 默认规则
        return self.default_rate, self.default_burst
    
    def set_user_limit(self, user_id: int, rate: float, burst: int):
        """
        为特定用户设置自定义限流规则
        
        Args:
            user_id: 用户ID
            rate: 每秒允许的操作次数
            burst: 突发请求数
        """
        self.custom_rules[user_id] = (rate, burst)
        logger.info(f"为用户 {user_id} 设置自定义限流: {rate}/s, 突发: {burst}")
    
    def remove_user_limit(self, user_id: int):
        """
        移除用户的自定义限流规则
        
        Args:
            user_id: 用户ID
        """
        if user_id in self.custom_rules:
            del self.custom_rules[user_id]
            logger.info(f"移除用户 {user_id} 的自定义限流规则")
    
    def is_rate_limited(self, user_id: int) -> tuple[bool, Optional[float]]:
        """
        检查用户是否被限流
        
        Args:
            user_id: 用户ID
            
        Returns:
            (是否被限流, 建议等待时间)
        """
        current_time = time.time()
        rate, burst = self.get_user_limits(user_id)
        
        # 获取用户请求记录
        user_requests = self.user_requests[user_id]
        
        # 清理过期请求（超过1秒的请求）
        cutoff_time = current_time - 1.0
        user_requests[:] = [req_time for req_time in user_requests if req_time > cutoff_time]
        
        # 检查突发限制
        if len(user_requests) >= burst:
            # 计算需要等待的时间
            oldest_request = min(user_requests)
            wait_time = 1.0 - (current_time - oldest_request)
            return True, max(0, wait_time)
        
        # 检查频率限制
        if len(user_requests) > 0:
            time_since_last = current_time - user_requests[-1]
            min_interval = 1.0 / rate
            
            if time_since_last < min_interval:
                wait_time = min_interval - time_since_last
                return True, wait_time
        
        # 记录此次请求
        user_requests.append(current_time)
        
        return False, None
    
    def cleanup_old_records(self):
        """清理过期的用户请求记录"""
        current_time = time.time()
        
        # 只有达到清理间隔才执行
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        # 清理超过5分钟的记录
        cutoff_time = current_time - 300
        users_to_remove = []
        
        for user_id, requests in self.user_requests.items():
            # 过滤掉过期请求
            requests[:] = [req_time for req_time in requests if req_time > cutoff_time]
            
            # 如果用户没有任何请求记录，标记删除
            if not requests:
                users_to_remove.append(user_id)
        
        # 删除空记录
        for user_id in users_to_remove:
            del self.user_requests[user_id]
        
        self.last_cleanup = current_time
        
        if users_to_remove:
            logger.debug(f"清理了 {len(users_to_remove)} 个过期用户记录")
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """中间件主要逻辑"""
        
        # 获取用户ID
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None
        
        # 如果无法获取用户ID，直接通过
        if user_id is None:
            return await handler(event, data)
        
        # 定期清理过期记录
        self.cleanup_old_records()
        
        # 对媒体上传（photo/video/相册）放行，不进行限流，避免一次性发送多媒体被提示过快
        if isinstance(event, Message):
            try:
                if getattr(event, 'media_group_id', None) is not None:
                    return await handler(event, data)
                if getattr(event, 'photo', None) or getattr(event, 'video', None):
                    return await handler(event, data)
            except Exception:
                pass

        # 检查限流
        is_limited, wait_time = self.is_rate_limited(user_id)
        
        if is_limited:
            # 记录限流事件
            logger.warning(f"用户 {user_id} 被限流，建议等待 {wait_time:.2f}s")
            
            # 根据事件类型回复限流消息
            if isinstance(event, Message):
                try:
                    await event.answer(
                        f"⏰ 操作过于频繁，请等待 {wait_time:.1f} 秒后再试。",
                        show_alert=False
                    )
                except Exception as e:
                    logger.error(f"发送限流消息失败: {e}")
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer(
                        f"⏰ 操作过于频繁，请等待 {wait_time:.1f} 秒后再试。",
                        show_alert=True
                    )
                except Exception as e:
                    logger.error(f"回复限流回调失败: {e}")
            
            # 不继续处理请求
            return
        
        # 继续处理请求
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(f"处理请求时发生错误: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取限流统计信息
        
        Returns:
            统计信息字典
        """
        current_time = time.time()
        active_users = 0
        total_requests = 0
        
        # 统计活跃用户和总请求数
        for user_id, requests in self.user_requests.items():
            if requests:
                active_users += 1
                total_requests += len(requests)
        
        return {
            "active_users": active_users,
            "total_requests": total_requests,
            "custom_rules_count": len(self.custom_rules),
            "default_rate": self.default_rate,
            "default_burst": self.default_burst,
            "admin_rate": self.admin_rate,
            "last_cleanup": self.last_cleanup,
            "cleanup_interval": self.cleanup_interval
        }
