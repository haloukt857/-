# -*- coding: utf-8 -*-
"""
模板管理路由
提供模板键的增删改查，持久化到 templates 表
"""

import logging
from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..layout import create_layout, require_auth
from database.db_templates import template_manager

logger = logging.getLogger(__name__)


@require_auth
async def templates_list(request: Request):
    try:
        params = dict(request.query_params)
        q = (params.get('q') or '').strip()
        prefix = (params.get('prefix') or '').strip()

        if prefix:
            templates = await template_manager.get_templates_by_prefix(prefix)
        else:
            templates = await template_manager.get_all_templates()

        if q:
            q_lower = q.lower()
            templates = [t for t in templates if q_lower in t['key'].lower() or q_lower in (t.get('content') or '').lower()]

        # 统计
        stats = await template_manager.get_template_statistics()

        # 过滤表单
        filter_form = Form(
            Div(
                Div(
                    Label("搜索关键词", cls="label"),
                    Input(name="q", value=q, placeholder="按键/内容搜索", cls="input input-bordered"),
                    cls="form-control"
                ),
                Div(
                    Label("前缀分类", cls="label"),
                    Input(name="prefix", value=prefix, placeholder="如 user_ / admin_", cls="input input-bordered"),
                    cls="form-control"
                ),
                cls="grid grid-cols-1 md:grid-cols-2 gap-4"
            ),
            Div(
                Button("筛选", type="submit", cls="btn btn-primary"),
                A("重置", href="/templates", cls="btn btn-ghost ml-2"),
                A("+ 新建模板", href="/templates/new", cls="btn btn-success ml-2"),
                cls="flex gap-2 mt-3"
            ),
            method="get"
        )

        # 列表表格
        table = Table(
            Thead(Tr(Th("键名"), Th("内容预览"), Th("最近更新"), Th("操作"))),
            Tbody(
                *[
                    Tr(
                        Td(Code(t['key'])),
                        Td(Div((t.get('content') or '')[:80] + ("..." if len(t.get('content') or '')>80 else ""), cls="truncate max-w-xl")),
                        Td(t.get('updated_at', '')),
                        Td(
                            Div(
                                A("编辑", href=f"/templates/{t['key']}/edit", cls="btn btn-sm btn-info mr-2"),
                                Form(
                                    Button("删除", type="submit", cls="btn btn-sm btn-error",
                                           onclick="return confirm('确定删除该模板？');"),
                                    method="post", action=f"/templates/{t['key']}/delete"
                                ),
                                cls="flex gap-2"
                            )
                        )
                    ) for t in templates
                ]
            ),
            cls="table w-full"
        )

        stats_cards = Div(
            Div(
                Div("总模板数", cls="stat-title"),
                Div(str(stats.get('total_templates', 0)), cls="stat-value"),
                cls="stat"
            ),
            Div(
                Div("最近7天更新", cls="stat-title"),
                Div(str(stats.get('recent_updates', 0)), cls="stat-value"),
                cls="stat"
            ),
            cls="stats shadow mb-4"
        )

        content = Div(
            Div(H1("模板管理"), cls="page-header"),
            Div(filter_form, cls="card bg-base-100 p-4 shadow mb-4"),
            stats_cards,
            Div(table, cls="overflow-x-auto card bg-base-100 p-4 shadow"),
            cls="page-content"
        )
        return create_layout("模板管理", content)
    except Exception as e:
        logger.error(f"模板管理页面错误: {e}")
        return create_layout("错误", Div(P("加载失败")))


@require_auth
async def template_new(request: Request):
    form = Form(
        Div(
            Div(Label("模板键名", cls="label"), Input(name="key", placeholder="例如 user_welcome_message", cls="input input-bordered"), cls="form-control mb-4"),
            Div(Label("模板内容", cls="label"), Textarea(name="content", cls="textarea textarea-bordered h-48"), cls="form-control"),
            cls="card bg-base-100 p-6 shadow max-w-3xl mx-auto"
        ),
        Div(Button("创建模板", type="submit", cls="btn btn-primary"), A("取消", href="/templates", cls="btn ml-2"), cls="flex justify-end mt-4"),
        method="post", action="/templates/create"
    )
    return create_layout("新建模板", Div(Div(H1("新建模板"), cls="page-header"), form, cls="page-content"))


@require_auth
async def template_create(request: Request):
    try:
        form = await request.form()
        key = (form.get('key') or '').strip()
        content = form.get('content') or ''
        if not key:
            raise ValueError("键名不能为空")
        ok = await template_manager.add_template(key, content)
        if ok:
            return RedirectResponse(url=f"/templates/{key}/edit", status_code=302)
        else:
            raise ValueError("创建失败，键可能已存在")
    except Exception as e:
        logger.error(f"创建模板失败: {e}")
        return create_layout("创建失败", Div(P(str(e)), A("返回", href="/templates", cls="btn btn-primary mt-4")))


@require_auth
async def template_edit(request: Request, key: str):
    try:
        info = await template_manager.get_template_info(key)
        if not info:
            raise ValueError("模板不存在")
        form = Form(
            Div(
                Div(Label("模板键名", cls="label"), Input(name="key", value=info['key'], readonly=True, cls="input input-bordered"), cls="form-control mb-4"),
                Div(Label("模板内容", cls="label"), Textarea(info.get('content',''), name="content", cls="textarea textarea-bordered h-72"), cls="form-control"),
                cls="card bg-base-100 p-6 shadow max-w-4xl mx-auto"
            ),
            Div(Button("保存", type="submit", cls="btn btn-primary"), A("返回列表", href="/templates", cls="btn ml-2"), cls="flex justify-end mt-4"),
            method="post", action=f"/templates/{key}/update"
        )
        return create_layout("编辑模板", Div(Div(H1(f"编辑模板 - {key}"), cls="page-header"), form, cls="page-content"))
    except Exception as e:
        logger.error(f"编辑模板页面失败: {e}")
        return create_layout("错误", Div(P("加载失败")))


@require_auth
async def template_update(request: Request, key: str):
    try:
        form = await request.form()
        content = form.get('content') or ''
        ok = await template_manager.update_template(key, content)
        if ok:
            return RedirectResponse(url=f"/templates/{key}/edit?updated=1", status_code=302)
        else:
            raise ValueError("保存失败")
    except Exception as e:
        logger.error(f"更新模板失败: {e}")
        return create_layout("保存失败", Div(P(str(e)), A("返回", href=f"/templates/{key}/edit", cls="btn btn-primary mt-4")))


@require_auth
async def template_delete(request: Request, key: str):
    try:
        ok = await template_manager.delete_template(key)
        return RedirectResponse(url="/templates", status_code=302)
    except Exception as e:
        logger.error(f"删除模板失败: {e}")
        return RedirectResponse(url="/templates", status_code=302)

