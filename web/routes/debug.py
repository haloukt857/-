# -*- coding: utf-8 -*-
"""
系统调试路由模块
提供系统状态检查、数据库调试等工具
"""

import logging
import sys
import os
from datetime import datetime
from fasthtml.common import *
from starlette.requests import Request

# 导入布局和认证组件
from ..layout import create_layout, require_auth

logger = logging.getLogger(__name__)


@require_auth
async def debug_dashboard(request: Request):
    """系统调试仪表板"""
    try:
        # 获取系统信息
        system_info = {
            "python_version": sys.version,
            "platform": sys.platform,
            "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "working_directory": os.getcwd(),
            "environment_variables": dict(os.environ),
        }
        
        content = Div(
            # 页面头部
            Div(
                H1("系统调试工具", cls="page-title"),
                P("系统状态检查和调试信息", cls="page-subtitle"),
                cls="page-header"
            ),
            
            # 系统信息
            Div(
                H3("系统信息", cls="text-xl font-semibold mb-4"),
                Div(
                    P(f"Python 版本: {system_info['python_version']}", cls="mb-2"),
                    P(f"平台: {system_info['platform']}", cls="mb-2"),
                    P(f"当前时间: {system_info['current_time']}", cls="mb-2"),
                    P(f"工作目录: {system_info['working_directory']}", cls="mb-2"),
                    cls="p-4"
                ),
                cls="card bg-base-100 shadow-xl mb-6"
            ),
            
            # 系统操作
            Div(
                H3("系统操作", cls="text-xl font-semibold mb-4"),
                Div(
                    Div(
                        A("数据库检查", href="/debug/database", cls="btn btn-primary mr-2"),
                        A("日志查看", href="/debug/logs", cls="btn btn-secondary mr-2"),
                        A("缓存状态", href="/debug/cache", cls="btn btn-info mr-2"),
                        A("配置检查", href="/debug/config", cls="btn btn-warning"),
                        cls="flex flex-wrap gap-2"
                    ),
                    cls="p-4"
                ),
                cls="card bg-base-100 shadow-xl"
            ),
            
            cls="page-content"
        )
        
        return create_layout("系统调试", content)
        
    except Exception as e:
        logger.error(f"系统调试页面错误: {e}")
        error_content = Div(
            H1("系统调试错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def debug_database(request: Request):
    """数据库调试页面"""
    try:
        content = Div(
            H1("数据库调试", cls="page-title"),
            P("数据库连接和表状态检查", cls="page-subtitle"),
            cls="page-content"
        )
        
        return create_layout("数据库调试", content)
        
    except Exception as e:
        logger.error(f"数据库调试页面错误: {e}")
        error_content = Div(
            H1("数据库调试错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600")
        )
        return create_layout("系统错误", error_content)