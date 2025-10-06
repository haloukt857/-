# -*- coding: utf-8 -*-
"""
自动回复管理路由
最小化实现：触发词 + 回复消息的增删改与排序；无统计。
"""

import logging
from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..layout import (
    create_layout, require_auth,
    get_or_create_csrf_token, validate_csrf,
    okx_form_group, okx_input, okx_button, okx_select
)
from ..services.auto_reply_service import AutoReplyService

logger = logging.getLogger(__name__)


@require_auth
async def auto_reply_dashboard(request: Request):
    try:
        params = request.query_params
        msg = params.get('msg')
        err = params.get('err')

        csrf = get_or_create_csrf_token(request)
        triggers = await AutoReplyService.list_triggers(include_messages=True)

        # 顶部提示
        alert = None
        if err:
            alert = Div(Div(f"❌ {err}", cls="alert alert-error"), cls="mb-4")
        elif msg:
            alert = Div(Div(f"✅ {msg}", cls="alert alert-success"), cls="mb-4")

        # 新建触发词表单
        new_trigger_form = Form(
            Input(type="hidden", name="csrf_token", value=csrf),
            okx_form_group("触发词", okx_input("trigger_text", placeholder="例如：你好", required=True)),
            okx_form_group("匹配方式", okx_select("match_type", [("exact", "完全匹配"), ("contains", "包含匹配")], selected="contains")),
            okx_form_group("优先级", okx_input("priority_order", type="number", value="0")),
            okx_form_group("状态", okx_select("is_active", [("1", "启用"), ("0", "禁用")], selected="1")),
            okx_button("添加触发词", type="submit", cls="btn btn-success btn-sm"),
            method="post", action="/auto-reply/triggers/create",
            cls="space-y-3"
        )

        # 触发词 + 消息表
        rows = []
        for t in triggers:
            t_id = t.get('id')
            header = Tr(
                Td(Code(str(t_id))),
                Td(
                    Form(
                        Input(type="hidden", name="csrf_token", value=csrf),
                        Div(
                            okx_input("trigger_text", value=t.get('trigger_text', ''), required=True, cls="input input-bordered w-full"),
                            Button("保存", type="submit", cls="btn btn-xs btn-primary ml-2"),
                            cls="flex items-center gap-2"
                        ),
                        method="post", action=f"/auto-reply/triggers/{t_id}/update"
                    )
                ),
                Td(
                    Form(
                        Input(type="hidden", name="csrf_token", value=csrf),
                        Div(
                            okx_select("match_type", [("exact", "完全"), ("contains", "包含")], selected=t.get('match_type','contains')),
                            Button("保存", type="submit", cls="btn btn-xs btn-primary ml-2"),
                            cls="flex items-center gap-2"
                        ),
                        method="post", action=f"/auto-reply/triggers/{t_id}/update"
                    )
                ),
                Td(
                    Form(
                        Input(type="hidden", name="csrf_token", value=csrf),
                        Div(
                            okx_input("priority_order", type="number", value=str(t.get('priority_order',0))),
                            Button("保存", type="submit", cls="btn btn-xs btn-primary ml-2"),
                            cls="flex items-center gap-2"
                        ),
                        method="post", action=f"/auto-reply/triggers/{t_id}/update"
                    )
                ),
                Td(
                    Form(
                        Input(type="hidden", name="csrf_token", value=csrf),
                        Div(
                            okx_select("is_active", [("1","启用"),("0","禁用")], selected=("1" if t.get('is_active') else "0")),
                            Button("保存", type="submit", cls="btn btn-xs btn-primary ml-2"),
                            cls="flex items-center gap-2"
                        ),
                        method="post", action=f"/auto-reply/triggers/{t_id}/update"
                    )
                ),
                Td(
                    Form(
                        Input(type="hidden", name="csrf_token", value=csrf),
                        Button("删除", cls="btn btn-xs btn-error", type="submit", onclick="return confirm('确定删除触发词及其消息？')"),
                        method="post", action=f"/auto-reply/triggers/{t_id}/delete"
                    )
                )
            )
            rows.append(header)

            # 该触发词的消息行
            messages = t.get('messages', []) or []
            if messages:
                for m in messages:
                    m_id = m.get('id')
                    rows.append(
                        Tr(
                            Td("↳", cls="text-gray-500"),
                            Td(
                                Form(
                                    Input(type="hidden", name="csrf_token", value=csrf),
                                    Div(
                                        okx_input("message_content", value=m.get('message_content',''), cls="input input-bordered w-full"),
                                        Button("保存", type="submit", cls="btn btn-xs btn-primary ml-2"),
                                        cls="flex items-center gap-2"
                                    ),
                                    method="post", action=f"/auto-reply/messages/{m_id}/update"
                                )
                            ),
                            Td(Span("消息", cls="text-xs text-gray-400")),
                            Td(
                                Form(
                                    Input(type="hidden", name="csrf_token", value=csrf),
                                    Div(
                                        okx_input("display_order", type="number", value=str(m.get('display_order',0))),
                                        Button("保存", type="submit", cls="btn btn-xs btn-primary ml-2"),
                                        cls="flex items-center gap-2"
                                    ),
                                    method="post", action=f"/auto-reply/messages/{m_id}/update"
                                )
                            ),
                            Td(
                                Form(
                                    Input(type="hidden", name="csrf_token", value=csrf),
                                    Div(
                                        okx_select("is_active", [("1","启用"),("0","禁用")], selected=("1" if m.get('is_active') else "0")),
                                        Button("保存", type="submit", cls="btn btn-xs btn-primary ml-2"),
                                        cls="flex items-center gap-2"
                                    ),
                                    method="post", action=f"/auto-reply/messages/{m_id}/update"
                                )
                            ),
                            Td(
                                Form(
                                    Input(type="hidden", name="csrf_token", value=csrf),
                                    Button("删除", cls="btn btn-xs btn-error", type="submit", onclick="return confirm('确定删除该回复？')"),
                                    method="post", action=f"/auto-reply/messages/{m_id}/delete"
                                )
                            )
                        )
                    )

            # 新增消息行
            # 新增行：使用 form 属性把不同单元格的控件绑定到同一个表单
            form_id = f"addmsg_{t_id}"
            rows.append(
                Tr(
                    Td("+", cls="text-gray-500"),
                    Td(
                        okx_input("message_content", placeholder="输入一条自动回复内容", required=True, cls="input input-bordered w-full", form=form_id)
                    ),
                    Td(Span("消息", cls="text-xs text-gray-400")),
                    Td(
                        okx_input("display_order", type="number", value="0", form=form_id)
                    ),
                    Td(
                        okx_select("is_active", [("1","启用"),("0","禁用")], selected="1", form=form_id)
                    ),
                    Td(
                        Form(
                            Input(type="hidden", name="csrf_token", value=csrf),
                            Input(type="hidden", name="trigger_id", value=str(t_id)),
                            Button("添加", type="submit", cls="btn btn-xs btn-success"),
                            method="post", action="/auto-reply/messages/create", id=form_id
                        )
                    )
                )
            )

        table = Table(
            Thead(Tr(Th("ID"), Th("触发词"), Th("匹配"), Th("排序"), Th("状态"), Th("操作"))),
            Tbody(*rows),
            cls="table w-full"
        )

        content = Div(
            H1("自动回复", cls="page-title"),
            alert or "",
            Div(
                H3("新建触发词", cls="text-lg font-semibold mb-2"),
                new_trigger_form,
                cls="card bg-base-100 shadow p-6 mb-6"
            ),
            Div(
                H3("触发词与回复", cls="text-lg font-semibold mb-2"),
                Div(table, cls="overflow-x-auto"),
                cls="card bg-base-100 shadow p-6"
            )
        )

        return create_layout("自动回复", content)
    except Exception as e:
        logger.error(f"自动回复管理页面错误: {e}")
        return create_layout("错误", Div(P("加载失败")))


# === POST 动作 ===

@require_auth
async def trigger_create_post(request: Request):
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token','')):
            return RedirectResponse(url="/auto-reply?err=csrf", status_code=302)
        text = (form.get('trigger_text') or '').strip()
        match_type = (form.get('match_type') or 'contains').strip()
        priority = int(form.get('priority_order') or 0)
        is_active = (form.get('is_active') or '1') == '1'
        admin_id = request.session.get('admin_id') or 0
        if not text:
            return RedirectResponse(url="/auto-reply?err=empty_trigger", status_code=302)
        res = await AutoReplyService.create_trigger(text, match_type, priority, is_active, admin_id)
        if res.get('success'):
            return RedirectResponse(url="/auto-reply?msg=created", status_code=302)
        return RedirectResponse(url=f"/auto-reply?err={res.get('error','create_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"创建触发词失败: {e}")
        return RedirectResponse(url="/auto-reply?err=exception", status_code=302)


@require_auth
async def trigger_update_post(request: Request):
    t_id = int(request.path_params.get('trigger_id'))
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token','')):
            return RedirectResponse(url="/auto-reply?err=csrf", status_code=302)
        text = form.get('trigger_text')
        match_type = form.get('match_type')
        is_active = None
        if form.get('is_active') is not None:
            is_active = (form.get('is_active') or '1') == '1'
        priority = form.get('priority_order')
        priority_val = int(priority) if priority not in (None, "") else None
        res = await AutoReplyService.update_trigger(t_id, text, match_type, priority_val, is_active)
        if res.get('success'):
            return RedirectResponse(url="/auto-reply?msg=updated", status_code=302)
        return RedirectResponse(url=f"/auto-reply?err={res.get('error','update_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"更新触发词失败: {e}")
        return RedirectResponse(url="/auto-reply?err=exception", status_code=302)


@require_auth
async def trigger_delete_post(request: Request):
    t_id = int(request.path_params.get('trigger_id'))
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token','')):
            return RedirectResponse(url="/auto-reply?err=csrf", status_code=302)
        res = await AutoReplyService.delete_trigger(t_id)
        if res.get('success'):
            return RedirectResponse(url="/auto-reply?msg=deleted", status_code=302)
        return RedirectResponse(url=f"/auto-reply?err={res.get('error','delete_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"删除触发词失败: {e}")
        return RedirectResponse(url="/auto-reply?err=exception", status_code=302)


@require_auth
async def message_create_post(request: Request):
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token','')):
            return RedirectResponse(url="/auto-reply?err=csrf", status_code=302)
        trigger_id = int(form.get('trigger_id'))
        content = (form.get('message_content') or '').strip()
        display_order = int(form.get('display_order') or 0)
        is_active = (form.get('is_active') or '1') == '1'
        if not content:
            return RedirectResponse(url="/auto-reply?err=empty_msg", status_code=302)
        res = await AutoReplyService.create_message(trigger_id, content, display_order, is_active)
        if res.get('success'):
            return RedirectResponse(url="/auto-reply?msg=msg_created", status_code=302)
        return RedirectResponse(url=f"/auto-reply?err={res.get('error','msg_create_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"创建消息失败: {e}")
        return RedirectResponse(url="/auto-reply?err=exception", status_code=302)


@require_auth
async def message_update_post(request: Request):
    m_id = int(request.path_params.get('message_id'))
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token','')):
            return RedirectResponse(url="/auto-reply?err=csrf", status_code=302)
        content = form.get('message_content')
        is_active = None
        if form.get('is_active') is not None:
            is_active = (form.get('is_active') or '1') == '1'
        display_order = form.get('display_order')
        display_val = int(display_order) if display_order not in (None, "") else None
        res = await AutoReplyService.update_message(m_id, content, display_val, is_active)
        if res.get('success'):
            return RedirectResponse(url="/auto-reply?msg=msg_updated", status_code=302)
        return RedirectResponse(url=f"/auto-reply?err={res.get('error','msg_update_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"更新消息失败: {e}")
        return RedirectResponse(url="/auto-reply?err=exception", status_code=302)


@require_auth
async def message_delete_post(request: Request):
    m_id = int(request.path_params.get('message_id'))
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token','')):
            return RedirectResponse(url="/auto-reply?err=csrf", status_code=302)
        res = await AutoReplyService.delete_message(m_id)
        if res.get('success'):
            return RedirectResponse(url="/auto-reply?msg=msg_deleted", status_code=302)
        return RedirectResponse(url=f"/auto-reply?err={res.get('error','msg_delete_failed')}", status_code=302)
    except Exception as e:
        logger.error(f"删除消息失败: {e}")
        return RedirectResponse(url="/auto-reply?err=exception", status_code=302)
