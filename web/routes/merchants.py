# -*- coding: utf-8 -*-
"""
商户管理路由模块
处理商户列表、审核、编辑等管理功能
"""

import logging
from fasthtml.common import *
from typing import Any
from starlette.requests import Request

# 导入布局和认证组件
from ..layout import (
    create_layout, require_auth,
    get_or_create_csrf_token, validate_csrf
)
from ..services.merchant_mgmt_service import MerchantMgmtService
from utils.enums import MERCHANT_STATUS

logger = logging.getLogger(__name__)


@require_auth
async def merchants_list(request: Request):
    """商户管理页面"""
    try:
        # 获取查询参数
        params = request.query_params
        # 分页参数
        page = int(params.get('page', '1') or '1')
        per_page = int(params.get('per_page', '20') or '20')
        # 默认显示“全部状态”（不筛选）
        status_filter_raw = params.get('status', '')
        status_filter = MERCHANT_STATUS.normalize(status_filter_raw) if status_filter_raw else ''
        search_query = params.get('search', '').strip()
        
        # 调用服务层获取商户数据和统计信息
        # 处理"全部状态"的空值，确保与旧版行为一致
        final_status = None if status_filter in ('', 'all') else status_filter
        
        merchants_data = await MerchantMgmtService.get_merchants_list(
            status=final_status,
            search=search_query,
            page=page,
            per_page=per_page
        )
        
        merchants = merchants_data["merchants"]
        stats = merchants_data["status_stats"]
        pagination = merchants_data["pagination"]
        # 严格以数据库字段为准，不做任何前端兜底拼装。
        
        # 创建商户管理页面
        content = Div(
            # 使用统一的页面头部
            Div(
                H1("商户管理", cls="page-title"),
                cls="page-header"
            ),
            
            # 使用统一的页面内容布局
            Div(
                # 数据统计
                Div(
                    H3("数据统计", cls="content-section-title"),
                    Div(
                        Div(
                            Div("商户总数", cls="stat-title"),
                            Div(str(stats.get("total", 0)), cls="stat-value text-primary"),
                            cls="stat"
                        ),
                        Div(
                            Div("待提交", cls="stat-title"),
                            Div(str(stats.get('pending_submission', 0)), cls="stat-value text-warning"),
                            cls="stat"
                        ),
                        Div(
                            Div("当前筛选总数", cls="stat-title"),
                            Div(str(pagination.get('total', len(merchants))), cls="stat-value text-secondary"),
                            cls="stat"
                        ),
                        Div(
                            Div("待审核", cls="stat-title"),
                            Div(str(stats.get('pending_approval', 0)), cls="stat-value text-warning"),
                            cls="stat"
                        ),
                        Div(
                            Div("已审核", cls="stat-title"),
                            Div(str(stats.get('approved', 0)), cls="stat-value text-success"),
                            cls="stat"
                        ),
                        cls="stats shadow mb-6"
                    )
                ),
                
                # 搜索筛选工具栏
                Div(
                    H3("搜索筛选", cls="text-xl font-semibold mb-4"),
                    Form(
                        Div(
                            # 状态筛选
                            Div(
                                Label("状态筛选", cls="label"),
                                Select(
                                    Option("待提交", value="pending_submission", selected=(status_filter == "pending_submission")),
                                    Option("待审核", value="pending_approval", selected=(status_filter == "pending_approval")),
                                    Option("已审核", value="approved", selected=(status_filter == "approved")),
                                    Option("已发布", value="published", selected=(status_filter == "published")),
                                    Option("已过期", value="expired", selected=(status_filter == "expired")),
                                    Option("全部状态", value="", selected=(status_filter == "" or status_filter == "all")),
                                    name="status",
                                    cls="select select-bordered w-full"
                                ),
                                cls="form-control min-w-[200px]"
                            ),
                            # 商户搜索
                            Div(
                                Label("商户搜索", cls="label"),
                                Input(
                                    name="search",
                                    placeholder="输入商户名称/ID、联系方式、地区或频道...",
                                    value=search_query,
                                    cls="input input-bordered w-full"
                                ),
                                cls="form-control flex-1"
                            ),
                            # 每页显示
                            Div(
                                Label("每页显示", cls="label"),
                                Select(
                                    Option("10条", value="10", selected=(str(per_page)=="10")),
                                    Option("20条", value="20", selected=(str(per_page)=="20")),
                                    Option("50条", value="50", selected=(str(per_page)=="50")),
                                    Option("100条", value="100", selected=(str(per_page)=="100")),
                                    name="per_page",
                                    cls="select select-bordered w-full"
                                ),
                                cls="form-control min-w-[160px]"
                            ),
                            # 按钮区域
                            Div(
                                Div(
                                    Button("搜索筛选", type="submit", cls="btn btn-primary"),
                                    Button("清除筛选", type="button", onclick="window.location.href='/merchants'", cls="btn btn-ghost ml-2"),
                                    cls="flex gap-2"
                                ),
                                cls="form-control md:self-end"
                            ),
                            cls="flex flex-col md:flex-row md:items-end gap-4"
                        ),
                        method="GET",
                        action="/merchants",
                        cls="card bg-base-100 shadow-xl p-6 mb-6"
                    )
                ),
                
                # 商户列表
                Div(
                    H3("商户列表", cls="text-xl font-semibold mb-4"),
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("ID", cls="whitespace-nowrap px-2 py-1 text-xs"),
                                    Th("商户名称", cls="whitespace-nowrap px-2 py-1 text-xs"),
                                    Th("联系方式", cls="whitespace-nowrap px-2 py-1 text-xs"),
                                    Th("地区", cls="whitespace-nowrap px-2 py-1 text-xs"),
                                    Th("频道用户名", cls="whitespace-nowrap px-2 py-1 text-xs"),
                                    Th("频道链接", cls="whitespace-nowrap px-2 py-1 text-xs"),
                                    Th("状态", cls="whitespace-nowrap px-2 py-1 text-xs"),
                                    Th("创建时间", cls="whitespace-nowrap px-2 py-1 text-xs"),
                                    Th("操作", cls="whitespace-nowrap px-2 py-1 text-xs text-right"),
                                )
                            ),
                            Tbody(
                                *[
                                    Tr(
                                        Td(str(merchant.get('id', '-')), cls="px-2 py-1 text-sm whitespace-nowrap"),
                                        Td(merchant.get('name', '-'), cls="px-2 py-1 text-sm whitespace-nowrap"),
                                        Td(merchant.get('contact_info', '-') or '-', cls="px-2 py-1 text-sm whitespace-nowrap"),
                                        Td(f"{merchant.get('city_name', '-')} - {merchant.get('district_name', '-')}", cls="px-2 py-1 text-sm whitespace-nowrap"),
                                        Td((lambda v: (str(v) if (v is not None and str(v).strip() != '') else '-'))(merchant.get('channel_chat_id')), cls="px-2 py-1 text-sm whitespace-nowrap font-mono"),
                                        Td(
                                            A(
                                                merchant.get('channel_link') or '-',
                                                href=merchant.get('channel_link') or '#',
                                                target="_blank" if merchant.get('channel_link') else None,
                                                rel="noopener" if merchant.get('channel_link') else None,
                                                cls="link truncate inline-block max-w-xs",
                                                **({} if merchant.get('channel_link') else {"onclick": "return false;"})
                                            ),
                                            cls="px-2 py-1 text-sm whitespace-nowrap"
                                        ),
                                        Td(
                                            (lambda s: Div(
                                                MERCHANT_STATUS.get_display_name(s),
                                                cls=f"badge badge-sm {MERCHANT_STATUS.get_badge_class(s)}"
                                            ))(merchant.get('status', 'unknown'))
                                        , cls="px-2 py-1 text-sm whitespace-nowrap"),
                                        Td(merchant.get('created_at', '-'), cls="px-2 py-1 text-sm whitespace-nowrap"),
                                Td(
                                    Div(
                                        A("详情", href=f"/merchants/{merchant.get('id')}/detail", cls="btn btn-xs btn-info"),
                                        A("帖子管理", href=f"/posts/{merchant.get('id')}", cls="btn btn-xs btn-secondary ml-1"),
                                        cls="flex justify-end"
                                    )
                                )
                            )
                                    for merchant in merchants
                                ] if merchants else [
                                    Tr(
                                        Td("暂无商户数据", colspan="9", cls="text-center text-gray-500")
                                    )
                                ]
                            ),
                            cls="table table-zebra table-compact w-full text-sm"
                        ),
                        cls="overflow-x-auto"
                    ),
                    cls="card bg-base-100 shadow-xl p-6"
                ),

                # 分页组件（与 /reviews 保持一致的本地实现）
                (lambda cur, pages, qp, pp, tot: _generate_pagination(cur, pages, qp, pp, tot) if pages and pages > 1 else Div())(
                    pagination.get('page', 1), pagination.get('pages', 1), request.query_params, pagination.get('per_page', per_page), pagination.get('total', 0)
                ),
                cls="page-content"
            )
        )
        
        return create_layout("商户管理", content)
        
    except Exception as e:
        logger.error(f"商户管理页面错误: {e}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        error_content = Div(
            H1("商户管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            Pre(f"{str(e)}\n\n{traceback.format_exc()}", cls="bg-gray-100 p-4 rounded text-sm")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def merchant_detail(request: Request):
    """商户只读详情页（管理动作以最小按钮形式提供）。"""
    merchant_id = int(request.path_params.get('merchant_id'))
    try:
        data = await MerchantMgmtService.get_merchant_detail(merchant_id)
        if not data.get('success'):
            return create_layout(
                "商户不存在",
                Div(H2("商户不存在", cls="text-2xl font-bold text-red-600 mb-4"), A("返回列表", href="/merchants", cls="btn btn-primary"))
            )

        merchant = data.get('merchant') or {}
        order_stats = data.get('order_stats') or {}
        review_stats = data.get('review_stats') or {}

        # 生成 CSRF token
        csrf = get_or_create_csrf_token(request)

        # 基本信息块
        base_info = Div(
            H3("基本信息", cls="text-xl font-semibold mb-3"),
            Table(
                Tbody(
                    Tr(Th("商户ID"), Td(str(merchant.get('id', '-')))),
                    Tr(Th("名称"), Td(merchant.get('name', '-') or '-')),
                    Tr(Th("联系方式"), Td(merchant.get('contact_info', '-') or '-')),
                    Tr(Th("地区"), Td(f"{merchant.get('city_name', '-') } - { merchant.get('district_name', '-') }")),
                    Tr(Th("价格"), Td(f"P: {merchant.get('p_price', '-') or '-'} / PP: {merchant.get('pp_price', '-') or '-'}")),
                    Tr(Th("一句话优势"), Td(merchant.get('adv_sentence', '-') or '-')),
                ),
                cls="table table-compact w-full"
            ),
            cls="card bg-base-100 shadow p-4"
        )

        # 渠道与时间
        channel_info = Div(
            H3("频道与时间", cls="text-xl font-semibold mb-3"),
            Table(
                Tbody(
                    Tr(Th("频道用户名/ID"), Td(merchant.get('channel_chat_id', '-') or '-')),
                    Tr(Th("频道链接"), Td(A(merchant.get('channel_link') or '-', href=merchant.get('channel_link') or '#', cls="link",
                                       **({} if merchant.get('channel_link') else {"onclick": "return false;"})))),
                    Tr(Th("状态"), Td(Span(MERCHANT_STATUS.get_display_name(merchant.get('status','unknown')), cls=f"badge {MERCHANT_STATUS.get_badge_class(merchant.get('status','unknown'))}"))),
                    Tr(Th("发布时间"), Td(merchant.get('publish_time', '-') or '-')),
                    Tr(Th("到期时间"), Td(merchant.get('expiration_time', '-') or '-')),
                )
            ),
            cls="card bg-base-100 shadow p-4"
        )

        # 统计
        stats = Div(
            H3("统计", cls="text-xl font-semibold mb-3"),
            Div(
                Div(Div("订单总数", cls="stat-title"), Div(str(order_stats.get('total_orders', 0)), cls="stat-value"), cls="stat"),
                Div(Div("已完成订单", cls="stat-title"), Div(str(order_stats.get('completed_orders', 0)), cls="stat-value text-success"), cls="stat"),
                Div(Div("评价总数", cls="stat-title"), Div(str(review_stats.get('total_reviews', 0)), cls="stat-value"), cls="stat"),
                cls="stats shadow"
            ),
            cls="card bg-base-100 shadow p-4"
        )

        # 管理动作（前端层：状态更新/刷新信息）
        current_status = str(merchant.get('status') or '')
        # 根据当前状态给出最小动作
        actions = []
        # 审核通过
        if current_status in {MERCHANT_STATUS.PENDING_SUBMISSION.value, MERCHANT_STATUS.PENDING_APPROVAL.value}:
            actions.append(
                Form(
                    Input(type="hidden", name="csrf_token", value=csrf),
                    Input(type="hidden", name="new_status", value=MERCHANT_STATUS.APPROVED.value),
                    Button("审核通过", type="submit", cls="btn btn-success btn-sm"),
                    method="post", action=f"/merchants/{merchant_id}/status"
                )
            )
        # 立即发布
        if current_status == MERCHANT_STATUS.APPROVED.value:
            actions.append(
                Form(
                    Input(type="hidden", name="csrf_token", value=csrf),
                    Input(type="hidden", name="new_status", value=MERCHANT_STATUS.PUBLISHED.value),
                    Button("立即发布", type="submit", cls="btn btn-info btn-sm"),
                    method="post", action=f"/merchants/{merchant_id}/status"
                )
            )
        # 设为过期
        if current_status == MERCHANT_STATUS.PUBLISHED.value:
            actions.append(
                Form(
                    Input(type="hidden", name="csrf_token", value=csrf),
                    Input(type="hidden", name="new_status", value=MERCHANT_STATUS.EXPIRED.value),
                    Button("设为过期", type="submit", cls="btn btn-warning btn-sm"),
                    method="post", action=f"/merchants/{merchant_id}/status"
                )
            )

        # 刷新Telegram资料
        actions.append(
            Form(
                Input(type="hidden", name="csrf_token", value=csrf),
                Button("刷新用户信息", type="submit", cls="btn btn-secondary btn-sm"),
                method="post", action=f"/merchants/{merchant_id}/refresh"
            )
        )

        actions_bar = Div(*actions, A("返回列表", href="/merchants", cls="btn btn-ghost btn-sm ml-2"), cls="flex gap-2 justify-end")

        content = Div(
            Div(H1("商户详情", cls="page-title"), P(f"ID: {merchant_id}", cls="page-subtitle"), cls="page-header"),
            Div(base_info, channel_info, stats, actions_bar, cls="space-y-4"),
            cls="page-content"
        )
        return create_layout("商户详情", content)
    except Exception as e:
        logger.error(f"商户详情页面错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return create_layout("错误", Div(P("加载失败"), P(str(e), cls="text-error")))


@require_auth
async def merchant_update_status(request: Request):
    """商户状态更新（POST + CSRF，前端层调用服务层批量接口）。"""
    merchant_id = int(request.path_params.get('merchant_id'))
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            from starlette.responses import RedirectResponse
            return RedirectResponse(url=f"/merchants/{merchant_id}/detail?error=csrf", status_code=302)
        new_status = str(form.get('new_status') or '').strip()
        if not new_status:
            from starlette.responses import RedirectResponse
            return RedirectResponse(url=f"/merchants/{merchant_id}/detail?error=empty_status", status_code=302)

        result = await MerchantMgmtService.batch_update_status([merchant_id], new_status)
        from starlette.responses import RedirectResponse
        if result.get('success'):
            return RedirectResponse(url=f"/merchants/{merchant_id}/detail?updated=1", status_code=302)
        return RedirectResponse(url=f"/merchants/{merchant_id}/detail?error=update_failed", status_code=302)
    except Exception as e:
        logger.error(f"更新商户状态失败: {e}")
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=f"/merchants/{merchant_id}/detail?error=exception", status_code=302)


@require_auth
async def merchant_refresh_info(request: Request):
    """刷新商户Telegram资料（POST + CSRF）。"""
    merchant_id = int(request.path_params.get('merchant_id'))
    form = await request.form()
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            from starlette.responses import RedirectResponse
            return RedirectResponse(url=f"/merchants/{merchant_id}/detail?error=csrf", status_code=302)
        result = await MerchantMgmtService.refresh_user_info(merchant_id)
        from starlette.responses import RedirectResponse
        if result.get('success'):
            return RedirectResponse(url=f"/merchants/{merchant_id}/detail?refreshed=1", status_code=302)
        return RedirectResponse(url=f"/merchants/{merchant_id}/detail?error=refresh_failed", status_code=302)
    except Exception as e:
        logger.error(f"刷新商户信息失败: {e}")
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=f"/merchants/{merchant_id}/detail?error=exception", status_code=302)


def _generate_pagination(current_page: int, total_pages: int, query_params, per_page: int, total_items: int) -> Any:
    """生成分页导航（复制并简化自 reviews/_generate_pagination）"""
    if total_pages <= 1:
        return Div()

    # 构建查询字符串（移除旧的page参数）
    query_dict = dict(query_params)
    if 'page' in query_dict:
        del query_dict['page']
    query_string = "&".join([f"{k}={v}" for k, v in query_dict.items() if v is not None and v != ""])
    query_prefix = f"?{query_string}&" if query_string else "?"

    pages = []

    if current_page > 1:
        pages.append(A("‹ 上一页", href=f"/merchants{query_prefix}page={current_page-1}", cls="btn btn-outline btn-sm"))

    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)

    for page_num in range(start_page, end_page + 1):
        if page_num == current_page:
            pages.append(Span(str(page_num), cls="btn btn-primary btn-sm"))
        else:
            pages.append(A(str(page_num), href=f"/merchants{query_prefix}page={page_num}", cls="btn btn-outline btn-sm"))

    if current_page < total_pages:
        pages.append(A("下一页 ›", href=f"/merchants{query_prefix}page={current_page+1}", cls="btn btn-outline btn-sm"))

    # 附带当前显示区间信息
    start_idx = (current_page - 1) * per_page + 1
    end_idx = min(current_page * per_page, total_items)
    info = P(f"显示第 {start_idx}-{end_idx} 条，共 {total_items} 条", cls="text-sm text-gray-500 mt-2")

    return Div(Div(*pages, cls="join"), info, cls="flex items-center justify-between mt-4 flex-wrap gap-2")
