# -*- coding: utf-8 -*-
"""
仪表板路由模块
处理系统概览和统计数据展示
"""

from fasthtml.common import *
from starlette.requests import Request
from datetime import datetime

# 导入布局和认证组件
from ..layout import create_layout, require_auth
from ..services.dashboard_service import DashboardService


@require_auth
async def dashboard(request: Request):
    """仪表板页面 - 基于实际数据的统计显示"""
    
    # 获取统计数据（使用服务层的缓存机制）
    stats_data = await DashboardService.get_dashboard_data()
    
    content = Div(
        # 使用统一的页面头部
        Div(
            H1("系统仪表板", cls="page-title"),
            P(f"数据更新时间: { (stats_data.get('last_updated') or '')[:19] }", cls="page-subtitle"),
            cls="page-header"
        ),
        
        # 使用统一的页面内容布局
        Div(
            # 第一行 - 核心业务数据
            Div(
                # 商户总数
                Div(
                    Div(
                        Span("🏪", cls="text-4xl mb-2"),
                        H3("商户总数", cls="font-bold text-white"),
                        P("已注册商户", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats_data["merchants"]["total"]), cls="text-4xl font-bold text-blue-400"),
                        P("个商户", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 活跃商户
                Div(
                    Div(
                        Span("✅", cls="text-4xl mb-2"),
                        H3("活跃商户", cls="font-bold text-white"),
                        P("已审核通过", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats_data["merchants"]["approved"]), cls="text-4xl font-bold text-green-400"),
                        P("个活跃", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 绑定码总数
                Div(
                    Div(
                        Span("🎫", cls="text-4xl mb-2"),
                        H3("绑定码", cls="font-bold text-white"),
                        P("系统绑定码", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats_data["binding_codes"]["total_codes"]), cls="text-4xl font-bold text-purple-400"),
                        P("个绑定码", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 绑定码使用率
                Div(
                    Div(
                        Span("📊", cls="text-4xl mb-2"),
                        H3("使用率", cls="font-bold text-white"),
                        P("绑定码使用率", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(f"{stats_data['binding_codes']['usage_rate']:.1f}%" if stats_data['binding_codes']['usage_rate'] > 0 else "0.0%", cls="text-4xl font-bold text-pink-400"),
                        P(f"({stats_data['binding_codes']['used_codes']}/{stats_data['binding_codes']['total_codes']})", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                cls="stats-container"
            ),
            
            # 第二行 - 业务评价数据
            Div(
                # 评价总数
                Div(
                    Div(
                        Span("⭐", cls="text-4xl mb-2"),
                        H3("评价总数", cls="font-bold text-white"),
                        P("用户评价数", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats_data["reviews"]["total"]), cls="text-4xl font-bold text-yellow-400"),
                        P("条评价", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 平均评分
                Div(
                    Div(
                        Span("📈", cls="text-4xl mb-2"),
                        H3("平均评分", cls="font-bold text-white"),
                        P("五维平均分", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(f"{stats_data['reviews']['average_rating']:.1f}" if stats_data['reviews']['average_rating'] > 0 else "0.0", cls="text-4xl font-bold text-orange-400"),
                        P("分 (满分10)", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 地区覆盖
                Div(
                    Div(
                        Span("🗺️", cls="text-4xl mb-2"),
                        H3("地区覆盖", cls="font-bold text-white"),
                        P("城市+区县", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(f"{stats_data['regions']['total_cities']}+{stats_data['regions']['total_districts']}", cls="text-4xl font-bold text-cyan-400"),
                        P("个地区", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 系统模板
                Div(
                    Div(
                        Span("📋", cls="text-4xl mb-2"),
                        H3("系统模板", cls="font-bold text-white"),
                        P("配置模板数", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats_data["system"]["template_count"]), cls="text-4xl font-bold text-indigo-400"),
                        P("个模板", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                cls="stats-container"
            ),
            
            cls="page-content"
        )
    )
    
    return create_layout("仪表板", content)
