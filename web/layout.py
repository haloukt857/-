# -*- coding: utf-8 -*-
"""
Web面板 - 共享布局与认证模块

本文件包含Web应用共享的UI布局、认证装饰器和相关辅助函数，
旨在解决循环依赖问题，并提供一个统一的视觉和安全层。
"""

import os
import time
import hashlib
import asyncio
import secrets
import functools
from typing import Callable, Union, Any, Dict, List

from fasthtml.common import *
from starlette.responses import RedirectResponse
from starlette.requests import Request

# --- 认证管理 ---

class AuthManager:
    """Web后台认证管理器"""

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return hashlib.sha256(password.encode()).hexdigest() == hashed

    @staticmethod
    def is_admin_session(request: Request) -> bool:
        return request.session.get('is_admin', False)

    @staticmethod
    def login_admin(request: Request, admin_id: int) -> bool:
        from config import ADMIN_IDS
        if admin_id in ADMIN_IDS:
            request.session['is_admin'] = True
            request.session['admin_id'] = admin_id
            return True
        return False

    @staticmethod
    def logout(request: Request) -> None:
        request.session.clear()


def require_auth(func: Callable) -> Callable:
    """
    认证装饰器，确保用户已登录。
    如果未登录，则重定向到登录页面。
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any):
        request = args[0] if args else kwargs.get('request')
        if not request or not AuthManager.is_admin_session(request):
            return RedirectResponse(url="/login", status_code=302)
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    return wrapper

def get_or_create_csrf_token(request: Request) -> str:
    """获取或创建CSRF令牌"""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, token: str) -> bool:
    """验证CSRF令牌"""
    expected = request.session.get("csrf_token")
    return bool(expected and token and secrets.compare_digest(str(token), str(expected)))


# --- 布局与UI ---

def _okx_css_version() -> str:
    """获取OKX主题CSS文件的版本号（基于文件修改时间）"""
    try:
        path = os.path.join("static", "css", "okx-theme.css")
        mtime = os.path.getmtime(path)
        return str(int(mtime))
    except Exception:
        return str(int(time.time()))


def create_layout(title: str, content, show_nav: bool = True, include_charts: bool = False):
    """
    创建页面布局 - 统一布局标准
    所有页面都应使用此函数来确保外观和导航的一致性。
    
    Args:
        title: 页面标题
        content: 页面内容
        show_nav: 是否显示导航
        include_charts: 是否包含Chart.js库（用于数据分析页面）
    """
    # 菜单项定义
    menu_items = [
        ("仪表板", "/", "/"),
        ("商户管理", "/merchants", "/merchants"),
        ("帖子管理", "/posts", "/posts"),
        ("时间配置", "/schedule/time-slots", "/schedule/time-slots"),
        ("频道配置", "/channels/config", "/channels/config"),
        ("模板管理", "/templates", "/templates"),
        ("自动回复", "/auto-reply", "/auto-reply"),
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
            style="max-width: 1200px; margin: 0 auto; padding: 0 1.5rem;"
        ),
        cls="navbar bg-base-100 shadow sticky top-0 z-50"
    ) if show_nav else ""
    
    # 构建 HTML 头部元素
    head_elements = [
        Title(title),
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        Link(rel="preconnect", href="https://cdn.jsdelivr.net"),
        Link(rel="dns-prefetch", href="https://cdn.jsdelivr.net"),
        Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css"),
        Script(src="https://cdn.tailwindcss.com"),
        Link(rel="stylesheet", href=f"/static/css/okx-theme.css?v={_okx_css_version()}"),
    ]
    
    # 如果需要图表功能，添加Chart.js CDN
    if include_charts:
        head_elements.append(
            Script(src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js")
        )
    
    dev_tools_ui = []
    if os.getenv('RUN_MODE', 'dev') == 'dev':
        # 左下角开发工具按钮 + 模态框（仅开发环境显示）
        dev_tools_ui = [
            Div(
                Button("开发工具", id="devResetBtn", cls="btn btn-warning btn-xs", onclick="(function(){var m=document.getElementById('devResetModal'); if(m){ m.classList.add('modal-open'); }})();"),
                style="position:fixed;left:10px;bottom:10px;z-index:9999;"
            ),
            # 模态框
            Div(
                Div(
                    H3("开发工具", cls="text-lg font-bold mb-2"),
                    P("输入管理员密码，然后选择要执行的操作（仅开发环境）", cls="text-sm text-gray-500 mb-3"),
                    Div(
                        Label("操作：", cls="label mr-2"),
                        Select(
                            Option("重置模板", value="templates", selected=True),
                            Option("重置数据库(含商户/订单/地区/模板等)", value="database"),
                            id="devAction", cls="select select-bordered w-full max-w-xs"
                        ),
                        cls="flex items-center gap-2 mb-2"
                    ),
                    Div(
                        Label(Input(type="checkbox", id="devPreserveRegions", cls="checkbox checkbox-sm mr-2"), Span("保留城市/区县基础数据(自动导入种子)"), cls="flex items-center"),
                        P("仅对“重置数据库”生效", cls="text-xs text-gray-500 ml-6"),
                        cls="mb-3"
                    ),
                    Form(
                        Input(type="password", placeholder="管理员密码", id="devResetPwd", cls="input input-bordered w-full mb-3"),
                        Button("执行", id="devResetSubmit", cls="btn btn-error btn-sm"),
                        Button("取消", id="devResetCancel", type="button", cls="btn btn-ghost btn-sm ml-2"),
                    ),
                    cls="modal-box"
                ),
                id="devResetModal",
                cls="modal",
                style="z-index:10000;"
            ),
            Script(
                '''
                (function(){
                  const btn = document.getElementById('devResetBtn');
                  const modal = document.getElementById('devResetModal');
                  const cancel = document.getElementById('devResetCancel');
                  const submit = document.getElementById('devResetSubmit');
                  const pwd = document.getElementById('devResetPwd');
                  function selectedAction(){
                    const sel = document.getElementById('devAction');
                    return sel ? sel.value : 'templates';
                  }
                  if(!btn||!modal||!cancel||!submit||!pwd) return;
                  const openModal = ()=>{ modal.classList.add('modal-open'); pwd.value=''; pwd.focus(); };
                  const closeModal = ()=>{ modal.classList.remove('modal-open'); };
                  btn.addEventListener('click', openModal);
                  cancel.addEventListener('click', closeModal);
                  submit.addEventListener('click', async function(e){
                    e.preventDefault();
                    const password = pwd.value || '';
                    if(!password){ alert('请输入管理员密码'); return; }
                    const action = selectedAction();
                    try{
                      const url = action === 'database' ? '/dev/reset-database' : '/dev/reset-templates';
                      const preserveRegions = document.getElementById('devPreserveRegions').checked;
                      const res = await fetch(url, {
                        method:'POST',
                        headers:{'Content-Type':'application/json'},
                        body: JSON.stringify({password, preserve_regions: preserveRegions})
                      });
                      const data = await res.json();
                      if(data && data.success){
                        if(action==='database'){
                          alert('✅ 数据库已重置完成' + (data.backup? ('\n已备份: '+data.backup):''));
                          location.reload();
                        } else {
                          alert('✅ 模板已重置完成，更新数量: '+(data.updated||0));
                        }
                        closeModal();
                      }else{
                        alert('❌ 重置失败: '+(data && data.error ? data.error : '未知错误'));
                      }
                    }catch(err){
                      alert('❌ 请求失败: '+err);
                    }
                  });
                })();
                '''
            )
        ]

    # 固定在页面最左上角的品牌标识（不嵌入导航容器）
    brand_badge = Div(
        Div(
            A("好色仙人系统", href="/", cls="font-semibold text-base lg:text-lg leading-tight text-gray-200 hover:text-white whitespace-nowrap"),
        ),
        Div(
            A("TG: @Jiraiya_system", href="https://t.me/Jiraiya_system", target="_blank",
              cls="text-xs lg:text-sm text-gray-400 hover:text-gray-200 whitespace-nowrap"),
        ),
        cls="flex flex-col items-start",
        style="position:fixed;left:8px;top:10px;z-index:10000;line-height:1.1;"
    )

    return Html(
        Head(*head_elements),
        Body(
            brand_badge,
            nav,
            Div(
                content,
                cls="page-container"
            ),
            *dev_tools_ui,
            Script(
                '''
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
                '''
            ),
            Script(
                '''
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
                '''
            ),
            cls="min-h-screen bg-gray-50"
        )
    )


# --- UI 组件函数 ---

def okx_button(text: str, **kwargs):
    """OKX主题按钮组件"""
    cls = kwargs.pop('cls', 'btn btn-primary')
    return Button(text, cls=cls, **kwargs)


def okx_input(name: str = None, **kwargs):
    """OKX主题输入框组件"""
    cls = kwargs.pop('cls', 'input input-bordered w-full')
    if name:
        kwargs['name'] = name
    return Input(cls=cls, **kwargs)


def okx_textarea(name: str = None, **kwargs):
    """OKX主题文本域组件"""
    cls = kwargs.pop('cls', 'textarea textarea-bordered w-full')
    content = kwargs.pop('content', '')
    if name:
        kwargs['name'] = name
    return Textarea(content, cls=cls, **kwargs)


def okx_select(name: str = None, options: list = None, **kwargs):
    """OKX主题选择框组件"""
    cls = kwargs.pop('cls', 'select select-bordered w-full')
    selected = kwargs.pop('selected', None)
    if name:
        kwargs['name'] = name
    
    select_options = []
    if options:
        for option in options:
            if isinstance(option, (list, tuple)) and len(option) == 2:
                value, text = option
                is_selected = (str(value) == str(selected)) if selected is not None else False
                select_options.append(Option(text, value=value, selected=is_selected))
            else:
                is_selected = (str(option) == str(selected)) if selected is not None else False
                select_options.append(Option(option, value=option, selected=is_selected))
    
    return Select(*select_options, cls=cls, **kwargs)


def okx_form_group(label: str, input_element, help_text: str = None, **kwargs):
    """OKX主题表单组组件"""
    elements = [
        Label(label, cls="label label-text"),
        input_element
    ]
    if help_text:
        elements.append(P(help_text, cls="text-sm text-gray-500 mt-1"))
    
    return Div(
        *elements,
        cls="form-control w-full mb-4",
        **kwargs
    )
