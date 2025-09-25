"""
安全管理器
提供输入验证、速率限制、访问控制和安全监控功能
"""

import os
import sys
import re
import hashlib
import hmac
import secrets
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)


class SecurityManager:
    """安全管理器"""
    
    def __init__(self):
        """初始化安全管理器"""
        # 访问控制
        self.blocked_users: Set[int] = set()
        self.admin_sessions: Dict[int, datetime] = {}
        self.failed_login_attempts: Dict[str, List[datetime]] = defaultdict(list)
        
        # 速率限制跟踪
        self.request_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.suspicious_activity: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        
        # 安全配置
        self.max_login_attempts = 5
        self.login_attempt_window = timedelta(minutes=15)
        self.admin_session_timeout = timedelta(hours=2)
        self.max_message_length = 4000
        self.max_requests_per_minute = 60
        
        # 恶意模式检测
        self.malicious_patterns = [
            re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
            re.compile(r'javascript:', re.IGNORECASE),
            re.compile(r'on\w+\s*=', re.IGNORECASE),
            re.compile(r'eval\s*\(', re.IGNORECASE),
            re.compile(r'union\s+select', re.IGNORECASE),
            re.compile(r'drop\s+table', re.IGNORECASE),
            re.compile(r'delete\s+from', re.IGNORECASE),
            re.compile(r'\.\./|\.\.\\\|\.\.%2f', re.IGNORECASE),
        ]
        
        # 敏感信息模式
        self.sensitive_patterns = [
            re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),  # 信用卡号
            re.compile(r'\b\d{15,18}\b'),  # 身份证号
            re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),  # 邮箱
            re.compile(r'\b(?:\+86)?1[3-9]\d{9}\b'),  # 手机号
        ]
        
        logger.info("安全管理器初始化完成")
    
    def validate_input(self, text: str, input_type: str = "general") -> Dict[str, Any]:
        """
        验证输入内容
        
        Args:
            text: 输入文本
            input_type: 输入类型 (general, username, password, message等)
            
        Returns:
            验证结果字典
        """
        result = {
            "valid": True,
            "sanitized_text": text,
            "warnings": [],
            "blocked_reasons": []
        }
        
        try:
            # 1. 基础验证
            if not text or not isinstance(text, str):
                result["valid"] = False
                result["blocked_reasons"].append("输入为空或类型错误")
                return result
            
            # 2. 长度检查
            if len(text) > self.max_message_length:
                result["valid"] = False
                result["blocked_reasons"].append(f"输入长度超限 ({len(text)} > {self.max_message_length})")
                return result
            
            # 3. 恶意模式检测
            for pattern in self.malicious_patterns:
                if pattern.search(text):
                    result["valid"] = False
                    result["blocked_reasons"].append(f"检测到恶意模式: {pattern.pattern[:50]}")
                    logger.warning(f"恶意输入检测: {text[:100]}")
                    return result
            
            # 4. 敏感信息检测
            for pattern in self.sensitive_patterns:
                if pattern.search(text):
                    result["warnings"].append("输入包含敏感信息")
                    # 脱敏处理
                    result["sanitized_text"] = pattern.sub("***", text)
            
            # 5. 特定类型验证
            if input_type == "username":
                if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fff]+$', text):
                    result["warnings"].append("用户名包含特殊字符")
            
            elif input_type == "command":
                if not text.startswith('/'):
                    result["warnings"].append("命令格式不正确")
            
            # 6. HTML标签清理
            result["sanitized_text"] = self._sanitize_html(result["sanitized_text"])
            
        except Exception as e:
            logger.error(f"输入验证异常: {e}")
            result["valid"] = False
            result["blocked_reasons"].append(f"验证异常: {str(e)}")
        
        return result
    
    def _sanitize_html(self, text: str) -> str:
        """清理HTML标签"""
        try:
            # 移除HTML标签
            clean_text = re.sub(r'<[^>]+>', '', text)
            
            # 解码HTML实体
            html_entities = {
                '&lt;': '<',
                '&gt;': '>',
                '&amp;': '&',
                '&quot;': '"',
                '&#x27;': "'",
                '&#x2F;': '/',
            }
            
            for entity, char in html_entities.items():
                clean_text = clean_text.replace(entity, char)
            
            return clean_text
            
        except Exception as e:
            logger.warning(f"HTML清理失败: {e}")
            return text
    
    def check_rate_limit(self, user_id: int, action: str = "general") -> Dict[str, Any]:
        """
        检查速率限制
        
        Args:
            user_id: 用户ID
            action: 动作类型
            
        Returns:
            限制检查结果
        """
        now = datetime.now()
        result = {
            "allowed": True,
            "remaining": self.max_requests_per_minute,
            "reset_time": None,
            "blocked_until": None
        }
        
        try:
            # 获取用户请求历史
            user_requests = self.request_history[user_id]
            
            # 清理过期请求
            cutoff_time = now - timedelta(minutes=1)
            while user_requests and user_requests[0] < cutoff_time:
                user_requests.popleft()
            
            # 检查当前请求数
            current_requests = len(user_requests)
            
            if current_requests >= self.max_requests_per_minute:
                result["allowed"] = False
                result["remaining"] = 0
                result["blocked_until"] = (user_requests[0] + timedelta(minutes=1)).isoformat()
                
                # 记录可疑活动
                self._record_suspicious_activity(user_id, "rate_limit_exceeded", {
                    "requests_count": current_requests,
                    "action": action
                })
                
                logger.warning(f"用户 {user_id} 触发速率限制: {current_requests} 请求/分钟")
            else:
                # 记录请求
                user_requests.append(now)
                result["remaining"] = self.max_requests_per_minute - current_requests - 1
                result["reset_time"] = (now + timedelta(minutes=1)).isoformat()
        
        except Exception as e:
            logger.error(f"速率限制检查异常: {e}")
            # 异常时允许请求，但记录日志
            result["allowed"] = True
        
        return result
    
    def authenticate_admin_session(self, user_id: int, password: str) -> Dict[str, Any]:
        """
        验证管理员会话
        
        Args:
            user_id: 用户ID  
            password: 密码
            
        Returns:
            认证结果
        """
        result = {
            "authenticated": False,
            "session_token": None,
            "expires_at": None,
            "blocked": False
        }
        
        try:
            # 检查是否被阻止
            if self._is_login_blocked(str(user_id)):
                result["blocked"] = True
                result["message"] = "登录尝试过多，请稍后重试"
                return result
            
            # 验证密码
            expected_password = os.getenv("WEB_ADMIN_PASSWORD")
            if not expected_password or not self._verify_password(password, expected_password):
                self._record_failed_login(str(user_id))
                result["message"] = "密码错误"
                return result
            
            # 生成会话令牌
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + self.admin_session_timeout
            
            # 存储会话
            self.admin_sessions[user_id] = expires_at
            
            result.update({
                "authenticated": True,
                "session_token": session_token,
                "expires_at": expires_at.isoformat(),
                "message": "认证成功"
            })
            
            logger.info(f"管理员 {user_id} 认证成功")
            
        except Exception as e:
            logger.error(f"管理员认证异常: {e}")
            result["message"] = "认证过程发生错误"
        
        return result
    
    def validate_admin_session(self, user_id: int) -> bool:
        """验证管理员会话是否有效"""
        try:
            if user_id not in self.admin_sessions:
                return False
            
            expires_at = self.admin_sessions[user_id]
            if datetime.now() > expires_at:
                del self.admin_sessions[user_id]
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"会话验证异常: {e}")
            return False
    
    def _is_login_blocked(self, identifier: str) -> bool:
        """检查登录是否被阻止"""
        if identifier not in self.failed_login_attempts:
            return False
        
        attempts = self.failed_login_attempts[identifier]
        cutoff_time = datetime.now() - self.login_attempt_window
        
        # 清理过期尝试
        attempts[:] = [attempt for attempt in attempts if attempt > cutoff_time]
        
        return len(attempts) >= self.max_login_attempts
    
    def _record_failed_login(self, identifier: str):
        """记录失败的登录尝试"""
        self.failed_login_attempts[identifier].append(datetime.now())
        logger.warning(f"登录失败: {identifier}")
    
    def _verify_password(self, provided: str, expected: str) -> bool:
        """安全密码验证"""
        try:
            # 简单的密码比较（生产环境应该使用哈希）
            return hmac.compare_digest(provided.encode(), expected.encode())
        except Exception:
            return False
    
    def _record_suspicious_activity(self, user_id: int, activity_type: str, details: Dict[str, Any]):
        """记录可疑活动"""
        try:
            activity = {
                "type": activity_type,
                "timestamp": datetime.now().isoformat(),
                "details": details
            }
            
            self.suspicious_activity[user_id].append(activity)
            
            # 保留最近50条记录
            if len(self.suspicious_activity[user_id]) > 50:
                self.suspicious_activity[user_id] = self.suspicious_activity[user_id][-50:]
            
            logger.warning(f"可疑活动记录 - 用户: {user_id}, 类型: {activity_type}")
            
        except Exception as e:
            logger.error(f"记录可疑活动失败: {e}")
    
    def block_user(self, user_id: int, reason: str = "安全违规"):
        """阻止用户"""
        self.blocked_users.add(user_id)
        self._record_suspicious_activity(user_id, "user_blocked", {"reason": reason})
        logger.warning(f"用户 {user_id} 已被阻止: {reason}")
    
    def unblock_user(self, user_id: int):
        """解除用户阻止"""
        self.blocked_users.discard(user_id)
        logger.info(f"用户 {user_id} 已解除阻止")
    
    def is_user_blocked(self, user_id: int) -> bool:
        """检查用户是否被阻止"""
        return user_id in self.blocked_users
    
    def get_security_summary(self) -> Dict[str, Any]:
        """获取安全状况摘要"""
        try:
            now = datetime.now()
            
            # 统计活跃会话
            active_sessions = sum(
                1 for expires_at in self.admin_sessions.values()
                if expires_at > now
            )
            
            # 统计最近的可疑活动
            recent_suspicious = 0
            for activities in self.suspicious_activity.values():
                recent_suspicious += sum(
                    1 for activity in activities
                    if datetime.fromisoformat(activity["timestamp"]) > now - timedelta(hours=24)
                )
            
            return {
                "timestamp": now.isoformat(),
                "blocked_users_count": len(self.blocked_users),
                "active_admin_sessions": active_sessions,
                "failed_login_attempts_count": sum(
                    len(attempts) for attempts in self.failed_login_attempts.values()
                ),
                "recent_suspicious_activity": recent_suspicious,
                "total_users_tracked": len(self.request_history),
                "security_patterns_count": len(self.malicious_patterns),
                "status": "healthy" if recent_suspicious < 10 else "alert"
            }
            
        except Exception as e:
            logger.error(f"获取安全摘要失败: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def validate_telegram_webhook(self, token: str, data: bytes, signature: str) -> bool:
        """验证Telegram Webhook签名"""
        try:
            expected_signature = hmac.new(
                token.encode(),
                data,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Webhook签名验证失败: {e}")
            return False
    
    def clean_expired_data(self):
        """清理过期数据"""
        try:
            now = datetime.now()
            
            # 清理过期的管理员会话
            expired_sessions = [
                user_id for user_id, expires_at in self.admin_sessions.items()
                if expires_at <= now
            ]
            for user_id in expired_sessions:
                del self.admin_sessions[user_id]
            
            # 清理过期的失败登录记录
            cutoff_time = now - self.login_attempt_window
            for identifier in list(self.failed_login_attempts.keys()):
                attempts = self.failed_login_attempts[identifier]
                attempts[:] = [attempt for attempt in attempts if attempt > cutoff_time]
                if not attempts:
                    del self.failed_login_attempts[identifier]
            
            # 清理过期的可疑活动记录
            activity_cutoff = now - timedelta(days=7)
            for user_id in list(self.suspicious_activity.keys()):
                activities = self.suspicious_activity[user_id]
                activities[:] = [
                    activity for activity in activities
                    if datetime.fromisoformat(activity["timestamp"]) > activity_cutoff
                ]
                if not activities:
                    del self.suspicious_activity[user_id]
            
            logger.info("安全数据清理完成")
            
        except Exception as e:
            logger.error(f"清理安全数据失败: {e}")


# 全局安全管理器实例
security_manager = SecurityManager()