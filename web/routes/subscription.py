# -*- coding: utf-8 -*-
"""
订阅验证路由模块
处理用户频道订阅验证和管理功能
"""

import logging
from fasthtml.common import *
from starlette.requests import Request

# 导入布局和认证组件
from ..layout import create_layout, require_auth
from ..services.subscription_mgmt_service import SubscriptionMgmtService

logger = logging.getLogger(__name__)


@require_auth
async def subscription_dashboard(request: Request):
    """订阅验证管理页面"""
    try:
        # 调用服务层获取订阅数据
        subscription_data = await SubscriptionMgmtService.get_subscription_dashboard()
        
        content = Div(
            H1("订阅验证管理", cls="page-title"),
            P("管理用户频道订阅验证", cls="page-subtitle"),
            cls="page-content"
        )
        
        return create_layout("订阅验证管理", content)
        
    except Exception as e:
        logger.error(f"订阅验证管理页面错误: {e}")
        error_content = Div(
            H1("订阅验证管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600")
        )
        return create_layout("系统错误", error_content)