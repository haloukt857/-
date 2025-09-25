# -*- coding: utf-8 -*-
"""
Web服务层包
模块化服务层，提供纯业务逻辑处理，与UI层解耦

服务架构:
- 统一的服务接口和错误处理
- 与数据库管理器层的集成
- 支持异步操作和缓存
- 标准化的响应格式
"""

from .auth_service import AuthService
from .dashboard_service import DashboardService
from .merchant_mgmt_service import MerchantMgmtService
from .user_mgmt_service import UserMgmtService
from .order_mgmt_service import OrderMgmtService
from .review_mgmt_service import ReviewMgmtService
from .region_mgmt_service import RegionMgmtService
from .incentive_mgmt_service import IncentiveMgmtService
from .subscription_mgmt_service import SubscriptionMgmtService
# from .binding_mgmt_service import BindingMgmtService  # V2.0: 已迁移到DB Manager
from .post_mgmt_service import PostMgmtService
from .analytics_service import AnalyticsService
from .export_service import ExportService
from .cache_service import CacheService

__all__ = [
    'AuthService',
    'DashboardService', 
    'MerchantMgmtService',
    'UserMgmtService',
    'OrderMgmtService',
    'ReviewMgmtService',
    'RegionMgmtService',
    'IncentiveMgmtService',
    'SubscriptionMgmtService',
    # 'BindingMgmtService',  # V2.0: 已迁移到DB Manager
    'PostMgmtService',
    'AnalyticsService',
    'ExportService',
    'CacheService'
]

# 服务层版本信息
VERSION = "2.0.0"
SCHEMA_VERSION = "2025.09.06.3"