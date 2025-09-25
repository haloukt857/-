# -*- coding: utf-8 -*-
"""
订单分析图表页面
提供订单趋势、状态分布、商户排行等可视化图表
"""

import logging
from typing import Any, Dict, List
from starlette.routing import Route
from starlette.responses import Response, HTMLResponse
from starlette.exceptions import HTTPException
from starlette.requests import Request
from datetime import datetime, timedelta
import json

from database.db_orders import OrderManager
from database.db_merchants import merchant_manager
from web.layout import create_layout, require_auth
from utils.enums import ORDER_STATUS
from fasthtml.common import *

logger = logging.getLogger(__name__)

@require_auth
async def order_analytics_dashboard(request: Request) -> Response:
    """订单分析仪表板页面"""
    
    try:
        # 获取分析数据
        analytics_data = await _get_analytics_data()
    except Exception as e:
        logger.error(f"获取分析数据失败: {e}")
        raise HTTPException(status_code=500, detail="无法获取分析数据")
    
    # 图表容器
    charts_section = Div(
        # 第一行图表
        Div(
            # 订单趋势图
            Div(
                H3("📈 订单趋势 (近30天)", cls="content-section-title"),
                Canvas(id="orderTrendChart", width="400", height="200"),
                cls="content-section"
            ),
            
            # 状态分布饼图
            Div(
                H3("📊 订单状态分布", cls="content-section-title"),
                Canvas(id="statusDistributionChart", width="400", height="200"),
                cls="content-section"
            ),
            
            cls="content-grid grid-2"
        ),
        
        # 第二行图表
        Div(
            # 热门商户排行
            Div(
                H3("🏆 热门商户排行 (Top 10)", cls="content-section-title"),
                Canvas(id="topMerchantsChart", width="400", height="300"),
                cls="content-section"
            ),
            
            # 收入趋势
            Div(
                H3("💰 收入趋势 (近7天)", cls="content-section-title"),
                Canvas(id="revenueTrendChart", width="400", height="300"), 
                cls="content-section"
            ),
            
            cls="content-grid grid-2"
        )
    )
    
    # Chart.js初始化脚本
    chart_script = Script(f"""
    // 图表数据
    const analyticsData = {json.dumps(analytics_data)};
    
    // 订单趋势图
    const trendCtx = document.getElementById('orderTrendChart').getContext('2d');
    new Chart(trendCtx, {{
        type: 'line',
        data: {{
            labels: analyticsData.trend_dates,
            datasets: [{{
                label: '订单数量',
                data: analyticsData.trend_counts,
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.1,
                fill: true
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{
                    display: false
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    ticks: {{
                        stepSize: 1
                    }}
                }}
            }}
        }}
    }});
    
    // 状态分布饼图
    const statusCtx = document.getElementById('statusDistributionChart').getContext('2d');
    new Chart(statusCtx, {{
        type: 'doughnut',
        data: {{
            labels: analyticsData.status_labels,
            datasets: [{{
                data: analyticsData.status_counts,
                backgroundColor: [
                    '#fbbf24', // warning - 尝试预约
                    '#10b981', // success - 已完成  
                    '#3b82f6', // info - 已评价
                    '#8b5cf6', // primary - 双方评价
                    '#6b7280'  // secondary - 单方评价
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{
                    position: 'bottom'
                }}
            }}
        }}
    }});
    
    // 热门商户排行
    const merchantsCtx = document.getElementById('topMerchantsChart').getContext('2d');
    new Chart(merchantsCtx, {{
        type: 'bar',
        data: {{
            labels: analyticsData.merchant_names,
            datasets: [{{
                label: '订单数量',
                data: analyticsData.merchant_counts,
                backgroundColor: 'rgba(34, 197, 94, 0.8)',
                borderColor: 'rgb(34, 197, 94)',
                borderWidth: 1
            }}]
        }},
        options: {{
            responsive: true,
            indexAxis: 'y',
            plugins: {{
                legend: {{
                    display: false
                }}
            }},
            scales: {{
                x: {{
                    beginAtZero: true,
                    ticks: {{
                        stepSize: 1
                    }}
                }}
            }}
        }}
    }});
    
    // 收入趋势图
    const revenueCtx = document.getElementById('revenueTrendChart').getContext('2d');
    new Chart(revenueCtx, {{
        type: 'bar',
        data: {{
            labels: analyticsData.revenue_dates,
            datasets: [{{
                label: '收入 (¥)',
                data: analyticsData.revenue_amounts,
                backgroundColor: 'rgba(236, 72, 153, 0.8)',
                borderColor: 'rgb(236, 72, 153)',
                borderWidth: 1
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{
                    display: false
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    ticks: {{
                        callback: function(value) {{
                            return '¥' + value.toLocaleString();
                        }}
                    }}
                }}
            }}
        }}
    }});
    
    // 定时刷新数据 (可选)
    setInterval(async function() {{
        try {{
            const response = await fetch('/orders/analytics-data');
            if (response.ok) {{
                const newData = await response.json();
                // 更新图表数据...
                console.log('数据已更新');
            }}
        }} catch (e) {{
            console.log('数据更新失败:', e);
        }}
    }}, 60000); // 每分钟更新
    """)
    
    content = Div(
        H1("订单数据分析", cls="page-title"),
        
        # 返回链接
        Div(
            A("← 返回订单管理", href="/orders", cls="btn btn-outline")
        ),
        
        charts_section,
        chart_script
    )
    
    return HTMLResponse(str(create_layout("订单分析", content)))

async def _get_analytics_data() -> Dict[str, Any]:
    """获取分析图表所需的数据"""
    try:
        order_manager = OrderManager()
        
        # 近30天订单趋势
        trend_data = await _get_order_trend_data(30)
        
        # 订单状态分布
        status_data = await _get_status_distribution()
        
        # 热门商户排行 (Top 10)
        merchant_data = await _get_top_merchants(10)
        
        # 近7天收入趋势
        revenue_data = await _get_revenue_trend_data(7)
        
        return {
            # 趋势数据
            'trend_dates': trend_data['dates'],
            'trend_counts': trend_data['counts'],
            
            # 状态分布
            'status_labels': status_data['labels'],
            'status_counts': status_data['counts'],
            
            # 商户排行
            'merchant_names': merchant_data['names'],
            'merchant_counts': merchant_data['counts'],
            
            # 收入趋势
            'revenue_dates': revenue_data['dates'],
            'revenue_amounts': revenue_data['amounts']
        }
        
    except Exception as e:
        logger.error(f"获取分析数据失败: {e}")
        # 返回默认数据
        return {
            'trend_dates': [],
            'trend_counts': [],
            'status_labels': [],
            'status_counts': [],
            'merchant_names': [],
            'merchant_counts': [],
            'revenue_dates': [],
            'revenue_amounts': []
        }

async def _get_order_trend_data(days: int) -> Dict[str, List]:
    """获取订单趋势数据"""
    try:
        order_manager = OrderManager()
        dates = []
        counts = []
        
        for i in range(days):
            date = datetime.now().date() - timedelta(days=i)
            date_str = date.isoformat()
            next_date_str = (date + timedelta(days=1)).isoformat()
            
            count = await order_manager.count_orders(
                date_from=date_str,
                date_to=next_date_str
            )
            
            dates.append(date.strftime('%m-%d'))
            counts.append(count)
        
        # 反转数据，使最新日期在右边
        dates.reverse()
        counts.reverse()
        
        return {'dates': dates, 'counts': counts}
        
    except Exception as e:
        logger.error(f"获取订单趋势数据失败: {e}")
        return {'dates': [], 'counts': []}

async def _get_status_distribution() -> Dict[str, List]:
    """获取订单状态分布"""
    try:
        order_manager = OrderManager()
        
        statuses = [
            ORDER_STATUS.ATTEMPT_BOOKING.value,
            ORDER_STATUS.COMPLETED.value,
            ORDER_STATUS.REVIEWED.value,
            ORDER_STATUS.MUTUAL_REVIEW.value,
            ORDER_STATUS.SINGLE_REVIEW.value
        ]
        
        labels = []
        counts = []
        
        for status in statuses:
            count = await order_manager.count_orders(status=status)
            if count > 0:  # 只显示有数据的状态
                labels.append(status)
                counts.append(count)
        
        return {'labels': labels, 'counts': counts}
        
    except Exception as e:
        logger.error(f"获取状态分布数据失败: {e}")
        return {'labels': [], 'counts': []}

async def _get_top_merchants(limit: int) -> Dict[str, List]:
    """获取热门商户排行"""
    try:
        from database.db_connection import db_manager
        
        query = """
            SELECT m.name, COUNT(o.id) as order_count
            FROM merchants m
            LEFT JOIN orders o ON m.id = o.merchant_id
            GROUP BY m.id, m.name
            HAVING order_count > 0
            ORDER BY order_count DESC
            LIMIT ?
        """
        
        results = await db_manager.fetch_all(query, (limit,))
        
        names = []
        counts = []
        
        for row in results:
            names.append(row['name'] or f"商户{row.get('id', 'Unknown')}")
            counts.append(row['order_count'])
        
        return {'names': names, 'counts': counts}
        
    except Exception as e:
        logger.error(f"获取商户排行数据失败: {e}")
        return {'names': [], 'counts': []}

async def _get_revenue_trend_data(days: int) -> Dict[str, List]:
    """获取收入趋势数据"""
    try:
        order_manager = OrderManager()
        dates = []
        amounts = []
        
        for i in range(days):
            date = datetime.now().date() - timedelta(days=i)
            date_str = date.isoformat()
            next_date_str = (date + timedelta(days=1)).isoformat()
            
            revenue = await order_manager.get_revenue_stats(
                date_from=date_str,
                date_to=next_date_str
            )
            
            dates.append(date.strftime('%m-%d'))
            amounts.append(revenue)
        
        # 反转数据
        dates.reverse()
        amounts.reverse()
        
        return {'dates': dates, 'amounts': amounts}
        
    except Exception as e:
        logger.error(f"获取收入趋势数据失败: {e}")
        return {'dates': [], 'amounts': []}

@require_auth
async def analytics_data_api(request: Request) -> Response:
    """分析数据API (用于实时更新图表)"""
    try:
        data = await _get_analytics_data()
        return Response(
            content=json.dumps(data),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"获取分析数据API失败: {e}")
        return Response(
            content=json.dumps({"error": "获取数据失败"}),
            status_code=500,
            media_type="application/json"
        )

# 导出路由
order_analytics_routes = [
    Route("/analytics", order_analytics_dashboard, methods=["GET"]),
    Route("/analytics-data", analytics_data_api, methods=["GET"]),
]
