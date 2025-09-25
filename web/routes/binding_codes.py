# -*- coding: utf-8 -*-
"""
绑定码管理路由模块
处理商户绑定码生成、管理和使用功能
从 web/app.py.backup 迁移的完整实现
"""

import logging
from datetime import datetime
from fasthtml.common import *
from starlette.requests import Request

# 导入布局和认证组件
from ..layout import create_layout, require_auth

# 导入数据库管理器（唯一调用链路：Route → DB Manager）
from database.db_binding_codes import binding_codes_manager

logger = logging.getLogger(__name__)


@require_auth
async def binding_codes_list(request: Request):
    """绑定码列表页面"""
    try:
        # 获取查询参数
        # 复选框在未勾选时不会提交参数；这里按“参数缺省 = 默认值”处理，
        # 勾选时参数值为 'true'，未勾选则视为 False。
        include_used = (
            (request.query_params.get("include_used") or "").lower() == "true"
            if ("include_used" in request.query_params) else False
        )
        include_expired = (
            (request.query_params.get("include_expired") or "").lower() == "true"
            if ("include_expired" in request.query_params) else False
        )
        plan_filter_raw = request.query_params.get("plan_days")
        plan_days_filter = int(plan_filter_raw) if (plan_filter_raw and plan_filter_raw.isdigit()) else None
        page = int(request.query_params.get("page", "1"))
        limit = 20  # 每页显示20条
        offset = (page - 1) * limit
        
        # 获取绑定码数据
        binding_data = await binding_codes_manager.get_all_binding_codes(
            include_used=include_used,
            include_expired=include_expired,
            limit=limit if page == 1 else None,  # 首页限制，后续加载更多
            plan_days=plan_days_filter
        )
        
        codes = binding_data.get("codes", [])
        total = binding_data.get("total", 0)
        
        # 获取统计信息
        stats = await binding_codes_manager.get_binding_code_statistics()
        
        # 分页处理
        displayed_codes = codes[offset:offset+limit] if page > 1 else codes[:limit]
        has_more = len(codes) > offset + limit or binding_data.get("has_more", False)
        
        # 构建表格行
        table_rows = []
        for code in displayed_codes:
            status_badge = Span(
                "已使用" if code.get('is_used') else "未使用",
                cls="badge badge-success" if code.get('is_used') else "badge badge-warning"
            )
            
            merchant_info = "未绑定"
            if code.get('merchant_name'):
                merchant_info = f"{code.get('merchant_name')} (ID: {code.get('merchant_id')})"
            
            expires_info = "永久有效"
            if code.get('expires_at'):
                expires_info = code.get('expires_at')
            
            actions = Div(
                A("详情", href=f"/binding-codes/{code['code']}/detail", 
                  cls="btn btn-xs btn-info mr-1"),
                Button("删除", onclick=f"confirmDeleteCode('{code['code']}')", 
                       cls="btn btn-xs btn-error mr-1"),
                cls="flex gap-1"
            )
            
            table_rows.append(
                Tr(
                    Td(code['code'], cls="font-mono"),
                    Td(status_badge),
                    Td(merchant_info),
                    Td(code.get('created_at', '')),
                    Td(expires_info),
                    Td((str(code.get('plan_days')) + ' 天') if code.get('plan_days') else '-'),
                    Td(code.get('used_at', '') or '-'),
                    Td(actions)
                )
            )
        
        # 过滤器表单
        filter_form = Form(
            Div(
                Div(
                    Label("显示选项:", cls="label label-text font-semibold"),
                    Div(
                        Label(
                            Input(type="checkbox", name="include_used", value="true",
                                  checked=include_used, cls="checkbox"),
                            Span("包含已使用", cls="label-text ml-2"),
                            cls="cursor-pointer flex items-center"
                        ),
                        Label(
                            Input(type="checkbox", name="include_expired", value="true",
                                  checked=include_expired, cls="checkbox"),
                            Span("包含已过期", cls="label-text ml-2"),
                            cls="cursor-pointer flex items-center"
                        ),
                        Div(
                            Label("绑定周期:", cls="label label-text font-semibold mr-2"),
                            Select(
                                Option("全部", value="", selected=(plan_days_filter is None)),
                                Option("7 天", value="7", selected=(plan_days_filter == 7)),
                                Option("23 天", value="23", selected=(plan_days_filter == 23)),
                                Option("30 天", value="30", selected=(plan_days_filter == 30)),
                                name="plan_days",
                                cls="select select-bordered select-sm"
                            ),
                            cls="flex items-center"
                        ),
                        cls="flex gap-4"
                    ),
                    cls="form-control"
                ),
                Button("筛选", type="submit", cls="btn btn-primary"),
                cls="flex items-end gap-4"
            ),
            method="GET",
            cls="bg-base-200 p-4 rounded mb-6"
        )
        
        # 统计卡片
        stats_cards = Div(
            Div(
                Div(
                    Div(
                        H3(str(stats.get('total_codes', 0)), cls="text-2xl font-bold"),
                        P("总绑定码", cls="text-sm opacity-60"),
                        cls="stat"
                    ),
                    Div(
                        H3(str(stats.get('valid_codes', 0)), cls="text-2xl font-bold text-success"),
                        P("未使用", cls="text-sm opacity-60"),
                        cls="stat"
                    ),
                    Div(
                        H3(str(stats.get('used_codes', 0)), cls="text-2xl font-bold text-warning"),
                        P("已使用", cls="text-sm opacity-60"),
                        cls="stat"
                    ),
                    Div(
                        H3(f"{stats.get('usage_rate', 0):.1f}%", cls="text-2xl font-bold text-info"),
                        P("使用率", cls="text-sm opacity-60"),
                        cls="stat"
                    ),
                    cls="stats shadow w-full"
                ),
                cls="mb-6"
            ),
        )
        
        # 主表格
        table = Div(
            Table(
                Thead(
                    Tr(
                        Th("绑定码", cls="w-32"),
                        Th("状态"),
                        Th("绑定商户"),
                        Th("创建时间"),
                        Th("过期时间"),
                        Th("绑定周期"),
                        Th("使用时间"),
                        Th("操作", cls="w-32")
                    )
                ),
                Tbody(*table_rows),
                cls="table table-zebra w-full"
            ),
            cls="overflow-x-auto bg-base-100 rounded-lg shadow"
        )
        
        # 分页
        pagination = ""
        if total > limit:
            pagination = Div(
                Div(
                    Button("上一页", 
                           onclick=f"loadPage({page-1})" if page > 1 else None,
                           disabled=page <= 1, cls="btn btn-sm"),
                    Span(f"第 {page} 页", cls="mx-4"),
                    Button("下一页", 
                           onclick=f"loadPage({page+1})" if has_more else None,
                           disabled=not has_more, cls="btn btn-sm"),
                    cls="join"
                ),
                cls="flex justify-center mt-6"
            )
        
        # 页面内容
        content = Div(
            # 页面标题
            Div(
                H1("绑定码管理", cls="page-title"),
                Div(
                    A("生成新绑定码", href="/binding-codes/generate", 
                      cls="btn btn-primary"),
                    A("导出数据", href="/binding-codes/export", 
                      cls="btn btn-secondary ml-2"),
                    cls="flex gap-2"
                ),
                cls="flex justify-between items-center mb-6"
            ),
            
            # 统计信息
            stats_cards,
            
            # 过滤器
            filter_form,
            
            # 数据表格
            table,
            
            # 分页
            pagination,
            
            # JavaScript
            Script("""
                function confirmDeleteCode(code) {
                    if (confirm('确定要删除这个绑定码吗？此操作不可撤销。')) {
                        fetch(`/binding-codes/${code}/delete`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            }
                        }).then(response => {
                            if (response.ok) {
                                location.reload();
                            } else {
                                alert('删除失败');
                            }
                        });
                    }
                }
                
                function loadPage(page) {
                    const params = new URLSearchParams(window.location.search);
                    params.set('page', page);
                    window.location.search = params.toString();
                }
            """)
        )
        
        return create_layout("绑定码管理", content)
        
    except Exception as e:
        logger.error(f"绑定码列表页面错误: {e}")
        error_content = Div(
            H1("页面错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"加载绑定码列表时发生错误: {str(e)}"),
            A("返回首页", href="/", cls="btn btn-primary mt-4")
        )
        return create_layout("页面错误", error_content)

@require_auth
async def binding_codes_generate_page(request: Request):
    """生成绑定码页面"""
    try:
        # 生成表单
        form = Form(
            Div(
                H2("生成新绑定码", cls="text-2xl font-bold mb-6"),
                
                # 数量选择
                Div(
                    Label("生成数量:", cls="label label-text font-semibold"),
                    Input(type="number", name="count", value="1", min="1", max="100",
                          cls="input input-bordered", required=True),
                    Div("一次最多生成100个绑定码", cls="text-sm text-gray-500 mt-1"),
                    cls="form-control mb-4"
                ),
                
                # 过期设置（失效时间，单位小时；与发布后的周期无关）
                Div(
                    Label("过期时间:", cls="label label-text font-semibold"),
                    Select(
                        Option("永不过期", value=""),
                        Option("1小时后", value="1"),
                        Option("24小时后", value="24"),
                        Option("7天后", value="168"),
                        Option("30天后", value="720"),
                        name="expiry_hours",
                        cls="select select-bordered"
                    ),
                    cls="form-control mb-6"
                ),

                # 绑定周期（发布后自动计算到期天数：7/23/30）
                Div(
                    Label("绑定周期(发布后)", cls="label label-text font-semibold"),
                    Select(
                        Option("不设置", value=""),
                        Option("7 天(首周)", value="7"),
                        Option("23 天(续费)", value="23"),
                        Option("30 天(整月)", value="30"),
                        name="plan_days",
                        cls="select select-bordered"
                    ),
                    Div("用于计算发布后的到期日，不体现在绑定码文本中。", cls="text-sm text-gray-500 mt-1"),
                    cls="form-control mb-6"
                ),
                
                # 操作按钮（提高层级，避免被上方选择器装饰层遮挡）
                Div(
                    Button("生成绑定码", type="submit", cls="btn btn-primary"),
                    A("取消", href="/binding-codes", cls="btn btn-ghost ml-2"),
                    cls="flex gap-2",
                    style="position:relative; z-index:1002;"
                ),
                
                cls="bg-base-100 p-6 rounded-lg shadow max-w-md mx-auto"
            ),
            method="POST",
            action="/binding-codes/generate"
        )
        
        content = Div(
            Div(
                A("← 返回绑定码管理", href="/binding-codes", 
                  cls="btn btn-ghost mb-4"),
                cls="mb-6"
            ),
            form
        )
        
        return create_layout("生成绑定码", content)
        
    except Exception as e:
        logger.error(f"绑定码生成页面错误: {e}")
        error_content = Div(
            H1("页面错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"加载生成页面时发生错误: {str(e)}"),
            A("返回绑定码管理", href="/binding-codes", cls="btn btn-primary mt-4")
        )
        return create_layout("页面错误", error_content)

@require_auth
async def binding_codes_generate_action(request: Request):
    """处理生成绑定码请求"""
    try:
        # 获取表单数据
        form_data = await request.form()
        # 生成数量
        raw_count = form_data.get("count", "1")
        try:
            count = int(str(raw_count).strip())
        except Exception:
            raise ValueError("生成数量必须是数字")
        # 过期时间：允许 '永不过期' 或空，及数字小时
        raw_expiry = form_data.get("expiry_hours")
        expiry_hours = None
        if raw_expiry is not None:
            s = str(raw_expiry).strip()
            if s == "":
                # 显式永不过期
                expiry_hours = 0
            elif s and s not in ("永不过期", "none", "null", "-1"):
                if s.isdigit():
                    expiry_hours = int(s)
                else:
                    # 容错：尝试去除非数字字符
                    import re
                    digits = "".join(re.findall(r"\d+", s))
                    expiry_hours = int(digits) if digits else None
        
        # 验证数量
        if count < 1 or count > 100:
            raise ValueError("生成数量必须在1-100之间")
        
        # 绑定周期 plan_days（7/23/30），用于“发布后”自动计算过期时间
        plan_days = None
        raw_plan = form_data.get("plan_days")
        if raw_plan:
            s = str(raw_plan).strip()
            if s.isdigit():
                plan_days = int(s)

        # 生成绑定码
        generated_codes = []
        for i in range(count):
            code_info = await binding_codes_manager.generate_binding_code(
                expiry_hours=expiry_hours,
                plan_days=plan_days
            )
            generated_codes.append(code_info)
        
        # 显示结果页面
        codes_list = Div(
            *[
                Div(
                    Div(code['code'], cls="font-mono text-lg font-bold"),
                    Div(f"过期时间: {code.get('expires_at', '永不过期')}", 
                        cls="text-sm text-gray-500"),
                    cls="bg-base-200 p-3 rounded mb-2"
                )
                for code in generated_codes
            ]
        )
        
        content = Div(
            Div(
                H1("绑定码生成成功", cls="text-2xl font-bold text-success mb-4"),
                P(f"已成功生成 {count} 个绑定码:", cls="mb-4"),
                
                codes_list,
                
                Div(
                    A("返回绑定码管理", href="/binding-codes", cls="btn btn-primary"),
                    A("继续生成", href="/binding-codes/generate", cls="btn btn-ghost ml-2"),
                    cls="mt-6 flex gap-2"
                ),
                
                cls="max-w-2xl mx-auto"
            )
        )
        
        return create_layout("生成成功", content)
        
    except Exception as e:
        logger.error(f"生成绑定码失败: {e}")
        error_content = Div(
            H1("生成失败", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"生成绑定码时发生错误: {str(e)}"),
            A("重试", href="/binding-codes/generate", cls="btn btn-primary mt-4"),
            A("返回管理", href="/binding-codes", cls="btn btn-ghost mt-4 ml-2")
        )
        return create_layout("生成失败", error_content)

@require_auth
async def binding_code_detail(request: Request):
    """绑定码详情页面"""
    try:
        # 获取路径参数
        code = request.path_params.get("code")
        if not code:
            raise ValueError("缺少绑定码")
        
        # 获取绑定码信息
        code_info = await binding_codes_manager.get_binding_code_info(code)
        if not code_info:
            raise ValueError("绑定码不存在")
        
        # 状态徽章
        status_badge = Span(
            "已使用" if code_info.get('is_used') else "未使用",
            cls="badge badge-lg " + ("badge-success" if code_info.get('is_used') else "badge-warning")
        )
        
        # 商户信息
        merchant_section = ""
        if code_info.get('merchant_name'):
            merchant_section = Div(
                H3("绑定商户信息", cls="text-lg font-bold mb-2"),
                Div(
                    P(f"商户名称: {code_info.get('merchant_name')}"),
                    P(f"商户ID: {code_info.get('merchant_id')}"),
                    P(f"Telegram ID: {code_info.get('merchant_chat_id', '未知')}"),
                    P(f"绑定时间: {code_info.get('used_at', '未知')}"),
                    cls="bg-base-200 p-4 rounded"
                ),
                cls="mb-6"
            )
        
        # 详情内容
        content = Div(
            # 页面标题
            Div(
                A("← 返回绑定码管理", href="/binding-codes", 
                  cls="btn btn-ghost mb-4"),
                H1("绑定码详情", cls="page-title"),
                cls="mb-6"
            ),
            
            # 基本信息卡片
            Div(
                H2("基本信息", cls="text-xl font-bold mb-4"),
                Div(
                    Div(
                        Div("绑定码", cls="font-semibold"),
                        Div(code_info['code'], cls="font-mono text-lg"),
                        cls="flex justify-between items-center py-2"
                    ),
                    Div(
                        Div("状态", cls="font-semibold"),
                        status_badge,
                        cls="flex justify-between items-center py-2"
                    ),
                    Div(
                        Div("创建时间", cls="font-semibold"),
                        Div(code_info.get('created_at', '未知')),
                        cls="flex justify-between items-center py-2"
                    ),
                    Div(
                        Div("过期时间", cls="font-semibold"),
                        Div(code_info.get('expires_at', '永久有效')),
                        cls="flex justify-between items-center py-2"
                    ),
                    cls="divide-y divide-base-300"
                ),
                cls="bg-base-100 p-6 rounded-lg shadow mb-6"
            ),
            
            # 商户信息（如果已绑定）
            merchant_section,
            
            # 操作按钮
            Div(
                Button("删除绑定码", 
                       onclick=f"confirmDeleteCode('{code}')",
                       cls="btn btn-error"),
                cls="flex gap-2"
            ),
            
            # JavaScript
            Script(f"""
                function confirmDeleteCode(code) {{
                    if (confirm('确定要删除这个绑定码吗？此操作不可撤销。')) {{
                        fetch(`/binding-codes/${{code}}/delete`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }}
                        }}).then(response => {{
                            if (response.ok) {{
                                window.location.href = '/binding-codes';
                            }} else {{
                                alert('删除失败');
                            }}
                        }});
                    }}
                }}
            """)
        )
        
        return create_layout("绑定码详情", content)
        
    except Exception as e:
        logger.error(f"绑定码详情页面错误: {e}")
        error_content = Div(
            H1("页面错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"加载绑定码详情时发生错误: {str(e)}"),
            A("返回绑定码管理", href="/binding-codes", cls="btn btn-primary mt-4")
        )
        return create_layout("页面错误", error_content)

@require_auth
async def binding_code_delete(request: Request):
    """删除绑定码"""
    try:
        # 获取路径参数
        code = request.path_params.get("code")
        if not code:
            raise ValueError("缺少绑定码")
        
        # 删除绑定码
        success = await binding_codes_manager.delete_binding_code(code)
        
        if success:
            # DB层已记录日志，避免重复
            return {"success": True, "message": "绑定码删除成功"}
        else:
            # 只在DB层操作失败时记录路由层日志
            logger.warning(f"绑定码删除失败: {code}")
            return {"success": False, "message": "绑定码删除失败"}
        
    except Exception as e:
        logger.error(f"删除绑定码错误: {e}")
        return {"success": False, "message": f"删除失败: {str(e)}"}

@require_auth
async def binding_codes_export(request: Request):
    """导出绑定码数据"""
    try:
        # 获取所有绑定码数据
        binding_data = await binding_codes_manager.get_all_binding_codes(
            include_used=True,
            include_expired=True
        )
        codes = binding_data.get("codes", [])
        
        # 创建CSV内容
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入标题行
        headers = [
            'ID', '绑定码', '状态', '商户ID', '商户名称', 
            '创建时间', '过期时间', '使用时间', '绑定用户名', '绑定用户姓名'
        ]
        writer.writerow(headers)
        
        # 写入数据行
        for code in codes:
            writer.writerow([
                code['id'],
                code['code'],
                '已使用' if code.get('is_used') else '未使用',
                code.get('merchant_id', ''),
                code.get('merchant_name', ''),
                code.get('created_at', ''),
                code.get('expires_at', ''),
                code.get('used_at', ''),
                code.get('bound_telegram_username', ''),
                code.get('bound_telegram_name', '')
            ])
        
        # 准备响应
        output.seek(0)
        filename = f"binding_codes_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        from starlette.responses import StreamingResponse
        
        def generate():
            yield output.getvalue().encode('utf-8-sig')  # BOM for Excel
        
        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出绑定码数据失败: {e}")
        error_content = Div(
            H1("导出失败", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"导出绑定码数据时发生错误: {str(e)}"),
            A("返回绑定码管理", href="/binding-codes", cls="btn btn-primary mt-4")
        )
        return create_layout("导出失败", error_content)
