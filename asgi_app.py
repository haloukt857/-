# -*- coding: utf-8 -*-
"""
ASGI统一应用入口
整合机器人webhook服务和重构后的模块化FastHTML管理面板。
"""

import os
import logging

# 导入重构后的模块化Web应用
from web.app import app as admin_app

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger(__name__)

def create_final_asgi_app():
    """创建最终的ASGI应用实例"""
    logger.info("创建重构后的Web管理应用...")

    # 直接使用重构后的完整FastHTML应用
    # 所有路由已经在web/app.py中注册完成，包括：
    # - 认证路由 (/login, /logout)
    # - 仪表板路由 (/)
    # - 商户管理路由 (/merchants)
    # - 用户管理路由 (/users)
    # - 订单管理路由 (/orders)
    # - 评价管理路由 (/reviews)
    # - 地区管理路由 (/regions)
    # - 激励系统路由 (/incentives)
    # - 订阅验证路由 (/subscription)
    # - 绑定码管理路由 (/binding-codes)
    # - 帖子管理路由 (/posts)
    # - 媒体代理路由 (/media-proxy/{media_id:int})
    # - 调试工具路由 (/debug/*)
    
    app = admin_app
    logger.info("重构后的Web应用加载成功")
    
    # 显示路由统计
    try:
        route_count = len(app.router.routes) if hasattr(app.router, 'routes') else 0
        logger.info(f"已注册路由数量: {route_count}")
    except:
        logger.info("Web应用路由已完全加载")

    logger.info("重构后的模块化Web应用创建完成")
    return app

# 创建最终的应用实例
app = create_final_asgi_app()
