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
    
    # 图表容器（只输出6个canvas容器，不内嵌数据）
    charts_section = Div(
        # 第一行图表
        Div(
            # 用户等级分布饼图
            Div(
                H3("📊 用户等级分布", cls="content-section-title"),
                Canvas(id="levelDistributionChart", width="400", height="200"),
                cls="content-section"
            ),
            
            # 用户活跃度趋势
            Div(
                H3("📈 用户活跃度趋势 (近30天)", cls="content-section-title"),
                Canvas(id="userActivityChart", width="400", height="200"),
                cls="content-section"
            ),
            
            cls="content-grid grid-2"
        ),
        
        # 第二行图表
        Div(
            # 热门勋章排行
            Div(
                H3("🏆 热门勋章排行 (Top 10)", cls="content-section-title"),
                Canvas(id="popularBadgesChart", width="400", height="300"),
                cls="content-section"
            ),
            
            # 积分分布柱状图
            Div(
                H3("💰 用户积分分布", cls="content-section-title"),
                Canvas(id="pointsDistributionChart", width="400", height="300"), 
                cls="content-section"
            ),
            
            cls="content-grid grid-2"
        ),
        
        # 第三行图表
        Div(
            # 评价活跃度
            Div(
                H3("⭐ 评价活跃度统计", cls="content-section-title"),
                Canvas(id="reviewActivityChart", width="400", height="250"),
                cls="content-section"
            ),
            
            # 用户成长轨迹
            Div(
                H3("📈 用户成长轨迹 (经验值分布)", cls="content-section-title"),
                Canvas(id="userGrowthChart", width="400", height="250"),
                cls="content-section"
            ),
            
            cls="content-grid grid-2"
        )
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
                        plugins: {
                            legend: { position: 'right' },
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
                        scales: {
                            y: { beginAtZero: true }
                        },
                        plugins: {
                            legend: { position: 'top' }
                        }
                    }
                });
                console.log('User activity chart initialized');
            }
            
            // 3. 热门勋章排行横向条形图
            const badgesCtx = document.getElementById('popularBadgesChart');
            if (badgesCtx) {
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
                        scales: {
                            x: { beginAtZero: true }
                        },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
                console.log('Popular badges chart initialized');
            }
            
            // 4. 用户积分分布柱状图
            const pointsCtx = document.getElementById('pointsDistributionChart');
            if (pointsCtx) {
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
                        scales: {
                            y: { beginAtZero: true }
                        },
                        plugins: {
                            legend: { position: 'top' }
                        }
                    }
                });
                console.log('Points distribution chart initialized');
            }
            
            // 5. 评价活跃度统计折线图
            const reviewCtx = document.getElementById('reviewActivityChart');
            if (reviewCtx) {
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
                        scales: {
                            y: { beginAtZero: true }
                        },
                        plugins: {
                            legend: { position: 'top' }
                        }
                    }
                });
                console.log('Review activity chart initialized');
            }
            
            // 6. 用户成长轨迹柱状图 (经验值分布)
            const growthCtx = document.getElementById('userGrowthChart');
            if (growthCtx) {
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
                        scales: {
                            y: { beginAtZero: true }
                        },
                        plugins: {
                            legend: { position: 'top' }
                        }
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
        # 页面头部
        Div(
            H1("用户激励系统数据分析", cls="page-title"),
            P("可视化展示用户行为、等级分布、勋章获取等数据", cls="page-subtitle"),
            cls="page-header"
        ),
        
        # 导航链接
        Div(
            A("← 返回用户管理", href="/users", cls="btn btn-outline"),
            A("← 返回激励管理", href="/incentives", cls="btn btn-outline ml-2"),
            cls="mb-6"
        ),
        
        charts_section,
        Script(chart_script_content),  # Chart.js初始化脚本
        
        cls="page-content"
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
