"""
Indicators Components - 状态指示器组件

提供状态徽章、加载指示器、提醒消息、通知等UI指示器组件。
支持不同状态、颜色、动画效果等。

Usage:
    from web.components.indicators import status_badge, loading_spinner, alert_message
    
    badge = status_badge("正常", "success")
    spinner = loading_spinner("加载中...")
    alert = alert_message("操作成功", "success")
"""

from typing import Optional, Dict, List, Union
from fasthtml.common import *


def status_badge(
    text: str,
    status_type: str = "default",
    size: str = "normal",
    **kwargs
) -> Span:
    """
    创建状态徽章组件
    
    Args:
        text (str): 徽章文本
        status_type (str): 状态类型 (success, error, warning, info, default)
        size (str): 徽章大小 (xs, sm, normal, lg)
        **kwargs: 其他HTML属性
        
    Returns:
        Span: 状态徽章
        
    Example:
        badge = status_badge("已审核", "success", "sm")
    """
    # 状态类型映射
    status_map = {
        "success": "badge-success",
        "error": "badge-error",
        "warning": "badge-warning", 
        "info": "badge-info",
        "primary": "badge-primary",
        "secondary": "badge-secondary",
        "accent": "badge-accent",
        "default": "badge-ghost"
    }
    
    # 大小映射
    size_map = {
        "xs": "badge-xs",
        "sm": "badge-sm", 
        "normal": "",
        "lg": "badge-lg"
    }
    
    badge_class = status_map.get(status_type, "badge-ghost")
    size_class = size_map.get(size, "")
    
    classes = ["badge", badge_class]
    if size_class:
        classes.append(size_class)
    
    default_cls = " ".join(classes)
    cls = kwargs.pop('cls', default_cls)
    
    return Span(text, cls=cls, **kwargs)


def loading_spinner(
    text: Optional[str] = None,
    size: str = "normal",
    inline: bool = False,
    **kwargs
) -> Div:
    """
    创建加载指示器组件
    
    Args:
        text (str, optional): 加载文本
        size (str): 大小 (xs, sm, normal, lg)
        inline (bool): 是否内联显示
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 加载指示器
        
    Example:
        spinner = loading_spinner("数据加载中...", "lg")
    """
    # 大小映射
    size_map = {
        "xs": "loading-xs",
        "sm": "loading-sm",
        "normal": "",
        "lg": "loading-lg"
    }
    
    size_class = size_map.get(size, "")
    
    # 加载动画
    spinner_classes = ["loading", "loading-spinner"]
    if size_class:
        spinner_classes.append(size_class)
    
    spinner_element = Span(cls=" ".join(spinner_classes))
    
    content = [spinner_element]
    
    if text:
        content.append(Span(text, cls="ml-2"))
    
    container_cls = "flex items-center" if inline else "flex items-center justify-center p-4"
    cls = kwargs.pop('cls', container_cls)
    
    return Div(*content, cls=cls, **kwargs)


def alert_message(
    message: str,
    alert_type: str = "info",
    closable: bool = False,
    icon: Optional[str] = None,
    **kwargs
) -> Div:
    """
    创建提醒消息组件
    
    Args:
        message (str): 消息内容
        alert_type (str): 提醒类型 (success, error, warning, info)
        closable (bool): 是否可关闭
        icon (str, optional): 图标
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 提醒消息
        
    Example:
        alert = alert_message("操作成功", "success", closable=True, icon="✓")
    """
    # 类型映射
    type_map = {
        "success": "alert-success",
        "error": "alert-error",
        "warning": "alert-warning",
        "info": "alert-info"
    }
    
    # 默认图标
    default_icons = {
        "success": "✓",
        "error": "✗",
        "warning": "⚠",
        "info": "ℹ"
    }
    
    alert_class = type_map.get(alert_type, "alert-info")
    display_icon = icon or default_icons.get(alert_type, "")
    
    content = []
    
    # 图标
    if display_icon:
        content.append(Span(display_icon, cls="text-lg"))
    
    # 消息内容
    content.append(Span(message))
    
    # 关闭按钮
    if closable:
        content.append(
            Button(
                "×",
                cls="btn btn-sm btn-circle btn-ghost ml-auto",
                onclick="this.parentElement.remove()"
            )
        )
    
    default_cls = f"alert {alert_class}"
    cls = kwargs.pop('cls', default_cls)
    
    return Div(*content, cls=cls, **kwargs)


def notification_toast(
    title: str,
    message: str = "",
    toast_type: str = "info",
    duration: int = 5000,
    **kwargs
) -> Div:
    """
    创建通知Toast组件
    
    Args:
        title (str): 通知标题
        message (str): 通知内容
        toast_type (str): 通知类型
        duration (int): 显示时长（毫秒）
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 通知Toast
        
    Example:
        toast = notification_toast("成功", "数据保存成功", "success", 3000)
    """
    toast_id = kwargs.pop('id', f"toast-{id(title)}")
    
    # 类型映射
    type_map = {
        "success": "alert-success",
        "error": "alert-error", 
        "warning": "alert-warning",
        "info": "alert-info"
    }
    
    alert_class = type_map.get(toast_type, "alert-info")
    
    content = []
    
    # 标题
    content.append(Div(title, cls="font-bold"))
    
    # 消息内容
    if message:
        content.append(Div(message, cls="text-sm"))
    
    # 关闭按钮
    content.append(
        Button(
            "×",
            cls="btn btn-sm btn-circle btn-ghost ml-auto",
            onclick=f"document.getElementById('{toast_id}').remove()"
        )
    )
    
    # 自动消失脚本
    auto_dismiss_script = Script(f"""
        setTimeout(function() {{
            const toast = document.getElementById('{toast_id}');
            if (toast) {{
                toast.style.opacity = '0';
                setTimeout(function() {{
                    toast.remove();
                }}, 300);
            }}
        }}, {duration});
    """)
    
    default_cls = f"alert {alert_class} shadow-lg mb-2"
    cls = kwargs.pop('cls', default_cls)
    
    return Div(
        *content,
        auto_dismiss_script,
        cls=cls,
        id=toast_id,
        **kwargs
    )


def progress_indicator(
    current: int,
    total: int,
    steps: Optional[List[str]] = None,
    **kwargs
) -> Div:
    """
    创建步骤进度指示器
    
    Args:
        current (int): 当前步骤
        total (int): 总步骤数
        steps (List[str], optional): 步骤名称列表
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 进度指示器
        
    Example:
        progress = progress_indicator(2, 4, ["填写信息", "提交审核", "等待批准", "完成"])
    """
    content = []
    
    # 步骤列表
    if steps and len(steps) >= total:
        step_items = []
        
        for i in range(total):
            step_num = i + 1
            is_current = step_num == current
            is_completed = step_num < current
            
            # 步骤状态类
            if is_completed:
                step_class = "step step-primary"
            elif is_current:
                step_class = "step step-primary"
            else:
                step_class = "step"
            
            step_items.append(
                Li(steps[i], cls=step_class, **{"data-content": "✓" if is_completed else str(step_num)})
            )
        
        content.append(
            Ul(*step_items, cls="steps steps-horizontal w-full")
        )
    else:
        # 简单进度条
        percentage = (current / total) * 100
        content.append(
            Div(
                Progress(value=percentage, max=100, cls="progress progress-primary w-full"),
                Div(f"步骤 {current}/{total}", cls="text-sm text-center mt-2")
            )
        )
    
    container_cls = kwargs.pop('cls', 'w-full')
    
    return Div(*content, cls=container_cls, **kwargs)


def status_dot(
    status: str = "default",
    animated: bool = False,
    **kwargs
) -> Span:
    """
    创建状态指示点
    
    Args:
        status (str): 状态类型
        animated (bool): 是否显示动画
        **kwargs: 其他HTML属性
        
    Returns:
        Span: 状态点
        
    Example:
        dot = status_dot("success", animated=True)
    """
    # 状态颜色映射
    color_map = {
        "success": "bg-green-500",
        "error": "bg-red-500",
        "warning": "bg-yellow-500",
        "info": "bg-blue-500",
        "default": "bg-gray-400"
    }
    
    color_class = color_map.get(status, "bg-gray-400")
    
    classes = [
        "inline-block",
        "w-3",
        "h-3", 
        "rounded-full",
        color_class
    ]
    
    if animated:
        classes.extend(["animate-pulse", "shadow-lg"])
    
    default_cls = " ".join(classes)
    cls = kwargs.pop('cls', default_cls)
    
    return Span(cls=cls, **kwargs)


def breadcrumb_indicator(
    items: List[Union[str, Dict[str, str]]],
    separator: str = ">",
    **kwargs
) -> Nav:
    """
    创建面包屑导航指示器
    
    Args:
        items (List): 面包屑项目
        separator (str): 分隔符
        **kwargs: 其他HTML属性
        
    Returns:
        Nav: 面包屑导航
        
    Example:
        breadcrumb = breadcrumb_indicator([
            {"text": "首页", "href": "/"},
            {"text": "商户管理", "href": "/merchants"},
            "商户详情"
        ])
    """
    breadcrumb_items = []
    
    for i, item in enumerate(items):
        if isinstance(item, dict):
            # 链接项
            link_text = item.get('text', '')
            link_href = item.get('href', '#')
            breadcrumb_items.append(
                A(link_text, href=link_href, cls="link link-hover")
            )
        else:
            # 文本项（通常是当前页）
            breadcrumb_items.append(
                Span(str(item), cls="font-medium")
            )
        
        # 添加分隔符（除了最后一项）
        if i < len(items) - 1:
            breadcrumb_items.append(
                Span(f" {separator} ", cls="mx-1 text-gray-400")
            )
    
    default_cls = "breadcrumbs text-sm"
    cls = kwargs.pop('cls', default_cls)
    
    return Nav(
        Ol(*[Li(item) for item in breadcrumb_items]),
        cls=cls,
        **kwargs
    )


# 向后兼容的导出
__all__ = [
    'status_badge',
    'loading_spinner',
    'alert_message',
    'notification_toast',
    'progress_indicator',
    'status_dot',
    'breadcrumb_indicator'
]