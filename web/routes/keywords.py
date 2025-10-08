# -*- coding: utf-8 -*-
"""
关键词管理（配置中心）
功能：列表、创建、编辑（名称/排序/启用）、删除。
"""

from fasthtml.common import *
from starlette.requests import Request
from ..layout import require_auth, create_layout
from database.db_keywords import (
    get_all_keywords as db_get_all,
    create_keyword as db_create,
    update_keyword as db_update,
    delete_keyword as db_delete,
    KeywordManagerExtended
)


@require_auth
async def keywords_list(request: Request):
    params = request.query_params
    search = (params.get('search') or '').strip()
    keywords = await KeywordManagerExtended.get_all_keywords(order_by='display_order')
    # 过滤（可选）
    if search:
        keywords = [k for k in keywords if search in k.get('name','')]

    # 顶部：新增表单
    create_form = Form(
        Div(
            Label("新增关键词", cls="label"),
            Div(
                Input(name="name", placeholder="关键词（建议2-6字）", cls="input input-bordered w-full"),
                Input(name="display_order", type="number", placeholder="显示顺序", cls="input input-bordered w-32 ml-2"),
                Button("创建", type="submit", cls="btn btn-primary ml-2"),
                cls="flex"
            ),
            cls="form-control"
        ),
        method="post", action="/config/keywords/create",
        cls="card bg-base-100 shadow p-4 mb-4"
    )

    rows = []
    for k in keywords:
        kid = k['id']
        rows.append(
            Tr(
                Td(str(kid)),
                Td(k.get('name','-')),
                Td(str(k.get('usage_count',0))),
                Td(str(k.get('display_order',0))),
                Td(
                    Div(
                        # 编辑（名称+顺序）
                        Form(
                            Input(type="hidden", name="id", value=str(kid)),
                            Input(name="name", value=k.get('name',''), cls="input input-bordered w-40"),
                            Input(name="display_order", type="number", value=str(k.get('display_order',0)), cls="input input-bordered w-24 ml-2"),
                            Button("保存", type="submit", cls="btn btn-sm btn-primary ml-2"),
                            method="post", action="/config/keywords/update",
                            cls="inline-flex"
                        ),
                        Form(
                            Button("删除", type="submit", cls="btn btn-sm btn-error ml-2",
                                   onclick="return confirm('确定删除该关键词？会从商户关联中移除');"),
                            method="post", action=f"/config/keywords/{kid}/delete",
                            cls="inline-flex"
                        ),
                        cls="flex items-center"
                    )
                )
            )
        )

    table = Table(
        Thead(Tr(
            Th("ID"), Th("名称"), Th("使用次数"), Th("显示顺序"), Th("操作")
        )),
        Tbody(*rows) if rows else Tbody(Tr(Td("暂无关键词", colspan="5", cls="text-center text-gray-500")))
    )

    content = Div(
        H1("关键词管理", cls="page-title"),
        create_form,
        Div(table, cls="card bg-base-100 shadow p-4"),
        cls="page-content"
    )
    return create_layout("关键词管理", content)


@require_auth
async def keywords_create(request: Request):
    form = await request.form()
    name = (form.get('name') or '').strip()
    try:
        display_order = int(form.get('display_order') or 0)
    except Exception:
        display_order = 0
    if name:
        try:
            await db_create(name, display_order)
        except Exception:
            pass
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/config/keywords", status_code=302)


@require_auth
async def keywords_update(request: Request):
    form = await request.form()
    try:
        kid = int(form.get('id') or 0)
    except Exception:
        kid = 0
    name = (form.get('name') or '').strip() or None
    try:
        display_order = int(form.get('display_order') or 0)
    except Exception:
        display_order = None
    if kid:
        try:
            await db_update(kid, name=name, display_order=display_order)
        except Exception:
            pass
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/config/keywords", status_code=302)


@require_auth
async def keywords_delete(request: Request):
    kid = int(request.path_params.get('keyword_id'))
    try:
        await db_delete(kid)
    except Exception:
        pass
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/config/keywords", status_code=302)

