"""
数据库模块
提供数据库连接管理、初始化和各种数据操作功能
"""

from .db_connection import db_manager, DatabaseManager
from .db_init import db_initializer, init_database, cleanup_database, get_db_stats
from .db_merchants import (
    MerchantManager,
    create_merchant,
    get_merchant,
    get_merchant_by_chat_id,
    get_all_merchants,
    update_merchant,
    update_merchant_status,
    delete_merchant,
    search_merchants,
    get_merchant_statistics
)

__all__ = [
    # 连接管理
    'db_manager',
    'DatabaseManager',
    
    # 初始化
    'db_initializer',
    'init_database',
    'cleanup_database',
    'get_db_stats',
    
    # 商户管理
    'MerchantManager',
    'create_merchant',
    'get_merchant',
    'get_merchant_by_chat_id',
    'get_all_merchants',
    'update_merchant',
    'update_merchant_status',
    'delete_merchant',
    'search_merchants',
    'get_merchant_statistics'
]