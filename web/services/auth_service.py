# -*- coding: utf-8 -*-
"""
认证服务
从app.py.old中提取的认证业务逻辑，提供统一的认证管理服务
"""

import hashlib
import logging
import secrets
from typing import Dict, Any, Optional
from starlette.requests import Request

# 导入配置
from config import WEB_CONFIG, ADMIN_IDS

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务类"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希处理"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """验证密码"""
        return hashlib.sha256(password.encode()).hexdigest() == hashed
    
    @staticmethod
    def is_admin_session(request: Request) -> bool:
        """检查是否为管理员会话"""
        return request.session.get('is_admin', False)
    
    @staticmethod
    def get_admin_id(request: Request) -> Optional[int]:
        """获取当前管理员ID"""
        if AuthService.is_admin_session(request):
            return request.session.get('admin_id')
        return None
    
    @staticmethod
    def login_admin(request: Request, admin_id: int) -> bool:
        """管理员登录"""
        if admin_id in ADMIN_IDS:
            request.session['is_admin'] = True
            request.session['admin_id'] = admin_id
            logger.info(f"管理员登录成功: admin_id={admin_id}")
            return True
        logger.warning(f"无效的管理员登录尝试: admin_id={admin_id}")
        return False
    
    @staticmethod
    def logout(request: Request) -> None:
        """登出"""
        admin_id = request.session.get('admin_id')
        request.session.clear()
        logger.info(f"管理员登出: admin_id={admin_id}")
    
    @staticmethod
    async def authenticate_admin(request: Request, password: str) -> Dict[str, Any]:
        """
        使用密码进行认证
        
        Returns:
            dict: 认证结果
                - success: bool 认证是否成功
                - admin_id: int 管理员ID (认证成功时)
                - message: str 认证消息
        """
        try:
            # 验证管理员密码
            admin_password = WEB_CONFIG.get("admin_password", "admin123")
            
            if AuthService.verify_password(password, AuthService.hash_password(admin_password)):
                # 使用默认管理员ID
                admin_id = ADMIN_IDS[0] if ADMIN_IDS else 1
                
                # 设置登录会话
                AuthService.login_admin(request, admin_id)
                
                return {
                    'success': True,
                    'admin_id': admin_id,
                    'message': '认证成功'
                }
            else:
                return {
                    'success': False,
                    'message': '密码错误'
                }
                
        except Exception as e:
            logger.error(f"认证过程中发生错误: {e}")
            return {
                'success': False,
                'message': '认证服务异常'
            }
    
    @staticmethod
    def get_or_create_csrf_token(request: Request) -> str:
        """获取或创建CSRF令牌"""
        token = request.session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            request.session["csrf_token"] = token
        return token
    
    @staticmethod
    def validate_csrf_token(request: Request, token: str) -> bool:
        """验证CSRF令牌"""
        expected = request.session.get("csrf_token")
        return bool(expected and token and secrets.compare_digest(str(token), str(expected)))
    
    @staticmethod
    async def get_session_info(request: Request) -> Dict[str, Any]:
        """获取会话信息"""
        try:
            is_admin = AuthService.is_admin_session(request)
            admin_id = AuthService.get_admin_id(request) if is_admin else None
            csrf_token = AuthService.get_or_create_csrf_token(request)
            
            return {
                'is_authenticated': is_admin,
                'admin_id': admin_id,
                'csrf_token': csrf_token,
                'session_data': {
                    key: value for key, value in request.session.items()
                    if key != 'csrf_token'  # 排除敏感信息
                }
            }
            
        except Exception as e:
            logger.error(f"获取会话信息失败: {e}")
            return {
                'is_authenticated': False,
                'admin_id': None,
                'csrf_token': None,
                'session_data': {},
                'error': str(e)
            }
    
    @staticmethod
    async def validate_admin_permissions(request: Request, required_permissions: Optional[list] = None) -> Dict[str, Any]:
        """
        验证管理员权限
        
        Args:
            request: 请求对象
            required_permissions: 需要的权限列表 (未来扩展用)
            
        Returns:
            dict: 权限验证结果
        """
        try:
            if not AuthService.is_admin_session(request):
                return {
                    'valid': False,
                    'message': '未登录或会话已过期',
                    'redirect_url': '/login'
                }
            
            admin_id = AuthService.get_admin_id(request)
            if admin_id not in ADMIN_IDS:
                return {
                    'valid': False,
                    'message': '权限不足',
                    'redirect_url': '/login'
                }
            
            # 未来可以在这里添加更细粒度的权限检查
            # if required_permissions:
            #     user_permissions = await get_user_permissions(admin_id)
            #     if not all(perm in user_permissions for perm in required_permissions):
            #         return {'valid': False, 'message': '权限不足'}
            
            return {
                'valid': True,
                'admin_id': admin_id,
                'message': '权限验证通过'
            }
            
        except Exception as e:
            logger.error(f"权限验证失败: {e}")
            return {
                'valid': False,
                'message': '权限验证服务异常',
                'error': str(e)
            }


# 为了保持向后兼容，提供原始的认证管理器类
class AuthManager(AuthService):
    """
    向后兼容的认证管理器
    实际功能由AuthService提供
    """
    pass