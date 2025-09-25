"""
Layout Components - 页面布局组件

从web/app.py.old中提取的布局相关组件，包含页面结构、导航菜单、容器等。
提供统一的页面布局标准和响应式设计。

Usage:
    from web.components.layouts import create_layout, create_page_container
    
    page = create_layout("页面标题", content)
    container = create_page_container(H1("标题"), P("内容"))
"""

import os
import time
from typing import List, Tuple, Union, Optional, Any
from fasthtml.common import *


def _okx_css_version() -> str:
    """
    获取OKX主题CSS文件版本号
    
    Returns:
        str: CSS文件的修改时间戳，用作缓存破坏参数
    """
    try:
        path = os.path.join("static", "css", "okx-theme.css")
        mtime = os.path.getmtime(path)
        return str(int(mtime))
    except Exception:
        return str(int(time.time()))


def create_layout(title: str, content, show_nav: bool = True):
    """
    创建页面布局 - 统一布局标准
    
    Args:
        title (str): 页面标题
        content: 页面内容元素
        show_nav (bool): 是否显示导航栏
        
    Returns:
        Html: 完整的HTML页面结构
        
    Example:
        page = create_layout("商户管理", 
                           Div(H1("商户列表"), P("内容")))
    """
    # 菜单项定义（避免重复）
    menu_items = [
        ("仪表板", "/", "/"),
        ("商户管理", "/merchants", "/merchants"),
        ("帖子管理", "/posts", "/posts"),
        ("订单管理", "/orders", "/orders"),
        ("评价管理", "/reviews", "/reviews"),
        ("订阅验证", "/subscription", "/subscription"),
        ("绑定码", "/binding-codes", "/binding-codes"),
        ("地区管理", "/regions", "/regions"),
        ("激励系统", "/incentives", "/incentives"),
    ]
    
    # 用户中心子菜单
    user_submenu = [
        ("用户列表", "/users", "/users"),
        ("用户分析", "/users/analytics", "/users/analytics"),
    ]
    
    # 创建菜单项的函数
    def create_menu_items(for_mobile=False):
        items = []
        for name, href, data_href in menu_items:
            items.append(Li(A(name, href=href, **{"data-href": data_href})))
        
        # 添加用户中心下拉菜单
        user_menu = Details(
            Summary("用户中心"),
            Ul(
                *[Li(A(name, href=href, **{"data-href": data_href})) for name, href, data_href in user_submenu]
            )
        )
        items.insert(4, Li(user_menu))  # 在订单管理后插入
        return items
    
    nav = Nav(
        Div(
            # 左侧：移动端菜单
            Div(
                # 移动端下拉菜单
                Div(
                    Label(
                        Span("☰", cls="text-xl"),
                        tabindex="0",
                        cls="btn btn-ghost lg:hidden"
                    ),
                    Ul(
                        *create_menu_items(for_mobile=True),
                        cls="menu menu-sm dropdown-content mt-3 z-[1] p-2 shadow bg-base-100 rounded-box w-56"
                    ),
                    cls="dropdown"
                ),
                cls="navbar-start"
            ),

            # 中间：桌面菜单
            Div(
                Ul(
                    *create_menu_items(),
                    cls="menu menu-horizontal px-1 hidden lg:flex"
                ),
                id="main-nav",
                cls="navbar-center"
            ),

            # 右侧：操作
            Div(
                A("退出", href="/logout", cls="btn btn-sm btn-outline"),
                cls="navbar-end"
            ),
            # 使用与页面内容相同的容器样式
            style="max-width: 1200px; margin: 0 auto; padding: 0 1.5rem;"
        ),
        cls="navbar bg-base-100 shadow sticky top-0 z-50"
    ) if show_nav else ""
    
    return Html(
        Head(
            Title(title),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            # 添加CSS样式链接
            Link(rel="preconnect", href="https://cdn.jsdelivr.net"),
            Link(rel="dns-prefetch", href="https://cdn.jsdelivr.net"),
            Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css"),
            Script(src="https://cdn.tailwindcss.com"),
            Link(rel="stylesheet", href=f"/static/css/okx-theme.css?v={_okx_css_version()}"),
        ),
        Body(
            nav,
            # 使用统一的页面容器类
            Div(
                content,
                cls="page-container"
            ),
            # 激活当前导航项的小脚本（基于 data-href 前缀匹配）
            Script(
                """
                document.addEventListener('DOMContentLoaded', function(){
                  var path = location.pathname;
                  document.querySelectorAll('#main-nav a[data-href]').forEach(function(a){
                    var href = a.getAttribute('data-href');
                    var isActive = (href === '/' && path === '/') || (href !== '/' && path.startsWith(href));
                    if (isActive) {
                      a.classList.add('active','btn-active');
                    }
                  });
                });
                """
            ),
            # 简易样式检测指示器（仅前端检测，不影响功能）
            Script(
                """
                document.addEventListener('DOMContentLoaded', function(){
                  try {
                    var bg = getComputedStyle(document.body).backgroundColor;
                    var fg = getComputedStyle(document.body).color;
                    var ok = (bg === 'rgb(0, 0, 0)' && fg === 'rgb(255, 255, 255)');
                    var el = document.createElement('div');
                    el.textContent = ok ? 'OKX CSS ✓' : 'CSS 未生效';
                    el.setAttribute('title', '点击隐藏');
                    el.style.cssText = 'position:fixed;right:10px;bottom:10px;z-index:9999;padding:6px 10px;border-radius:8px;font-size:12px;cursor:pointer;opacity:0.9;'+
                                      (ok ? 'background:#10b981;color:#000' : 'background:#ef4444;color:#fff');
                    el.onclick = function(){ this.remove(); };
                    document.body.appendChild(el);
                  } catch (e) { /* 忽略 */ }
                });
                """
            ),
            cls="min-h-screen bg-gray-50"
        )
    )


def create_page_container(*children, **kwargs) -> Div:
    """
    创建标准页面容器
    
    Args:
        *children: 子元素
        **kwargs: HTML属性
        
    Returns:
        Div: 页面容器
        
    Example:
        container = create_page_container(
            H1("标题"),
            P("内容"),
            cls="custom-class"
        )
    """
    default_cls = "page-container"
    cls = kwargs.pop('cls', default_cls)
    if cls != default_cls:
        cls = f"{default_cls} {cls}"
    
    return Div(*children, cls=cls, **kwargs)


def create_grid_layout(items: List, columns: int = 2, **kwargs) -> Div:
    """
    创建响应式网格布局
    
    Args:
        items (List): 网格项目列表
        columns (int): 桌面端列数
        **kwargs: HTML属性
        
    Returns:
        Div: 网格容器
        
    Example:
        grid = create_grid_layout([
            Div("卡片1"),
            Div("卡片2"), 
            Div("卡片3")
        ], columns=3)
    """
    grid_cls_map = {
        1: "grid grid-cols-1",
        2: "grid grid-cols-1 md:grid-cols-2 gap-4",
        3: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4",
        4: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4",
    }
    
    default_cls = grid_cls_map.get(columns, "grid grid-cols-1 md:grid-cols-2 gap-4")
    cls = kwargs.pop('cls', default_cls)
    
    return Div(*items, cls=cls, **kwargs)


def create_card(*children, title: str = None, **kwargs) -> Div:
    """
    创建标准卡片组件
    
    Args:
        *children: 卡片内容
        title (str, optional): 卡片标题
        **kwargs: HTML属性
        
    Returns:
        Div: 卡片容器
        
    Example:
        card = create_card(
            P("卡片内容"),
            title="我的卡片",
            cls="bg-white"
        )
    """
    card_content = []
    
    if title:
        card_content.append(
            Div(
                H3(title, cls="text-lg font-semibold"),
                cls="card-header p-4 border-b"
            )
        )
    
    card_content.append(
        Div(*children, cls="card-body p-4")
    )
    
    default_cls = "card bg-base-100 shadow rounded-lg"
    cls = kwargs.pop('cls', default_cls)
    
    return Div(*card_content, cls=cls, **kwargs)


def create_section(title: str, *children, **kwargs) -> Section:
    """
    创建页面区块
    
    Args:
        title (str): 区块标题
        *children: 区块内容
        **kwargs: HTML属性
        
    Returns:
        Section: 区块元素
        
    Example:
        section = create_section("统计数据",
                                P("这里是统计内容"),
                                cls="mb-6")
    """
    section_content = [
        H2(title, cls="text-xl font-bold mb-4")
    ]
    section_content.extend(children)
    
    default_cls = "section mb-6"
    cls = kwargs.pop('cls', default_cls)
    
    return Section(*section_content, cls=cls, **kwargs)


def create_breadcrumb(items: List[Union[str, Tuple[str, str]]], **kwargs) -> Div:
    """
    创建面包屑导航
    
    Args:
        items (List): 面包屑项目，可以是字符串或(text, href)元组
        **kwargs: HTML属性
        
    Returns:
        Div: 面包屑容器
        
    Example:
        breadcrumb = create_breadcrumb([
            ("首页", "/"),
            ("商户管理", "/merchants"),
            "商户详情"
        ])
    """
    breadcrumb_items = []
    
    for i, item in enumerate(items):
        if isinstance(item, tuple):
            text, href = item
            breadcrumb_items.append(
                A(text, href=href, cls="link link-hover")
            )
        else:
            breadcrumb_items.append(
                Span(item, cls="font-medium")
            )
        
        # 添加分隔符（除了最后一项）
        if i < len(items) - 1:
            breadcrumb_items.append(
                Span(" / ", cls="mx-2 text-gray-400")
            )
    
    default_cls = "breadcrumbs text-sm mb-4"
    cls = kwargs.pop('cls', default_cls)
    
    return Div(
        Ul(
            Li(*breadcrumb_items)
        ),
        cls=cls,
        **kwargs
    )


# 向后兼容的导出
__all__ = [
    'create_layout',
    'create_page_container',
    'create_grid_layout', 
    'create_card',
    'create_section',
    'create_breadcrumb',
    '_okx_css_version'
]