# -*- coding: utf-8 -*-
"""
认证路由模块
处理用户登录、登出和身份验证相关功能
"""

from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse

# 导入布局和认证组件
from ..layout import create_layout, okx_button, okx_input, okx_form_group
from ..services.auth_service import AuthService


def login_page(request: Request):
    """登录页面"""
    if AuthService.is_admin_session(request):
        return RedirectResponse(url="/", status_code=302)
    
    login_form = Form(
        Div(
            H2("管理员登录", cls="text-2xl font-bold text-center mb-6"),
            Div(
                okx_form_group("密码", okx_input("password", type="password", placeholder="请输入管理员密码")),
                okx_button("登录", type="submit", cls="btn btn-primary w-full"),
                cls="space-y-4"
            ),
            cls="card-body"
        ),
        method="post",
        action="/login",
        cls="card w-full max-w-sm mx-auto mt-16 shadow-xl bg-base-100"
    )
    
    return create_layout("管理员登录", login_form, show_nav=False)


async def login_submit(request: Request):
    """处理登录提交"""
    form = await request.form()
    password = form.get('password', '')
    
    # 调用服务层处理登录逻辑
    login_result = await AuthService.authenticate_admin(request, password)
    
    if login_result["success"]:
        return RedirectResponse(url="/", status_code=302)
    
    # 登录失败，重新显示登录页面
    error_form = Form(
        Div(
            H2("管理员登录", cls="text-2xl font-bold text-center mb-6"),
            Div(
                Div("密码错误，请重试", cls="alert alert-error mb-4"),
                okx_form_group("密码", okx_input("password", type="password", placeholder="请输入管理员密码")),
                okx_button("登录", type="submit", cls="btn btn-primary w-full"),
                cls="space-y-4"
            ),
            cls="card-body"
        ),
        method="post",
        action="/login",
        cls="card w-full max-w-sm mx-auto mt-16 shadow-xl bg-base-100"
    )
    
    return create_layout("管理员登录", error_form, show_nav=False)


def logout(request: Request):
    """登出"""
    AuthService.logout(request)
    return RedirectResponse(url="/login", status_code=302)