# -*- coding: utf-8 -*-
"""
手动广播页面与路由（最小功能）

提供：
- GET  /broadcast         页面（表单）
- POST /broadcast/send    发起广播任务
- GET  /broadcast/status  轮询任务状态（JSON）
"""

from __future__ import annotations

from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..layout import (
    create_layout,
    require_auth,
    get_or_create_csrf_token,
    validate_csrf,
    okx_form_group,
    okx_textarea,
    okx_input,
    okx_button,
)

from ..services import broadcast_service


@require_auth
async def broadcast_page(request: Request):
    csrf = get_or_create_csrf_token(request)
    form = Form(
        Input(type="hidden", name="csrf_token", value=csrf),
        okx_form_group(
            "消息内容",
            okx_textarea("text", rows=6, placeholder="请输入要发送的文本（1-4096 字）", required=True),
            help_text="仅支持纯文本。实际发送遵循 Telegram 速率限制。"
        ),
        okx_form_group(
            "预先检测活跃状态",
            Div(
                Label(
                    Input(type="checkbox", name="precheck_active", checked=True, cls="checkbox checkbox-sm mr-2"),
                    Span("先检测用户是否仍可接收消息（推荐）"),
                    cls="flex items-center"
                )
            ),
            help_text="通过 getChatMember/getChat 检测被拉黑/不可达用户并跳过，不发送任何消息。"
        ),
        okx_form_group(
            "测试用户ID",
            okx_input("test_user_id", type="number", placeholder="仅向该用户发送（可选）"),
            help_text="先用你的管理员ID测试，确认格式正确后再群发。"
        ),
        okx_form_group(
            "仅检测不发送",
            Div(
                Label(
                    Input(type="checkbox", name="dry_run", cls="checkbox checkbox-sm mr-2"),
                    Span("只进行活跃检测，不发送消息"),
                    cls="flex items-center"
                )
            ),
            help_text="用于全量健康扫描，结果会显示可达/不可达统计。"
        ),
        Div(
            okx_button("发送广播", type="submit", cls="btn btn-primary"),
            A("返回首页", href="/", cls="btn btn-ghost ml-2"),
            cls="mt-2"
        ),
        method="POST",
        action="/broadcast/send",
        cls="max-w-2xl"
    )

    tips = Div(
        H3("使用说明", cls="text-lg font-semibold mt-6 mb-2"),
        Ul(
            Li("速率：默认每秒最多 ~30 条；触发429将自动退避重试"),
            Li("失败示例：被拉黑/找不到用户会记录失败并继续"),
            Li("任务信息保存在内存中，进程重启会丢失进度"),
        ),
        cls="text-sm text-gray-600"
    )

    content = Div(
        H1("手动广播", cls="page-title"),
        form,
        tips,
        cls="page-content"
    )
    return create_layout("手动广播", content)


@require_auth
async def broadcast_send(request: Request):
    form = await request.form()
    token = form.get("csrf_token")
    if not validate_csrf(request, token):
        content = Div(P("CSRF 验证失败，请刷新后重试", cls="text-error"))
        return create_layout("提交失败", content)

    text = (form.get("text") or "").strip()
    if not text:
        content = Div(P("消息内容不能为空", cls="text-error"))
        return create_layout("提交失败", content)

    test_user_id = form.get("test_user_id") or None
    test_uid_val = None
    if test_user_id:
        try:
            test_uid_val = int(test_user_id)
        except Exception:
            content = Div(P("测试用户ID 必须为整数", cls="text-error"))
            return create_layout("提交失败", content)

    precheck_active = bool(form.get("precheck_active") is not None)
    dry_run = bool(form.get("dry_run") is not None)

    job_id = await broadcast_service.start_broadcast(
        text=text,
        test_user_id=test_uid_val,
        disable_notification=False,
        protect_content=False,
        precheck_active=precheck_active,
        dry_run=dry_run,
    )

    progress = Div(
        H3("任务已启动", cls="text-lg font-semibold mb-2"),
        P(f"Job ID: {job_id}", id="jobId", cls="text-xs text-gray-500 mb-3"),
        Div(
            Progress(value="0", max="100", id="prog", cls="progress progress-primary w-full"),
            P("准备中...", id="stats", cls="text-sm mt-2"),
            P("", id="prestats", cls="text-xs mt-1 text-gray-500"),
            cls="max-w-xl"
        ),
        Script(f"""
            (function(){{
              const jobId = '{job_id}';
              const prog = document.getElementById('prog');
              const stats = document.getElementById('stats');
              const prestats = document.getElementById('prestats');
              let timer = null;
              async function poll(){{
                try {{
                  const res = await fetch('/broadcast/status?job_id=' + encodeURIComponent(jobId));
                  const data = await res.json();
                  if (data && !data.error) {{
                    const total = data.total || 0;
                    const sent = data.sent || 0;
                    const success = data.success || 0;
                    const failed = data.failed || 0;
                    const rate = data.rate || 0;
                    const eta = data.eta_seconds;
                    const status = data.status;
                    const preTotal = data.prechecked_total;
                    const eligible = data.eligible_total;
                    const skipped = data.skipped_inactive;
                    const pct = total > 0 ? Math.floor(sent*100/total) : 0;
                    prog.value = String(pct);
                    stats.textContent = '状态: ' + status + ' | 进度: ' + sent + ' / ' + total + ' (' + pct + '%)'
                      + ' | 成功: ' + success + ' | 失败: ' + failed + ' | 速率: ' + rate + '/s'
                      + ' | ETA: ' + (eta == null ? '-' : (eta + 's'));
                    if (preTotal != null) {{
                      prestats.textContent = '预检: 可达 ' + (eligible || 0) + ' / ' + preTotal + ' ，跳过 ' + (skipped || 0);
                    }}
                    if (status === 'done' || status === 'failed') {{
                      clearInterval(timer);
                      timer = null;
                    }}
                  }} else {{
                    stats.textContent = '任务不存在或已过期';
                    clearInterval(timer);
                    timer = null;
                  }}
                }} catch (e) {{
                  stats.textContent = '轮询失败: ' + e;
                }}
              }}
              timer = setInterval(poll, 1000);
              poll();
            }})();
        """),
        cls="mt-6"
    )

    content = Div(
        H1("手动广播", cls="page-title"),
        progress,
        A("返回广播页面", href="/broadcast", cls="btn btn-ghost mt-4"),
        cls="page-content"
    )
    return create_layout("手动广播", content)


@require_auth
async def broadcast_status_api(request: Request):
    job_id = request.query_params.get("job_id") or ""
    data = await broadcast_service.get_status(job_id)
    return JSONResponse(data)
