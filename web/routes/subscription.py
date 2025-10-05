# -*- coding: utf-8 -*-
"""
订阅验证路由模块
处理用户频道订阅验证和管理功能

页面功能（最小改动、对齐服务层字段规范）：
- 查看与切换“订阅验证开关”
- 查看必需订阅频道列表（标准键：chat_id/display_name/join_link）
- 添加必需订阅频道
- 删除必需订阅频道

说明：采用 POST + CSRF 提交动作，已在 web/app.py 注册对应 POST 路由，
与站内其他管理页保持一致的交互语义。
"""

import logging
from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse

# 导入布局和认证组件
from ..layout import (
    create_layout, require_auth,
    validate_csrf, get_or_create_csrf_token,
    okx_form_group, okx_input, okx_button, okx_select
)
from ..services.subscription_mgmt_service import SubscriptionMgmtService

logger = logging.getLogger(__name__)


@require_auth
async def subscription_dashboard(request: Request):
    """订阅验证管理页面（展示 + 表单，动作使用POST）"""
    try:
        # 顶部提示（从查询参数读取一次性反馈）
        params = request.query_params
        msg = None
        err = None
        if params.get('updated'):
            msg = '已更新订阅验证开关'
        if params.get('channel_added'):
            msg = '频道已添加'
        if params.get('channel_removed'):
            msg = '频道已移除'
        if params.get('error'):
            err = params.get('error')

        # 2) 拉取最新数据
        dashboard = await SubscriptionMgmtService.get_subscription_dashboard()
        config = dashboard.get('config') or {}
        status = dashboard.get('status') or {}
        channels = config.get('required_subscriptions', [])

        # 3) 生成 CSRF
        csrf = get_or_create_csrf_token(request)

        # 4) 顶部提示
        alert = None
        if err:
            alert = Div(
                Div("❌ " + str(err), cls="alert alert-error"),
                cls="mb-4"
            )
        elif msg:
            alert = Div(
                Div("✅ " + str(msg), cls="alert alert-success"),
                cls="mb-4"
            )

        # 5) 页面主体
        # 统计卡片
        stats = Div(
            Div(
                Div("当前状态", cls="text-sm text-gray-600"),
                Div("已启用" if status.get('enabled') else "已禁用",
                    cls=f"text-2xl font-bold {'text-green-600' if status.get('enabled') else 'text-gray-500'}"),
                cls="stat-card"
            ),
            Div(
                Div("必需频道数", cls="text-sm text-gray-600"),
                Div(str(status.get('required_channels', 0)), cls="text-2xl font-bold text-blue-600"),
                cls="stat-card"
            ),
            Div(
                Div("已订阅用户数(占位)", cls="text-sm text-gray-600"),
                Div(str(status.get('total_subscribed_users', 0)), cls="text-2xl font-bold text-purple-600"),
                cls="stat-card"
            ),
            cls="stats-container mb-6"
        )

        # 开关表单（POST + CSRF）
        toggle_form = Form(
            Input(type="hidden", name="csrf_token", value=csrf),
            okx_form_group(
                "启用订阅验证",
                okx_select("enabled", [("1", "启用"), ("0", "禁用")], selected=("1" if status.get('enabled') else "0")),
                help_text="开启后，非管理员用户与机器人交互前需关注配置的频道"
            ),
            okx_button("保存开关", type="submit", cls="btn btn-primary btn-sm"),
            method="post",
            action="/subscription/toggle",
            cls="bg-base-200 p-4 rounded-lg"
        )

        # 添加频道表单（POST + CSRF）
        add_form = Details(
            Summary("➕ 添加必需频道", cls="btn btn-primary btn-sm mb-2"),
            Form(
                Input(type="hidden", name="csrf_token", value=csrf),
                okx_form_group("展示名称", okx_input("display_name", placeholder="例如：官方频道", required=False)),
                okx_form_group("频道标识 chat_id", okx_input("chat_id", placeholder="@your_channel 或 -100xxxx", required=True),
                                help_text="用于机器人API校验订阅状态"),
                okx_form_group("加入链接 join_link", okx_input("join_link", placeholder="https://t.me/your_channel", required=False)),
                okx_button("添加", type="submit", cls="btn btn-success btn-sm"),
                method="post",
                action="/subscription/channels/add",
                cls="bg-base-200 p-4 rounded-lg"
            ),
            cls="mb-4"
        )

        # 频道表格
        table_rows = []
        for idx, ch in enumerate(channels, 1):
            name = ch.get('display_name') or ch.get('chat_id') or f"频道{idx}"
            chat_id = ch.get('chat_id', '')
            join_link = ch.get('join_link', '')

            actions = Div(
                A("🔗 链接", href=join_link or "#", cls="btn btn-xs btn-outline mr-1", target="_blank") if join_link else "",
                Form(
                    Input(type="hidden", name="csrf_token", value=csrf),
                    Input(type="hidden", name="chat_id", value=str(chat_id)),
                    Button("🗑️ 删除", type="submit", cls="btn btn-xs btn-error",
                           onclick="return confirm('确定删除该频道吗？')"),
                    method="post",
                    action="/subscription/channels/remove",
                    cls="inline-flex"
                ),
                cls="flex"
            )

            table_rows.append(
                Tr(
                    Td(str(idx)),
                    Td(name),
                    Td(Code(str(chat_id))),
                    Td(A(join_link, href=join_link, target="_blank") if join_link else Span("-", cls="text-gray-400")),
                    Td(actions)
                )
            )

        channels_table = Div(
            H3("必需订阅频道", cls="text-lg font-semibold mb-2"),
            Table(
                Thead(Tr(Th("#"), Th("名称"), Th("chat_id"), Th("加入链接"), Th("操作"))),
                Tbody(*table_rows if table_rows else [Tr(Td(Span("暂无配置", cls="text-gray-500"), colspan="5"))])
            ),
            cls="mb-6"
        )

        content = Div(
            H1("订阅验证管理", cls="page-title"),
            P("配置并管理机器人强制订阅（频道关注）功能", cls="page-subtitle"),
            alert or "",
            stats,
            Div(
                H3("功能开关", cls="text-lg font-semibold mb-2"),
                toggle_form,
                cls="mb-6"
            ),
            add_form,
            channels_table,
            Div(
                P("提示：本页已与机器人校验逻辑对齐，字段统一为 chat_id/display_name/join_link。", cls="text-sm text-gray-500")
            )
        )

        return create_layout("订阅验证管理", content)

    except Exception as e:
        logger.error(f"订阅验证管理页面错误: {e}")
        error_content = Div(
            H1("订阅验证管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600")
        )
        return create_layout("系统错误", error_content)


# === POST 动作路由（在 web/app.py 中注册） ===

@require_auth
async def subscription_toggle_post(request: Request):
    """切换订阅验证开关"""
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/subscription?error=csrf", status_code=302)

        enabled_raw = (form.get('enabled') or '').lower()
        enabled = enabled_raw in ('1', 'true', 'on', 'yes')

        current = await SubscriptionMgmtService.get_subscription_config()
        cfg = current.get('config') or {}
        required = cfg.get('required_subscriptions', [])

        result = await SubscriptionMgmtService.update_subscription_config(
            enabled=enabled,
            required_subscriptions=required,
            verification_message=cfg.get('verification_message'),
            bypass_for_premium=cfg.get('bypass_for_premium', False)
        )
        if result.get('success'):
            return RedirectResponse(url="/subscription?updated=1", status_code=302)
        else:
            return RedirectResponse(url=f"/subscription?error={result.get('error','update_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"切换订阅验证开关失败: {e}")
        return RedirectResponse(url="/subscription?error=toggle_exception", status_code=302)


@require_auth
async def subscription_add_channel_post(request: Request):
    """添加必需订阅频道"""
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/subscription?error=csrf", status_code=302)

        display_name = (form.get('display_name') or '').strip()
        chat_id = (form.get('chat_id') or '').strip()
        join_link = (form.get('join_link') or '').strip()
        if not chat_id:
            return RedirectResponse(url="/subscription?error=chat_id_required", status_code=302)

        result = await SubscriptionMgmtService.add_required_subscription(
            channel_id=chat_id, channel_name=display_name or chat_id, channel_url=join_link
        )
        if result.get('success'):
            return RedirectResponse(url="/subscription?channel_added=1", status_code=302)
        else:
            return RedirectResponse(url=f"/subscription?error={result.get('error','add_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"添加必需频道失败: {e}")
        return RedirectResponse(url="/subscription?error=add_exception", status_code=302)


@require_auth
async def subscription_remove_channel_post(request: Request):
    """删除必需订阅频道"""
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/subscription?error=csrf", status_code=302)

        chat_id = (form.get('chat_id') or '').strip()
        if not chat_id:
            return RedirectResponse(url="/subscription?error=chat_id_required", status_code=302)

        result = await SubscriptionMgmtService.remove_required_subscription(chat_id)
        if result.get('success'):
            return RedirectResponse(url="/subscription?channel_removed=1", status_code=302)
        else:
            return RedirectResponse(url=f"/subscription?error={result.get('error','remove_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"移除必需频道失败: {e}")
        return RedirectResponse(url="/subscription?error=remove_exception", status_code=302)
