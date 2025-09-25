"""
Charts Components - 统计图表组件

提供统计卡片、进度条、图表容器等组件。
支持数据可视化、指标展示、趋势分析等功能。

Usage:
    from web.components.charts import stats_card, progress_bar, chart_container
    
    card = stats_card("总用户", "1,234", "↑ 12%", "text-success")
    bar = progress_bar(75, "任务完成度")
"""

from typing import List, Dict, Any, Optional, Union
from fasthtml.common import *


def stats_card(
    title: str,
    value: Union[str, int, float],
    change: Optional[str] = None,
    change_class: str = "text-success",
    icon: Optional[str] = None,
    **kwargs
) -> Div:
    """
    创建统计卡片组件
    
    Args:
        title (str): 卡片标题
        value (Union[str, int, float]): 主要数值
        change (str, optional): 变化指示（如 "↑ 12%"）
        change_class (str): 变化指示的CSS类名
        icon (str, optional): 图标HTML或文本
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 统计卡片
        
    Example:
        card = stats_card(
            "总用户数", 
            "1,234",
            "↑ 12%",
            "text-success",
            icon="👥"
        )
    """
    card_content = []
    
    # 卡片头部（标题和图标）
    header_content = [Span(title, cls="text-sm text-gray-600")]
    if icon:
        header_content.insert(0, Span(icon, cls="text-lg mr-2"))
    
    card_content.append(
        Div(*header_content, cls="flex items-center mb-2")
    )
    
    # 主要数值
    card_content.append(
        Div(str(value), cls="text-2xl font-bold text-gray-800")
    )
    
    # 变化指示
    if change:
        card_content.append(
            Div(change, cls=f"text-sm {change_class} mt-1")
        )
    
    default_cls = "bg-white p-4 rounded-lg shadow border"
    cls = kwargs.pop('cls', default_cls)
    
    return Div(*card_content, cls=cls, **kwargs)


def progress_bar(
    value: Union[int, float],
    label: Optional[str] = None,
    max_value: Union[int, float] = 100,
    color_class: str = "progress-primary",
    show_percentage: bool = True,
    **kwargs
) -> Div:
    """
    创建进度条组件
    
    Args:
        value (Union[int, float]): 当前值
        label (str, optional): 进度条标签
        max_value (Union[int, float]): 最大值
        color_class (str): 进度条颜色类
        show_percentage (bool): 是否显示百分比
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 进度条容器
        
    Example:
        bar = progress_bar(75, "任务完成度", color_class="progress-success")
    """
    percentage = min(100, (value / max_value) * 100)
    
    content = []
    
    # 标签和百分比
    if label or show_percentage:
        header_content = []
        if label:
            header_content.append(Span(label, cls="text-sm font-medium"))
        if show_percentage:
            percentage_text = f"{percentage:.1f}%" if percentage != int(percentage) else f"{int(percentage)}%"
            header_content.append(Span(percentage_text, cls="text-sm text-gray-600"))
        
        if len(header_content) == 1:
            content.append(Div(header_content[0], cls="mb-1"))
        else:
            content.append(
                Div(
                    header_content[0],
                    header_content[1], 
                    cls="flex justify-between items-center mb-1"
                )
            )
    
    # 进度条
    content.append(
        Progress(
            value=percentage,
            max=100,
            cls=f"progress {color_class} w-full"
        )
    )
    
    container_cls = kwargs.pop('cls', 'mb-4')
    
    return Div(*content, cls=container_cls, **kwargs)


def chart_container(
    title: str,
    chart_content,
    subtitle: Optional[str] = None,
    actions: Optional[List] = None,
    **kwargs
) -> Div:
    """
    创建图表容器组件
    
    Args:
        title (str): 图表标题
        chart_content: 图表内容
        subtitle (str, optional): 副标题
        actions (List, optional): 操作按钮列表
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 图表容器
        
    Example:
        container = chart_container(
            "销售趋势",
            Div("图表内容"),
            subtitle="最近30天",
            actions=[Button("导出", cls="btn btn-sm")]
        )
    """
    container_content = []
    
    # 图表头部
    header_content = []
    
    # 标题部分
    title_content = [H3(title, cls="text-lg font-semibold")]
    if subtitle:
        title_content.append(P(subtitle, cls="text-sm text-gray-600"))
    
    header_content.append(Div(*title_content))
    
    # 操作按钮
    if actions:
        header_content.append(Div(*actions, cls="flex gap-2"))
    
    if len(header_content) > 1:
        container_content.append(
            Div(*header_content, cls="flex justify-between items-start mb-4")
        )
    else:
        container_content.append(
            Div(header_content[0], cls="mb-4")
        )
    
    # 图表内容
    container_content.append(chart_content)
    
    default_cls = "bg-white p-6 rounded-lg shadow border"
    cls = kwargs.pop('cls', default_cls)
    
    return Div(*container_content, cls=cls, **kwargs)


def metric_grid(metrics: List[Dict[str, Any]], columns: int = 3, **kwargs) -> Div:
    """
    创建指标网格布局
    
    Args:
        metrics (List[Dict]): 指标数据列表
        columns (int): 网格列数
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 指标网格容器
        
    Example:
        grid = metric_grid([
            {"title": "总用户", "value": "1,234", "change": "↑ 12%"},
            {"title": "活跃用户", "value": "856", "change": "↑ 8%"},
            {"title": "新增用户", "value": "89", "change": "↓ 3%"}
        ], columns=3)
    """
    grid_cards = []
    
    for metric in metrics:
        card = stats_card(
            title=metric.get('title', ''),
            value=metric.get('value', '0'),
            change=metric.get('change'),
            change_class=metric.get('change_class', 'text-success'),
            icon=metric.get('icon')
        )
        grid_cards.append(card)
    
    # 生成响应式网格类
    grid_classes = {
        1: "grid grid-cols-1 gap-4",
        2: "grid grid-cols-1 md:grid-cols-2 gap-4", 
        3: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4",
        4: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4",
        5: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4",
        6: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4"
    }
    
    grid_cls = grid_classes.get(columns, "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4")
    container_cls = kwargs.pop('cls', grid_cls)
    
    return Div(*grid_cards, cls=container_cls, **kwargs)


def simple_chart(
    chart_type: str,
    data: List[Dict[str, Any]],
    width: str = "100%",
    height: str = "300px",
    **kwargs
) -> Div:
    """
    创建简单图表（使用Canvas或SVG）
    
    Args:
        chart_type (str): 图表类型 (bar, line, pie)
        data (List[Dict]): 图表数据
        width (str): 图表宽度
        height (str): 图表高度
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 图表容器
        
    Example:
        chart = simple_chart("bar", [
            {"label": "一月", "value": 100},
            {"label": "二月", "value": 150},
            {"label": "三月", "value": 120}
        ])
    """
    chart_id = kwargs.pop('id', f"chart-{id(data)}")
    
    # 创建canvas元素
    canvas = Canvas(
        width=width.replace('%', '').replace('px', '') if width != "100%" else "400",
        height=height.replace('px', ''),
        id=chart_id,
        style=f"width: {width}; height: {height}; border: 1px solid #e5e7eb; border-radius: 0.5rem;"
    )
    
    # 生成图表脚本
    chart_script = Script(f"""
        document.addEventListener('DOMContentLoaded', function() {{
            const canvas = document.getElementById('{chart_id}');
            const ctx = canvas.getContext('2d');
            const data = {data};
            const chartType = '{chart_type}';
            
            // 简单的图表绘制逻辑
            function drawChart() {{
                const width = canvas.width;
                const height = canvas.height;
                const padding = 40;
                
                // 清空画布
                ctx.clearRect(0, 0, width, height);
                
                if (chartType === 'bar') {{
                    drawBarChart(ctx, data, width, height, padding);
                }} else if (chartType === 'line') {{
                    drawLineChart(ctx, data, width, height, padding);
                }} else if (chartType === 'pie') {{
                    drawPieChart(ctx, data, width, height);
                }}
            }}
            
            function drawBarChart(ctx, data, width, height, padding) {{
                const barWidth = (width - padding * 2) / data.length - 10;
                const maxValue = Math.max(...data.map(d => d.value));
                
                data.forEach((item, index) => {{
                    const barHeight = (item.value / maxValue) * (height - padding * 2);
                    const x = padding + index * (barWidth + 10);
                    const y = height - padding - barHeight;
                    
                    // 绘制柱子
                    ctx.fillStyle = '#3b82f6';
                    ctx.fillRect(x, y, barWidth, barHeight);
                    
                    // 绘制标签
                    ctx.fillStyle = '#374151';
                    ctx.font = '12px sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText(item.label, x + barWidth / 2, height - 10);
                    ctx.fillText(item.value, x + barWidth / 2, y - 5);
                }});
            }}
            
            function drawLineChart(ctx, data, width, height, padding) {{
                const stepX = (width - padding * 2) / (data.length - 1);
                const maxValue = Math.max(...data.map(d => d.value));
                
                ctx.beginPath();
                ctx.strokeStyle = '#3b82f6';
                ctx.lineWidth = 2;
                
                data.forEach((item, index) => {{
                    const x = padding + index * stepX;
                    const y = height - padding - (item.value / maxValue) * (height - padding * 2);
                    
                    if (index === 0) {{
                        ctx.moveTo(x, y);
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                    
                    // 绘制数据点
                    ctx.fillStyle = '#3b82f6';
                    ctx.beginPath();
                    ctx.arc(x, y, 3, 0, 2 * Math.PI);
                    ctx.fill();
                }});
                
                ctx.stroke();
            }}
            
            function drawPieChart(ctx, data, width, height) {{
                const centerX = width / 2;
                const centerY = height / 2;
                const radius = Math.min(width, height) / 2 - 20;
                const total = data.reduce((sum, item) => sum + item.value, 0);
                
                let currentAngle = 0;
                const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];
                
                data.forEach((item, index) => {{
                    const sliceAngle = (item.value / total) * 2 * Math.PI;
                    
                    ctx.beginPath();
                    ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
                    ctx.lineTo(centerX, centerY);
                    ctx.fillStyle = colors[index % colors.length];
                    ctx.fill();
                    
                    currentAngle += sliceAngle;
                }});
            }}
            
            drawChart();
        }});
    """)
    
    container_cls = kwargs.pop('cls', 'chart-container')
    
    return Div(
        canvas,
        chart_script,
        cls=container_cls,
        **kwargs
    )


def status_indicator(
    status: str,
    color_map: Optional[Dict[str, str]] = None,
    **kwargs
) -> Span:
    """
    创建状态指示器
    
    Args:
        status (str): 状态文本
        color_map (Dict, optional): 状态颜色映射
        **kwargs: 其他HTML属性
        
    Returns:
        Span: 状态指示器
        
    Example:
        indicator = status_indicator("正常", {
            "正常": "badge-success",
            "异常": "badge-error"
        })
    """
    if color_map is None:
        color_map = {
            "正常": "badge-success",
            "异常": "badge-error", 
            "警告": "badge-warning",
            "待处理": "badge-info",
            "已完成": "badge-success",
            "进行中": "badge-warning",
            "已取消": "badge-error"
        }
    
    badge_class = color_map.get(status, "badge-ghost")
    default_cls = f"badge {badge_class}"
    cls = kwargs.pop('cls', default_cls)
    
    return Span(status, cls=cls, **kwargs)


# 向后兼容的导出
__all__ = [
    'stats_card',
    'progress_bar',
    'chart_container',
    'metric_grid',
    'simple_chart',
    'status_indicator'
]