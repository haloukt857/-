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
from ..layout import create_layout, require_auth
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
                                cls="form-control"
                            ),
                            Div(
                                Label("商户搜索", cls="label"),
                                Input(
                                    name="search",
                                    placeholder="输入商户名称/ID、联系方式、地区或频道...",
                                    value=search_query,
                                    cls="input input-bordered w-full"
                                ),
                                cls="form-control"
                            ),
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
                                cls="form-control"
                            ),
                            Div(
                                Button("搜索筛选", type="submit", cls="btn btn-primary"),
                                Button("清除筛选", type="button", onclick="window.location.href='/merchants'", cls="btn btn-ghost ml-2"),
                                cls="form-control mt-4"
                            ),
                            cls="grid grid-cols-1 md:grid-cols-4 gap-4"
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
                                                A("查看", href=f"/posts/{merchant.get('id')}", cls="btn btn-xs btn-info"),
                                                A("编辑", href=f"/posts/{merchant.get('id')}?mode=edit", cls="btn btn-xs btn-secondary ml-1"),
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
