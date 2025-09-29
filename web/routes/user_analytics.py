# -*- coding: utf-8 -*-
"""
用户激励系统数据分析页面
提供用户行为、等级分布、勋章获取等可视化图表
"""

import logging
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.requests import Request
import json

from web.layout import create_layout, require_auth
from web.services.user_mgmt_service import UserMgmtService
from fasthtml.common import *

logger = logging.getLogger(__name__)

@require_auth
async def user_analytics_dashboard(request: Request):
    """用户激励系统分析仪表板"""
    
    # 图表容器（响应式更紧凑：单一网格，最多三列，同时降低图表高度）
    charts_section = Div(
        # 1/6 等级分布
        Div(
            H3("📊 用户等级分布", cls="text-sm font-semibold mb-2"),
            Div(
                Canvas(id="levelDistributionChart", cls="absolute inset-0"),
                cls="relative h-full"
            ),
            cls="card bg-base-100 shadow p-3 h-full"
        ),
        # 2/6 活跃趋势
        Div(
            H3("📈 活跃度趋势(30天)", cls="text-sm font-semibold mb-2"),
            Div(
                Canvas(id="userActivityChart", cls="absolute inset-0"),
                cls="relative h-full"
            ),
            cls="card bg-base-100 shadow p-3 h-full"
        ),
        # 3/6 热门勋章
        Div(
            H3("🏆 热门勋章(Top10)", cls="text-sm font-semibold mb-2"),
            Div(
                Canvas(id="popularBadgesChart", cls="absolute inset-0"),
                cls="relative h-full"
            ),
            cls="card bg-base-100 shadow p-3 h-full"
        ),
        # 4/6 积分分布
        Div(
            H3("💰 积分分布", cls="text-sm font-semibold mb-2"),
            Div(
                Canvas(id="pointsDistributionChart", cls="absolute inset-0"),
                cls="relative h-full"
            ),
            cls="card bg-base-100 shadow p-3 h-full"
        ),
        # 5/6 评价活跃度
        Div(
            H3("⭐ 评价活跃度(7天)", cls="text-sm font-semibold mb-2"),
            Div(
                Canvas(id="reviewActivityChart", cls="absolute inset-0"),
                cls="relative h-full"
            ),
            cls="card bg-base-100 shadow p-3 h-full"
        ),
        # 6/6 成长轨迹（经验分布）
        Div(
            H3("📈 成长轨迹(经验分布)", cls="text-sm font-semibold mb-2"),
            Div(
                Canvas(id="userGrowthChart", cls="absolute inset-0"),
                cls="relative h-full"
            ),
            cls="card bg-base-100 shadow p-3 h-full"
        ),
        cls="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4",
        style="grid-auto-rows: minmax(18rem, 1fr);"
    )
    
    # Chart.js初始化脚本 - 通过fetch获取数据
    chart_script_content = """
    document.addEventListener('DOMContentLoaded', async function() {
        try {
            // 从唯一接口获取数据
            const res = await fetch('/users/analytics-data');
            if (!res.ok) {
                throw new Error('数据获取失败: ' + res.status);
            }
            const analyticsData = await res.json();
            console.log('Analytics data loaded:', analyticsData);
            
            // 辅助：整数刻度轴配置（避免0-0.5-1缩略）
            function getMaxTicksByWidth(container){
                try {
                    const w = (container && container.clientWidth) ? container.clientWidth : window.innerWidth;
                    if (w >= 1280) return 8;
                    if (w >= 1024) return 7;
                    if (w >= 768) return 6;
                    return 5;
                } catch (_) { return 6; }
            }

            function intAxisCfg(arr, container){
                const data = Array.isArray(arr) ? arr.map(Number).filter(v=>!isNaN(v)) : [];
                const max = Math.max(0, ...data, 0);
                const suggested = max === 0 ? 10 : Math.ceil(max * 1.2);
                const maxTicks = getMaxTicksByWidth(container);
                const step = Math.max(1, Math.ceil(suggested / maxTicks));
                return {
                    beginAtZero: true,
                    suggestedMax: suggested,
                    ticks: { stepSize: step, precision: 0, maxTicksLimit: maxTicks, autoSkip: true, callback: (v)=>Math.floor(v) }
                };
            }
            
            // 1. 用户等级分布饼图
            const levelCtx = document.getElementById('levelDistributionChart');
            if (levelCtx) {
                new Chart(levelCtx.getContext('2d'), {
                    type: 'doughnut',
                    data: {
                        labels: analyticsData.level_names || [],
                        datasets: [{
                            data: analyticsData.level_counts || [],
                            backgroundColor: [
                                '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'
                            ],
                            borderWidth: 2,
                            borderColor: '#ffffff'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        resizeDelay: 200,
                        animation: false,
                        plugins: {
                            legend: { position: 'bottom' },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        if (total === 0) return context.label + ': 0';
                                        const percentage = ((context.parsed / total) * 100).toFixed(1);
                                        return context.label + ': ' + context.parsed + ' 用户 (' + percentage + '%)';
                                    }
                                }
                            }
                        }
                    }
                });
                console.log('Level distribution chart initialized');
            }
            
            // 2. 用户活跃度趋势折线图
            const activityCtx = document.getElementById('userActivityChart');
            if (activityCtx) {
                const activityWrap = activityCtx.parentElement;
                new Chart(activityCtx.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: analyticsData.activity_dates || [],
                        datasets: [{
                            label: '活跃用户数',
                            data: analyticsData.activity_counts || [],
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        resizeDelay: 200,
                        animation: false,
                        scales: { y: intAxisCfg(analyticsData.activity_counts || [], activityWrap) },
                        plugins: {
                            legend: { position: 'bottom' }
                        }
                    }
                });
                console.log('User activity chart initialized');
            }
            
            // 3. 热门勋章排行横向条形图
            const badgesCtx = document.getElementById('popularBadgesChart');
            if (badgesCtx) {
                const badgesWrap = badgesCtx.parentElement;
                new Chart(badgesCtx.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels: analyticsData.badge_names || [],
                        datasets: [{
                            label: '获得用户数',
                            data: analyticsData.badge_counts || [],
                            backgroundColor: [
                                '#f59e0b', '#ef4444', '#10b981', '#3b82f6', '#8b5cf6',
                                '#06b6d4', '#f97316', '#84cc16', '#ec4899', '#6366f1'
                            ]
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        resizeDelay: 200,
                        animation: false,
                        scales: { x: intAxisCfg(analyticsData.badge_counts || [], badgesWrap) },
                        plugins: { legend: { display: false } }
                    }
                });
                console.log('Popular badges chart initialized');
            }
            
            // 4. 用户积分分布柱状图
            const pointsCtx = document.getElementById('pointsDistributionChart');
            if (pointsCtx) {
                const pointsWrap = pointsCtx.parentElement;
                new Chart(pointsCtx.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels: analyticsData.points_ranges || [],
                        datasets: [{
                            label: '用户数',
                            data: analyticsData.points_counts || [],
                            backgroundColor: '#3b82f6',
                            borderColor: '#1d4ed8',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        resizeDelay: 200,
                        animation: false,
                        scales: { y: intAxisCfg(analyticsData.points_counts || [], pointsWrap) },
                        plugins: { legend: { position: 'bottom' } }
                    }
                });
                console.log('Points distribution chart initialized');
            }
            
            // 5. 评价活跃度统计折线图
            const reviewCtx = document.getElementById('reviewActivityChart');
            if (reviewCtx) {
                const reviewWrap = reviewCtx.parentElement;
                new Chart(reviewCtx.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: analyticsData.review_activity_dates || [],
                        datasets: [{
                            label: '评价数量',
                            data: analyticsData.review_activity_counts || [],
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            fill: true,
                            tension: 0.3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        resizeDelay: 200,
                        animation: false,
                        scales: { y: intAxisCfg(analyticsData.review_activity_counts || [], reviewWrap) },
                        plugins: { legend: { position: 'bottom' } }
                    }
                });
                console.log('Review activity chart initialized');
            }
            
            // 6. 用户成长轨迹柱状图 (经验值分布)
            const growthCtx = document.getElementById('userGrowthChart');
            if (growthCtx) {
                const growthWrap = growthCtx.parentElement;
                new Chart(growthCtx.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels: analyticsData.xp_ranges || [],
                        datasets: [{
                            label: '用户数',
                            data: analyticsData.xp_counts || [],
                            backgroundColor: '#8b5cf6',
                            borderColor: '#7c3aed',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        resizeDelay: 200,
                        animation: false,
                        scales: { y: intAxisCfg(analyticsData.xp_counts || [], growthWrap) },
                        plugins: { legend: { position: 'bottom' } }
                    }
                });
                console.log('User growth chart initialized');
            }
            
            console.log('所有6个图表初始化完成');
            
        } catch (error) {
            console.error('图表初始化失败:', error);
            // 显示错误提示而不是伪造数据
            document.querySelectorAll('canvas').forEach(canvas => {
                const ctx = canvas.getContext('2d');
                ctx.font = '16px Arial';
                ctx.fillStyle = '#ef4444';
                ctx.textAlign = 'center';
                ctx.fillText('数据加载失败', canvas.width/2, canvas.height/2);
            });
        }
    });
    """
    
    content = Div(
        # 紧凑页头（减少垂直占位）
        Div(
            Div(
                H2("用户分析", cls="text-xl font-semibold"),
                P("等级分布、活跃趋势、勋章与积分概览", cls="text-xs text-gray-500 mt-1"),
                cls=""
            ),
            Div(
                A("返回用户管理", href="/users", cls="btn btn-outline btn-xs"),
                A("返回激励管理", href="/incentives", cls="btn btn-outline btn-xs ml-2"),
                cls=""
            ),
            cls="flex items-center justify-between mb-2"
        ),

        charts_section,
        Script(chart_script_content),  # Chart.js初始化脚本
        
        cls="page-content",
        style="min-height: calc(100vh - 80px);"
    )
    
    return create_layout("用户数据分析", content, include_charts=True)

@require_auth
async def user_analytics_data_api(request: Request):
    """用户分析数据API - 唯一数据接口"""
    try:
        # 调用服务层唯一方法获取数据
        data = await UserMgmtService.get_user_charts_dataset()
        return JSONResponse(data)
    except Exception as e:
        logger.error(f"获取用户分析数据API失败: {e}")
        # 异常返回500，不提供兜底数据
        return JSONResponse({"error": f"数据获取失败: {str(e)}"}, status_code=500)

# 导出路由（实际注册在web/app.py中）
user_analytics_routes = [
    Route("/analytics", user_analytics_dashboard, methods=["GET"]),
    Route("/analytics-data", user_analytics_data_api, methods=["GET"]),
]
