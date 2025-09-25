# -*- coding: utf-8 -*-
"""
路由包导出模块
统一导出所有路由模块供主应用使用
"""
import os

# 导入所有路由模块
from . import (
    auth,
    dashboard, 
    merchants,
    users,
    orders,
    reviews,
    regions,
    incentives,
    subscription,
    binding_codes,
    posts,
    templates,
    debug,
    media
)

# 路由已在web/app.py中直接注册，无需批量注册函数

# 导出所有路由模块供web/app.py直接导入使用
__all__ = [
    'auth', 'dashboard', 'merchants', 'users', 'orders',
    'reviews', 'regions', 'incentives', 'subscription',
    'binding_codes', 'posts', 'templates', 'debug', 'media'
]
