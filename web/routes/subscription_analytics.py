# -*- coding: utf-8 -*-
"""
频道订阅验证数据分析页面
提供订阅验证系统的数据可视化和统计分析
"""

import logging
from typing import Any, Dict, List
from starlette.routing import Route
from starlette.responses import Response, HTMLResponse
from starlette.exceptions import HTTPException
from starlette.requests import Request
from datetime import datetime, timedelta
import json

from database.db_system_config import system_config_manager
from database.db_logs import ActivityLogsDatabase
from web.layout import create_layout, require_auth
from fasthtml.common import *

logger = logging.getLogger(__name__)

@require_auth
async def subscription_analytics_dashboard(request: Request) -> Response:
    """订阅验证数据分析仪表板"""
    
    try:
        # 获取分析数据
        analytics_data = await _get_subscription_analytics_data()
    except Exception as e:
        logger.error(f"获取订阅分析数据失败: {e}")
        raise HTTPException(status_code=500, detail="无法获取分析数据")
    
    # 图表容器
    charts_section = Div(
        # 第一行图表
        Div(
            # 验证趋势图
            Div(
                H3("📈 验证趋势 (近30天)", cls="content-section-title"),
                Canvas(id="verificationTrendChart", width="400", height="200"),
                cls="content-section"
            ),
            
            # 通过率分析
            Div(
                H3("✅ 通过率分析", cls="content-section-title"),
                Canvas(id="passRateChart", width="400", height="200"),
                cls="content-section"
            ),
            
            cls="content-grid grid-2"
        ),
        
        # 第二行图表
        Div(
            # 频道订阅分布
            Div(
                H3("📺 频道订阅分布", cls="content-section-title"),
                Canvas(id="channelDistributionChart", width="400", height="300"),
                cls="content-section"
            ),
            
            # 失败原因分析
            Div(
                H3("❌ 验证失败统计", cls="content-section-title"),
                Canvas(id="failureReasonsChart", width="400", height="300"),
                cls="content-section"
            ),
            
            cls="content-grid grid-2"
        ),
        
        # 第三行：时间分布
        Div(
            # 验证活动时间分布
            Div(
                H3("⏰ 验证活动时间分布", cls="content-section-title"),
                Canvas(id="timeDistributionChart", width="800", height="250"),
                cls="content-section"
            ),
            
            cls="content-grid grid-1"
        )
    )
    
    # Chart.js初始化脚本
    chart_script = Script(f"""
    // 图表数据
    const analyticsData = {json.dumps(analytics_data)};
    
    // 验证趋势线图
    const trendCtx = document.getElementById('verificationTrendChart').getContext('2d');
    new Chart(trendCtx, {{
        type: 'line',
        data: {{
            labels: analyticsData.trend_dates,
            datasets: [
                {{
                    label: '总验证次数',
                    data: analyticsData.trend_total,
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.1,
                    fill: true
                }},
                {{
                    label: '验证失败次数',
                    data: analyticsData.trend_failed,
                    borderColor: 'rgb(239, 68, 68)',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    tension: 0.1,
                    fill: false
                }}
            ]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{
                    position: 'top'
                }},
                tooltip: {{
                    mode: 'index',
                    intersect: false
                }}
            }},
            scales: {{
                y: {{
                    beginAtZero: true,
                    ticks: {{
                        stepSize: 1
                    }}
                }}
            }},
            interaction: {{
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }}
        }}
    }});
    
    // 通过率饼图
    const passRateCtx = document.getElementById('passRateChart').getContext('2d');
    new Chart(passRateCtx, {{
        type: 'doughnut',
        data: {{
            labels: ['验证通过', '验证失败'],
            datasets: [{{
                data: [analyticsData.pass_count, analyticsData.fail_count],
                backgroundColor: [
                    'rgba(34, 197, 94, 0.8)',
                    'rgba(239, 68, 68, 0.8)'
                ],
                borderColor: [
                    'rgb(34, 197, 94)',
                    'rgb(239, 68, 68)'
                ],
                borderWidth: 2
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{
                    position: 'bottom'
                }},
                tooltip: {{
                    callbacks: {{
                        label: function(context) {{
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            return context.label + ': ' + context.parsed + ' 次 (' + percentage + '%)';
                        }}
                    }}
                }}
            }}
        }}
    }});
    
    // 频道订阅分布柱状图
    const channelCtx = document.getElementById('channelDistributionChart').getContext('2d');
    new Chart(channelCtx, {{
        type: 'bar',
        data: {{
            labels: analyticsData.channel_names,
            datasets: [{{
                label: '订阅失败次数',
                data: analyticsData.channel_failures,
                backgroundColor: 'rgba(245, 158, 11, 0.8)',
                borderColor: 'rgb(245, 158, 11)',
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
                        stepSize: 1
                    }}
                }}
            }}
        }}
    }});
    
    // 失败原因分析
    const failureCtx = document.getElementById('failureReasonsChart').getContext('2d');
    new Chart(failureCtx, {{
        type: 'pie',
        data: {{
            labels: analyticsData.failure_reasons.map(item => item.reason),
            datasets: [{{
                data: analyticsData.failure_reasons.map(item => item.count),
                backgroundColor: [
                    'rgba(239, 68, 68, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(139, 92, 246, 0.8)',
                    'rgba(236, 72, 153, 0.8)'
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{
                    position: 'right'
                }},
                tooltip: {{
                    callbacks: {{
                        label: function(context) {{
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            return context.label + ': ' + context.parsed + ' 次 (' + percentage + '%)';
                        }}
                    }}
                }}
            }}
        }}
    }});
    
    // 时间分布柱状图
    const timeCtx = document.getElementById('timeDistributionChart').getContext('2d');
    new Chart(timeCtx, {{
        type: 'bar',
        data: {{
            labels: analyticsData.hour_labels,
            datasets: [{{
                label: '验证次数',
                data: analyticsData.hour_counts,
                backgroundColor: 'rgba(16, 185, 129, 0.8)',
                borderColor: 'rgb(16, 185, 129)',
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
                        stepSize: 1
                    }}
                }},
                x: {{
                    title: {{
                        display: true,
                        text: '小时 (24小时制)'
                    }}
                }}
            }}
        }}
    }});
    
    // 定时刷新数据 (可选)
    setInterval(async function() {{
        try {{
            const response = await fetch('/subscription/analytics-data');
            if (response.ok) {{
                const newData = await response.json();
                // 更新图表数据...
                console.log('订阅数据已更新');
            }}
        }} catch (e) {{
            console.log('数据更新失败:', e);
        }}
    }}, 300000); // 每5分钟更新
    """)
    
    content = Div(
        H1("频道订阅验证数据分析", cls="page-title"),
        
        # 返回链接
        Div(
            A("← 返回订阅管理", href="/subscription", cls="btn btn-outline"),
        ),
        
        charts_section,
        chart_script
    )
    
    return HTMLResponse(str(create_layout("订阅验证数据分析", content)))

async def _get_subscription_analytics_data() -> Dict[str, Any]:
    """获取订阅验证分析图表所需的数据"""
    try:
        # 获取趋势数据（近30天）
        trend_data = await _get_verification_trend_data(30)
        
        # 获取通过率统计
        pass_fail_stats = await _get_pass_fail_statistics()
        
        # 获取频道分布数据
        channel_distribution = await _get_channel_failure_distribution()
        
        # 获取失败原因分析
        failure_reasons = await _get_failure_reasons_analysis()
        
        # 获取时间分布数据
        time_distribution = await _get_time_distribution_data()
        
        return {
            # 验证趋势
            'trend_dates': trend_data['dates'],
            'trend_total': trend_data['total_counts'],
            'trend_failed': trend_data['failed_counts'],
            
            # 通过率
            'pass_count': pass_fail_stats['pass_count'],
            'fail_count': pass_fail_stats['fail_count'],
            
            # 频道分布
            'channel_names': channel_distribution['names'],
            'channel_failures': channel_distribution['failure_counts'],
            
            # 失败原因
            'failure_reasons': failure_reasons,
            
            # 时间分布
            'hour_labels': time_distribution['hours'],
            'hour_counts': time_distribution['counts']
        }
        
    except Exception as e:
        logger.error(f"获取订阅分析数据失败: {e}")
        # 返回默认数据
        return {
            'trend_dates': [], 'trend_total': [], 'trend_failed': [],
            'pass_count': 0, 'fail_count': 0,
            'channel_names': [], 'channel_failures': [],
            'failure_reasons': [],
            'hour_labels': [], 'hour_counts': []
        }

async def _get_verification_trend_data(days: int) -> Dict[str, List]:
    """获取验证趋势数据"""
    try:
        dates = []
        total_counts = []
        failed_counts = []
        
        for i in range(days):
            date = datetime.now().date() - timedelta(days=i)
            date_str = date.strftime('%m-%d')
            
            # 这里应该从日志系统获取实际数据
            # 模拟数据
            total_count = 0  # await logs_db.count_subscription_verifications(date)
            failed_count = 0  # await logs_db.count_subscription_failures(date)
            
            dates.append(date_str)
            total_counts.append(total_count)
            failed_counts.append(failed_count)
        
        # 反转数据，使最新日期在右边
        dates.reverse()
        total_counts.reverse()
        failed_counts.reverse()
        
        return {
            'dates': dates,
            'total_counts': total_counts,
            'failed_counts': failed_counts
        }
        
    except Exception as e:
        logger.error(f"获取验证趋势数据失败: {e}")
        return {'dates': [], 'total_counts': [], 'failed_counts': []}

async def _get_pass_fail_statistics() -> Dict[str, int]:
    """获取通过/失败统计"""
    try:
        # 这里应该从日志系统获取实际数据
        # 模拟数据
        pass_count = 0  # await logs_db.count_subscription_passes()
        fail_count = 0  # await logs_db.count_subscription_failures()
        
        return {'pass_count': pass_count, 'fail_count': fail_count}
        
    except Exception as e:
        logger.error(f"获取通过率统计失败: {e}")
        return {'pass_count': 0, 'fail_count': 0}

async def _get_channel_failure_distribution() -> Dict[str, List]:
    """获取频道失败分布数据"""
    try:
        # 获取配置的频道列表
        config = await system_config_manager.get_config(
            'subscription_verification_config',
            {"enabled": False, "required_subscriptions": []}
        )
        
        channels = config.get("required_subscriptions", [])
        names = [channel.get("display_name", "未命名") for channel in channels]
        
        # 这里应该统计每个频道的失败次数
        # 模拟数据
        failure_counts = [0] * len(names)
        
        return {'names': names, 'failure_counts': failure_counts}
        
    except Exception as e:
        logger.error(f"获取频道失败分布失败: {e}")
        return {'names': [], 'failure_counts': []}

async def _get_failure_reasons_analysis() -> List[Dict[str, Any]]:
    """获取失败原因分析"""
    try:
        # 这里应该从日志系统分析失败原因
        # 模拟数据结构
        reasons = [
            {"reason": "未订阅频道", "count": 0},
            {"reason": "API调用失败", "count": 0},
            {"reason": "用户已离开频道", "count": 0},
            {"reason": "频道不存在", "count": 0}
        ]
        
        return reasons
        
    except Exception as e:
        logger.error(f"获取失败原因分析失败: {e}")
        return []

async def _get_time_distribution_data() -> Dict[str, List]:
    """获取时间分布数据"""
    try:
        # 24小时分布
        hours = [f"{i:02d}:00" for i in range(24)]
        
        # 这里应该统计每小时的验证次数
        # 模拟数据
        counts = [0] * 24
        
        return {'hours': hours, 'counts': counts}
        
    except Exception as e:
        logger.error(f"获取时间分布数据失败: {e}")
        return {'hours': [], 'counts': []}

@require_auth
async def subscription_analytics_data_api(request: Request) -> Response:
    """订阅分析数据API (用于实时更新图表)"""
    try:
        data = await _get_subscription_analytics_data()
        return Response(
            content=json.dumps(data),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"获取订阅分析数据API失败: {e}")
        return Response(
            content=json.dumps({"error": "获取数据失败"}),
            status_code=500,
            media_type="application/json"
        )

# 导出路由
subscription_analytics_routes = [
    Route("/analytics", subscription_analytics_dashboard, methods=["GET"]),
    Route("/analytics-data", subscription_analytics_data_api, methods=["GET"]),
]
