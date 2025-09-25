"""
管理员权限检查模块
提供灵活的权限管理和访问控制功能
"""

import logging
from typing import List, Dict, Set, Optional, Callable, Any
from functools import wraps
from telegram import Update, User
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class Permission:
    """权限定义"""
    
    # 超级管理员权限
    SUPER_ADMIN = "super_admin"
    
    # 地区管理权限
    REGION_MANAGE = "region_manage"
    REGION_VIEW = "region_view"
    PROVINCE_MANAGE = "province_manage"
    CITY_MANAGE = "city_manage"
    
    # 关键词管理权限
    KEYWORD_MANAGE = "keyword_manage"
    KEYWORD_VIEW = "keyword_view"
    
    # 商家管理权限
    MERCHANT_MANAGE = "merchant_manage"
    MERCHANT_VIEW = "merchant_view"
    MERCHANT_APPROVE = "merchant_approve"
    
    # 系统管理权限
    SYSTEM_CONFIG = "system_config"
    DATABASE_ACCESS = "database_access"
    USER_MANAGE = "user_manage"
    
    # 统计查看权限
    STATS_VIEW = "stats_view"


class AdminPermissions:
    """管理员权限管理系统"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self._permission_cache: Dict[int, Set[str]] = {}
        self._role_permissions: Dict[str, Set[str]] = {}
        self._setup_default_roles()
    
    def _setup_default_roles(self):
        """设置默认角色权限"""
        
        # 超级管理员 - 拥有所有权限
        self._role_permissions["super_admin"] = {
            Permission.SUPER_ADMIN,
            Permission.REGION_MANAGE,
            Permission.REGION_VIEW,
            Permission.PROVINCE_MANAGE,
            Permission.CITY_MANAGE,
            Permission.KEYWORD_MANAGE,
            Permission.KEYWORD_VIEW,
            Permission.MERCHANT_MANAGE,
            Permission.MERCHANT_VIEW,
            Permission.MERCHANT_APPROVE,
            Permission.SYSTEM_CONFIG,
            Permission.DATABASE_ACCESS,
            Permission.USER_MANAGE,
            Permission.STATS_VIEW
        }
        
        # 地区管理员
        self._role_permissions["region_admin"] = {
            Permission.REGION_MANAGE,
            Permission.REGION_VIEW,
            Permission.PROVINCE_MANAGE,
            Permission.CITY_MANAGE,
            Permission.STATS_VIEW
        }
        
        # 关键词管理员
        self._role_permissions["keyword_admin"] = {
            Permission.KEYWORD_MANAGE,
            Permission.KEYWORD_VIEW,
            Permission.REGION_VIEW,
            Permission.STATS_VIEW
        }
        
        # 商家管理员
        self._role_permissions["merchant_admin"] = {
            Permission.MERCHANT_MANAGE,
            Permission.MERCHANT_VIEW,
            Permission.MERCHANT_APPROVE,
            Permission.REGION_VIEW,
            Permission.KEYWORD_VIEW,
            Permission.STATS_VIEW
        }
        
        # 只读管理员
        self._role_permissions["readonly_admin"] = {
            Permission.REGION_VIEW,
            Permission.KEYWORD_VIEW,
            Permission.MERCHANT_VIEW,
            Permission.STATS_VIEW
        }
    
    async def initialize(self):
        """初始化权限系统"""
        try:
            # 创建管理员权限表
            await self._create_admin_tables()
            # 初始化默认管理员
            await self._initialize_default_admins()
            logger.info("管理员权限系统初始化完成")
        except Exception as e:
            logger.error(f"初始化管理员权限系统失败: {e}")
            raise
    
    async def _create_admin_tables(self):
        """创建管理员相关数据表"""
        
        # 管理员表
        admin_table_sql = """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'readonly_admin',
            is_active BOOLEAN DEFAULT TRUE,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # 管理员权限表
        permissions_table_sql = """
        CREATE TABLE IF NOT EXISTS admin_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            granted_by INTEGER,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, permission),
            FOREIGN KEY (user_id) REFERENCES admins (user_id)
        );
        """
        
        # 管理员操作日志表
        log_table_sql = """
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        await self.db_manager.execute_query(admin_table_sql)
        await self.db_manager.execute_query(permissions_table_sql)
        await self.db_manager.execute_query(log_table_sql)
        
        logger.info("管理员数据表创建完成")
    
    async def _initialize_default_admins(self):
        """初始化默认管理员"""
        try:
            for admin_id in ADMIN_IDS:
                # 检查是否已存在
                existing = await self.db_manager.fetch_one(
                    "SELECT id FROM admins WHERE user_id = ?",
                    (admin_id,)
                )
                
                if not existing:
                    # 添加默认管理员
                    await self.db_manager.execute_query(
                        """INSERT INTO admins (user_id, role, is_active, created_by) 
                           VALUES (?, 'super_admin', TRUE, ?)""",
                        (admin_id, admin_id)
                    )
                    
                    # 添加超级管理员权限
                    for permission in self._role_permissions["super_admin"]:
                        await self.db_manager.execute_query(
                            """INSERT OR IGNORE INTO admin_permissions 
                               (user_id, permission, granted_by) VALUES (?, ?, ?)""",
                            (admin_id, permission, admin_id)
                        )
                    
                    logger.info(f"初始化超级管理员: {admin_id}")
        
        except Exception as e:
            logger.error(f"初始化默认管理员失败: {e}")
    
    async def is_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        try:
            # 检查config中的ADMIN_IDS
            if user_id in ADMIN_IDS:
                return True
            
            # 检查数据库中的管理员
            result = await self.db_manager.fetch_one(
                "SELECT id FROM admins WHERE user_id = ? AND is_active = TRUE",
                (user_id,)
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"检查管理员身份失败: {e}")
            return False
    
    async def has_permission(self, user_id: int, permission: str) -> bool:
        """检查用户是否有指定权限"""
        try:
            # 检查是否为超级管理员
            if user_id in ADMIN_IDS:
                return True
            
            # 从缓存获取权限
            if user_id in self._permission_cache:
                return permission in self._permission_cache[user_id]
            
            # 从数据库获取权限
            permissions = await self._get_user_permissions(user_id)
            self._permission_cache[user_id] = permissions
            
            return permission in permissions
            
        except Exception as e:
            logger.error(f"检查权限失败: {e}")
            return False
    
    async def _get_user_permissions(self, user_id: int) -> Set[str]:
        """从数据库获取用户权限"""
        try:
            # 获取角色权限
            admin_info = await self.db_manager.fetch_one(
                "SELECT role FROM admins WHERE user_id = ? AND is_active = TRUE",
                (user_id,)
            )
            
            permissions = set()
            
            if admin_info:
                role = admin_info['role']
                if role in self._role_permissions:
                    permissions.update(self._role_permissions[role])
            
            # 获取额外权限
            extra_permissions = await self.db_manager.fetch_all(
                "SELECT permission FROM admin_permissions WHERE user_id = ?",
                (user_id,)
            )
            
            for perm in extra_permissions:
                permissions.add(perm['permission'])
            
            return permissions
            
        except Exception as e:
            logger.error(f"获取用户权限失败: {e}")
            return set()
    
    async def add_admin(self, user_id: int, role: str, added_by: int, 
                       username: str = None, full_name: str = None) -> bool:
        """添加新管理员"""
        try:
            # 检查添加者是否有权限
            if not await self.has_permission(added_by, Permission.USER_MANAGE):
                return False
            
            # 添加管理员
            await self.db_manager.execute_query(
                """INSERT OR REPLACE INTO admins 
                   (user_id, username, full_name, role, is_active, created_by) 
                   VALUES (?, ?, ?, ?, TRUE, ?)""",
                (user_id, username, full_name, role, added_by)
            )
            
            # 添加角色权限
            if role in self._role_permissions:
                for permission in self._role_permissions[role]:
                    await self.db_manager.execute_query(
                        """INSERT OR IGNORE INTO admin_permissions 
                           (user_id, permission, granted_by) VALUES (?, ?, ?)""",
                        (user_id, permission, added_by)
                    )
            
            # 清除缓存
            if user_id in self._permission_cache:
                del self._permission_cache[user_id]
            
            # 记录日志
            await self._log_action(added_by, "add_admin", "admin", user_id, 
                                 f"添加管理员，角色: {role}")
            
            logger.info(f"添加管理员: {user_id}, 角色: {role}")
            return True
            
        except Exception as e:
            logger.error(f"添加管理员失败: {e}")
            return False
    
    async def remove_admin(self, user_id: int, removed_by: int) -> bool:
        """移除管理员"""
        try:
            # 检查权限
            if not await self.has_permission(removed_by, Permission.USER_MANAGE):
                return False
            
            # 不能移除自己
            if user_id == removed_by:
                return False
            
            # 不能移除超级管理员
            if user_id in ADMIN_IDS:
                return False
            
            # 设置为非激活状态
            await self.db_manager.execute_query(
                "UPDATE admins SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (user_id,)
            )
            
            # 清除权限
            await self.db_manager.execute_query(
                "DELETE FROM admin_permissions WHERE user_id = ?",
                (user_id,)
            )
            
            # 清除缓存
            if user_id in self._permission_cache:
                del self._permission_cache[user_id]
            
            # 记录日志
            await self._log_action(removed_by, "remove_admin", "admin", user_id, "移除管理员")
            
            logger.info(f"移除管理员: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除管理员失败: {e}")
            return False
    
    async def get_admin_list(self) -> List[Dict]:
        """获取管理员列表"""
        try:
            admins = await self.db_manager.fetch_all(
                """SELECT user_id, username, full_name, role, is_active, created_at 
                   FROM admins ORDER BY created_at DESC"""
            )
            
            return [dict(admin) for admin in admins] if admins else []
            
        except Exception as e:
            logger.error(f"获取管理员列表失败: {e}")
            return []
    
    async def _log_action(self, user_id: int, action: str, target_type: str = None,
                         target_id: int = None, details: str = None):
        """记录管理员操作日志"""
        try:
            await self.db_manager.execute_query(
                """INSERT INTO admin_logs 
                   (user_id, action, target_type, target_id, details) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, action, target_type, target_id, details)
            )
        except Exception as e:
            logger.error(f"记录操作日志失败: {e}")
    
    def clear_cache(self, user_id: int = None):
        """清除权限缓存"""
        if user_id:
            if user_id in self._permission_cache:
                del self._permission_cache[user_id]
        else:
            self._permission_cache.clear()
    
    def require_permission(self, permission: str):
        """装饰器：要求指定权限"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(self_or_update, *args, **kwargs):
                # 处理不同的调用方式
                if hasattr(self_or_update, 'effective_user'):
                    # 直接传入update
                    update = self_or_update
                    user_id = update.effective_user.id
                else:
                    # 传入的是self，update在args中
                    if args and hasattr(args[0], 'effective_user'):
                        update = args[0]
                        user_id = update.effective_user.id
                    else:
                        logger.error("无法获取用户ID")
                        return False
                
                # 检查权限
                admin_permissions = AdminPermissions()
                if not await admin_permissions.has_permission(user_id, permission):
                    if hasattr(update, 'callback_query') and update.callback_query:
                        await update.callback_query.answer("❌ 权限不足", show_alert=True)
                    elif hasattr(update, 'message') and update.message:
                        await update.message.reply_text("❌ 权限不足")
                    return False
                
                return await func(self_or_update, *args, **kwargs)
            return wrapper
        return decorator
    
    def require_admin(self):
        """装饰器：要求管理员身份"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(self_or_update, *args, **kwargs):
                # 处理不同的调用方式
                if hasattr(self_or_update, 'effective_user'):
                    update = self_or_update
                    user_id = update.effective_user.id
                else:
                    if args and hasattr(args[0], 'effective_user'):
                        update = args[0]
                        user_id = update.effective_user.id
                    else:
                        logger.error("无法获取用户ID")
                        return False
                
                # 检查管理员身份
                admin_permissions = AdminPermissions()
                if not await admin_permissions.is_admin(user_id):
                    if hasattr(update, 'callback_query') and update.callback_query:
                        await update.callback_query.answer("❌ 需要管理员权限", show_alert=True)
                    elif hasattr(update, 'message') and update.message:
                        await update.message.reply_text("❌ 需要管理员权限")
                    return False
                
                return await func(self_or_update, *args, **kwargs)
            return wrapper
        return decorator


# 全局权限实例
admin_permissions = AdminPermissions()


# 常用装饰器
def require_admin(func: Callable) -> Callable:
    """要求管理员权限的装饰器"""
    return admin_permissions.require_admin()(func)


def require_permission(permission: str):
    """要求特定权限的装饰器"""
    return admin_permissions.require_permission(permission)


# 权限检查函数
async def check_admin(user_id: int) -> bool:
    """检查管理员身份"""
    return await admin_permissions.is_admin(user_id)


async def check_permission(user_id: int, permission: str) -> bool:
    """检查特定权限"""
    return await admin_permissions.has_permission(user_id, permission)