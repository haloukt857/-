# -*- coding: utf-8 -*-
"""
订单管理路由模块
处理订单列表、状态更新、分析统计等功能
"""

import logging
from fasthtml.common import *
from config import DEEPLINK_BOT_USERNAME
from starlette.requests import Request

# 导入布局和认证组件
from ..layout import create_layout, require_auth, okx_form_group, okx_input, okx_button, okx_select
from ..services.order_mgmt_service import OrderMgmtService

logger = logging.getLogger(__name__)


@require_auth
async def orders_list(request: Request):
    """订单管理列表页面（对齐旧版功能）"""
    try:
        # 获取筛选参数（与旧版一致：status, merchant_id, customer_id, date_from, date_to）
        status_filter = request.query_params.get('status', '')
        merchant_filter = request.query_params.get('merchant_id', '')
        customer_filter = request.query_params.get('customer_id', '') 
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')
        search_query = request.query_params.get('search', '').strip()
        page = int(request.query_params.get('page', '1'))
        per_page = int(request.query_params.get('per_page', '20'))
        
        # 调用服务层获取订单数据（传入所有筛选参数）
        orders_data = await OrderMgmtService.get_orders_list(
            status_filter=status_filter if status_filter else None,
            merchant_filter=merchant_filter if merchant_filter else None, 
            user_filter=customer_filter if customer_filter else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            search_query=search_query if search_query else None,
            page=page,
            per_page=per_page
        )
        
        orders = orders_data["orders"]
        stats = orders_data["statistics"]
        pagination = orders_data["pagination"]
        merchants = orders_data["merchants"]
        users = orders_data["users"]
        
        # 构造商户价格映射用于价格后缀显示
        merchant_price_map = {}
        try:
            merchant_price_map = {m['id']: {'p': int(m.get('p_price') or 0), 'pp': int(m.get('pp_price') or 0)} for m in merchants}
        except Exception:
            merchant_price_map = {}

        def price_with_suffix(order: dict) -> str:
            try:
                price = int(order.get('price') or 0)
            except Exception:
                price = order.get('price') or 0
            suffix = ''
            ct = (order.get('course_type') or '').upper()
            if ct in ('P', 'PP'):
                suffix = ct.lower()
            else:
                mp = merchant_price_map.get(order.get('merchant_id') or 0) or {}
                if price and mp:
                    if price == mp.get('p'):
                        suffix = 'p'
                    elif price == mp.get('pp'):
                        suffix = 'pp'
            return f"¥{price}{suffix}"

        # 创建订单管理页面
        content = Div(
            # 页面头部
            Div(
                H1("订单管理", cls="page-title"),
                P("管理用户订单和商户交易", cls="page-subtitle"),
                cls="page-header"
            ),
            
            # 统计卡片
            Div(
                Div(
                    Div("订单总数", cls="stat-title"),
                    Div(str(stats.get("total_orders", 0)), cls="stat-value text-primary"),
                    cls="stat"
                ),
                Div(
                    Div("待处理", cls="stat-title"),
                    Div(str(stats.get("pending_orders", 0)), cls="stat-value text-warning"),
                    cls="stat"
                ),
                Div(
                    Div("已完成", cls="stat-title"),
                    Div(str(stats.get("completed_orders", 0)), cls="stat-value text-success"),
                    cls="stat"
                ),
                Div(
                    Div("今日订单", cls="stat-title"),
                    Div(str(stats.get("today_orders", 0)), cls="stat-value text-info"),
                    cls="stat"
                ),
                cls="stats shadow mb-6"
            ),
            
            # 搜索筛选表单（统一风格：一行多项+按钮对齐）
            Form(
                Div(
                    # 状态筛选
                    Div(
                        Label("状态筛选", cls="label"),
                        Select(
                            Option("全部状态", value="", selected=(status_filter == "")),
                            *[Option(((orders_data.get("status_options") or OrderMgmtService.STATUS_DISPLAY_MAP)[status]), value=status, selected=(status_filter == status))
                              for status in (orders_data.get("status_options") or OrderMgmtService.STATUS_DISPLAY_MAP).keys()],
                            name="status", cls="select select-bordered w-full"
                        ),
                        cls="form-control min-w-[180px]"
                    ),
                    # 商户筛选
                    Div(
                        Label("商户筛选", cls="label"),
                        Select(
                            Option("全部商户", value="", selected=(merchant_filter == "")),
                            *[Option(f"#{merchant['id']} - {merchant.get('name', '未设置')}", value=str(merchant['id']), selected=(merchant_filter == str(merchant['id']))) for merchant in merchants[:50]],
                            name="merchant_id", cls="select select-bordered w-full"
                        ),
                        cls="form-control min-w-[220px]"
                    ),
                    # 客户筛选
                    Div(
                        Label("客户筛选", cls="label"),
                        Select(
                            Option("全部客户", value="", selected=(customer_filter == "")),
                            *[Option(f"#{user['user_id']} - {user.get('username', '未设置')}", value=str(user['user_id']), selected=(customer_filter == str(user['user_id']))) for user in users[:50]],
                            name="customer_id", cls="select select-bordered w-full"
                        ),
                        cls="form-control min-w-[220px]"
                    ),
                    # 日期区间
                    Div(
                        Label("起止日期", cls="label"),
                        Div(
                            Input(type="date", name="date_from", value=date_from, cls="input input-bordered"),
                            Span("-", cls="mx-2"),
                            Input(type="date", name="date_to", value=date_to, cls="input input-bordered"),
                            cls="flex items-center"
                        ),
                        cls="form-control min-w-[260px]"
                    ),
                    # 按钮
                    Div(
                        Div(
                            Button("搜索", type="submit", cls="btn btn-primary"),
                            A("重置", href="/orders", cls="btn btn-ghost ml-2"),
                            cls="flex gap-2"
                        ),
                        cls="form-control md:self-end"
                    ),
                    cls="flex flex-col md:flex-row md:items-end gap-4 flex-wrap"
                ),
                method="GET",
                action="/orders",
                cls="card bg-base-100 shadow-xl p-6 mb-6"
            ),
            
            # 批量操作区域（对齐旧版）
            Form(
                Div(
                    Label("批量操作：", cls="label font-semibold"),
                    Div(
                        Input(type="checkbox", id="select_all", cls="checkbox mr-2"),
                        Label("全选", fr="select_all", cls="cursor-pointer"),
                        cls="flex items-center mr-4"
                    ),
                    Select(
                        Option("选择操作", value="", selected=True),
                        Option("批量完成", value="batch_complete"),
                        Option("批量标记已评价", value="batch_reviewed"), 
                        Option("批量取消", value="batch_cancel"),
                        Option("批量导出CSV", value="batch_export"),
                        name="batch_action", cls="select select-bordered mr-2"
                    ),
                    Button("执行", type="submit", cls="btn btn-secondary"),
                    cls="flex items-center gap-2"
                ),
                method="POST",
                action="/orders/batch",
                cls="card bg-base-100 shadow p-4 mb-4"
            ),
            
            # 订单列表（对齐旧版表格列）
            Div(
                Table(
                    Thead(
                        Tr(
                            Th(Input(type="checkbox", id="select_all_header", cls="checkbox")),  # 全选列
                            Th("订单ID"),
                            Th("商户"),  
                            Th("客户"),
                            Th("价格"),
                            Th("状态"),
                            Th("预约时间"),
                            Th("创建时间"),
                            Th("操作")
                        )
                    ),
                    Tbody(
                        *[
                            Tr(
                                Td(Input(type="checkbox", name="order_ids", value=str(order.get('id')), cls="checkbox")),
                                Td(f"#{order.get('id', '-')}", cls="font-mono"),
                                Td(f"#{order.get('merchant_id', '-')} - {order.get('merchant_name', '未设置')}"),
                                Td(f"#{order.get('customer_user_id', '-')} - {order.get('customer_username', '未设置')}"),
                                Td(price_with_suffix(order), cls="font-semibold text-success font-mono"),
                                Td(
                                    Span(
                                        OrderMgmtService.get_status_icon(order.get('status', '')),
                                        OrderMgmtService.get_status_display(order.get('status', '')),
                                        cls=f"badge badge-lg {OrderMgmtService.get_status_color(order.get('status', ''))} gap-1"
                                    )
                                ),
                                Td(order.get('appointment_time', '未设置')),
                                Td(order.get('created_at', '-')),
                                Td(
                                    Div(
                                        A("详情", href=f"/orders/{order.get('id')}", cls="btn btn-sm btn-info mr-1"),
                                        # 快速操作按钮（根据状态显示）
                                        *([A("完成", href=f"/orders/{order.get('id')}/complete", cls="btn btn-sm btn-success mr-1")] 
                                          if order.get('status') == '尝试预约' else []),
                                        *([A("标记评价", href=f"/orders/{order.get('id')}/mark_reviewed", cls="btn btn-sm btn-warning mr-1")] 
                                          if order.get('status') == '已完成' else []),
                                        A("取消", href=f"/orders/{order.get('id')}/cancel", cls="btn btn-sm btn-error"),
                                        cls="flex gap-1 flex-wrap"
                                    )
                                )
                            )
                            for order in orders
                        ] if orders else [
                            Tr(
                                Td("暂无订单数据", colspan="9", cls="text-center text-gray-500")
                            )
                        ]
                    ),
                    cls="table table-zebra w-full"
                ),
                cls="overflow-x-auto card bg-base-100 shadow-xl p-6"
            ),
            
            # 分页组件（保留筛选参数）
            Div(
                Div(f"共 {pagination['total']} 条记录，第 {pagination['page']}/{pagination['pages']} 页", 
                    cls="text-sm text-gray-500 mb-4"),
                Div(
                    *([A(str(p), 
                        href=f"/orders?page={p}&status={status_filter}&merchant_id={merchant_filter}&customer_id={customer_filter}&date_from={date_from}&date_to={date_to}&per_page={per_page}",
                        cls=f"btn btn-sm {'btn-primary' if p == pagination['page'] else 'btn-ghost'} mr-1")
                      for p in range(max(1, pagination['page'] - 2), min(pagination['pages'] + 1, pagination['page'] + 3))]
                     if pagination['pages'] > 1 else []),
                    cls="flex flex-wrap gap-1"
                ),
                cls="mt-6" if pagination['pages'] > 1 else "hidden"
            ),
            
            cls="page-content"
        )
        
        # 全选JavaScript脚本
        select_all_script = Script("""
        document.addEventListener('DOMContentLoaded', function() {
            const selectAllCheckbox = document.getElementById('select_all_header');
            const orderCheckboxes = document.querySelectorAll('input[name="order_ids"]');
            
            if (selectAllCheckbox) {
                selectAllCheckbox.addEventListener('change', function() {
                    orderCheckboxes.forEach(function(checkbox) {
                        checkbox.checked = selectAllCheckbox.checked;
                    });
                });
            }
        });
        """)
        
        return create_layout("订单管理", Div(content, select_all_script))
        
    except Exception as e:
        logger.error(f"订单管理页面错误: {e}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        error_content = Div(
            H1("订单管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            Pre(f"{str(e)}\n\n{traceback.format_exc()}", cls="bg-gray-100 p-4 rounded text-sm")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def order_detail(request: Request):
    """订单详情页面（对齐旧版功能）"""
    order_id = int(request.path_params['order_id'])
    
    try:
        # 获取订单详情
        detail_data = await OrderMgmtService.get_order_detail(order_id)
        
        if not detail_data['success']:
            error_content = Div(
                H2("订单不存在", cls="text-2xl font-bold text-red-600 mb-4"),
                P(detail_data.get('error', '未知错误')),
                A("返回订单列表", href="/orders", cls="btn btn-primary mt-4")
            )
            return create_layout("订单不存在", error_content)
        
        order = detail_data.get('order') or {}
        merchant = detail_data.get('merchant') or {}
        user = detail_data.get('user') or {}
        reviews = detail_data.get('reviews') or []
        status_info = detail_data.get('status_info') or {
            'display_name': '未知', 'color': 'ghost', 'icon': '❓'
        }
        
        # 价格+课程类型展示
        def price_with_suffix(order: dict, merchant: dict | None) -> str:
            try:
                price = int(order.get('price') or 0)
            except Exception:
                price = order.get('price') or 0
            suffix = ''
            ct = (order.get('course_type') or '').upper()
            if ct in ('P', 'PP'):
                suffix = ct.lower()
            else:
                try:
                    p = int((merchant or {}).get('p_price') or 0)
                    pp = int((merchant or {}).get('pp_price') or 0)
                    if price == p:
                        suffix = 'p'
                    elif price == pp:
                        suffix = 'pp'
                except Exception:
                    pass
            return f"¥{price}{suffix}"

        # 订单信息卡片
        order_info_card = Div(
            H3("📋 订单信息", cls="text-xl font-semibold mb-4"),
            Div(
                Div("订单状态", cls="stat-title"),
                Div(
                    Span(
                        status_info['icon'],
                        status_info['display_name'], 
                        cls=f"badge badge-lg {status_info['color']} gap-2"
                    ),
                    cls="stat-value text-sm"
                ),
                cls="stat"
            ),
            Div(
                Div("订单价格", cls="stat-title"),
                Div(price_with_suffix(order, merchant), cls="stat-value text-success"),
                cls="stat"
            ),
            Div(
                Div("创建时间", cls="stat-title"),
                Div(order.get('created_at', '未知'), cls="stat-value text-sm"),
                cls="stat"
            ),
            cls="stats shadow mb-6"
        )
        
        # 商户信息卡片
        merchant_card = Div(
            H3("🏪 商户信息", cls="text-xl font-semibold mb-4"),
            Div(
                P(f"商户名称: {(merchant or {}).get('name', '未设置')}", cls="text-lg font-semibold mb-2"),
                P(f"商户ID: #{(merchant or {}).get('id', '-')}", cls="text-gray-500 mb-2"),
                P(f"联系方式: {(merchant or {}).get('username', '未设置')}", cls="text-gray-500 mb-4"),
                Div(
                    A("查看商户详情", href=f"/posts/{(merchant or {}).get('id')}", cls="btn btn-info mr-2"),
                    A("联系商户", 
                      href=f"https://t.me/{DEEPLINK_BOT_USERNAME}?start=merchant_{(merchant or {}).get('id')}", 
                      target="_blank", cls="btn btn-primary"),
                    cls="flex gap-2"
                )
            ),
            cls="bg-base-200 p-4 rounded mb-6"
        )
        
        # 客户信息卡片
        user_card = Div(
            H3("👤 客户信息", cls="text-xl font-semibold mb-4"),
            Div(
                P(f"用户名: {(user or {}).get('username', '未设置')}", cls="text-lg font-semibold mb-2"),
                P(f"用户ID: #{(user or {}).get('user_id', '-')}", cls="text-gray-500 mb-2"),
            ),
            cls="bg-base-200 p-4 rounded mb-6"
        )
        
        # 评价信息（如果有）
        reviews_card = None
        if reviews:
            review_items = []
            for review in reviews[:3]:  # 显示最新3条评价
                review_items.append(Div(
                    P(f"评分: {'⭐' * review.get('rating', 0)}", cls="font-semibold mb-1"),
                    P(review.get('comment', '无评论'), cls="text-gray-600 mb-2"),
                    P(f"评价时间: {review.get('created_at', '')}", cls="text-sm text-gray-500"),
                    cls="border-b border-gray-200 pb-3 mb-3 last:border-b-0 last:mb-0 last:pb-0"
                ))
            
            reviews_card = Div(
                H3("⭐ 相关评价", cls="text-xl font-semibold mb-4"),
                Div(*review_items if review_items else [P("暂无评价", cls="text-gray-500")]),
                cls="bg-base-200 p-4 rounded mb-6"
            )
        
        # 状态更新表单
        status_update_form = Form(
            H3("🔄 状态更新", cls="text-xl font-semibold mb-4"),
            Div(
                Label("新状态:", cls="label"),
                Select(
                    *[Option(OrderMgmtService.get_status_display(status), value=status,
                           selected=(status == order.get('status')))
                      for status in OrderMgmtService.STATUS_DISPLAY_MAP.keys()],
                    name="status", cls="select select-bordered w-full mb-4"
                ),
                Label("备注 (可选):", cls="label"),
                Textarea(name="note", placeholder="更新原因或备注信息...", 
                        cls="textarea textarea-bordered w-full mb-4"),
                Button("更新状态", type="submit", cls="btn btn-primary"),
                cls="space-y-2"
            ),
            method="POST",
            action=f"/orders/{order_id}/update_status",
            cls="bg-base-200 p-4 rounded mb-6"
        )
        
        content = Div(
            H1(f"订单详情 - #{order_id}", cls="page-title"),
            P("查看和管理订单信息", cls="page-subtitle"),
            
            A("← 返回订单列表", href="/orders", cls="btn btn-outline mb-6"),
            
            # 左右分栏布局
            Div(
                # 左侧信息区
                Div(
                    order_info_card,
                    merchant_card,
                    user_card,
                    reviews_card if reviews_card else Div(),
                    cls="space-y-6"
                ),
                # 右侧操作区
                Div(
                    status_update_form,
                    cls="space-y-6"
                ),
                cls="grid grid-cols-1 lg:grid-cols-2 gap-8"
            ),
            
            cls="page-content"
        )
        
        return create_layout("订单详情", content)
        
    except Exception as e:
        logger.error(f"订单详情页面错误: order_id={order_id}, error={e}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        error_content = Div(
            H1("订单详情错误", cls="text-2xl font-bold text-red-600 mb-4"),
            Pre(f"{str(e)}\n\n{traceback.format_exc()}", cls="bg-gray-100 p-4 rounded text-sm")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def order_update_status(request: Request):
    """更新订单状态"""
    order_id = int(request.path_params['order_id'])
    
    try:
        form_data = await request.form()
        new_status = form_data.get('status')
        note = form_data.get('note', '').strip()
        
        # 调用服务层更新状态
        result = await OrderMgmtService.update_order_status(order_id, new_status, note)
        
        if result['success']:
            logger.info(f"订单状态更新成功: order_id={order_id}, status={new_status}")
            # 重定向回详情页
            from starlette.responses import RedirectResponse
            return RedirectResponse(url=f"/orders/{order_id}", status_code=302)
        else:
            error_content = Div(
                H2("更新失败", cls="text-2xl font-bold text-red-600 mb-4"),
                P(result.get('error', '未知错误')),
                A("返回订单详情", href=f"/orders/{order_id}", cls="btn btn-primary mt-4")
            )
            return create_layout("更新失败", error_content)
            
    except Exception as e:
        logger.error(f"更新订单状态失败: order_id={order_id}, error={e}")
        error_content = Div(
            H2("更新异常", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"更新订单状态时发生异常: {str(e)}"),
            A("返回订单详情", href=f"/orders/{order_id}", cls="btn btn-primary mt-4")
        )
        return create_layout("更新异常", error_content)


@require_auth
async def order_complete(request: Request):
    """快速操作：标记订单完成"""
    order_id = int(request.path_params['order_id'])
    
    try:
        result = await OrderMgmtService.update_order_status(order_id, "completed", "管理员快速完成操作")
        
        from starlette.responses import RedirectResponse
        if result['success']:
            return RedirectResponse(url=f"/orders/{order_id}", status_code=302)
        else:
            return RedirectResponse(url=f"/orders?error={result.get('error', '操作失败')}", status_code=302)
            
    except Exception as e:
        logger.error(f"快速完成订单失败: order_id={order_id}, error={e}")
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=f"/orders?error=操作异常", status_code=302)


@require_auth  
async def order_cancel(request: Request):
    """快速操作：取消订单"""
    order_id = int(request.path_params['order_id'])
    
    try:
        # 取消订单实际上是删除订单（对齐旧版行为）
        result = await OrderMgmtService.delete_order(order_id)
        
        from starlette.responses import RedirectResponse
        if result['success']:
            return RedirectResponse(url="/orders", status_code=302)
        else:
            return RedirectResponse(url=f"/orders?error={result.get('error', '取消失败')}", status_code=302)
            
    except Exception as e:
        logger.error(f"取消订单失败: order_id={order_id}, error={e}")
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=f"/orders?error=取消异常", status_code=302)


@require_auth
async def order_mark_reviewed(request: Request):
    """快速操作：标记已评价"""
    order_id = int(request.path_params['order_id'])
    
    try:
        result = await OrderMgmtService.update_order_status(order_id, "reviewed", "管理员标记已评价")
        
        from starlette.responses import RedirectResponse
        if result['success']:
            return RedirectResponse(url=f"/orders/{order_id}", status_code=302)
        else:
            return RedirectResponse(url=f"/orders?error={result.get('error', '标记失败')}", status_code=302)
            
    except Exception as e:
        logger.error(f"标记评价失败: order_id={order_id}, error={e}")
        from starlette.responses import RedirectResponse
        return RedirectResponse(url=f"/orders?error=标记异常", status_code=302)


@require_auth
async def orders_batch_operation(request: Request):
    """批量操作处理"""
    try:
        form_data = await request.form()
        batch_action = form_data.get('batch_action', '')
        order_ids = form_data.getlist('order_ids')
        
        if not batch_action:
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/orders?error=未选择操作类型", status_code=302)
        
        if not order_ids:
            from starlette.responses import RedirectResponse  
            return RedirectResponse(url="/orders?error=未选择订单", status_code=302)
        
        order_ids = [int(oid) for oid in order_ids]
        
        if batch_action == "batch_complete":
            result = await OrderMgmtService.batch_update_status(order_ids, "completed")
            
        elif batch_action == "batch_reviewed":
            result = await OrderMgmtService.batch_update_status(order_ids, "reviewed")
            
        elif batch_action == "batch_cancel":
            # 批量取消（删除）
            success_count = 0
            failed_count = 0
            for order_id in order_ids:
                del_result = await OrderMgmtService.delete_order(order_id)
                if del_result['success']:
                    success_count += 1
                else:
                    failed_count += 1
            result = {
                'success': success_count > 0,
                'success_count': success_count,
                'failed_count': failed_count,
                'message': f'成功取消 {success_count} 个订单，失败 {failed_count} 个'
            }
            
        elif batch_action == "batch_export":
            # 批量导出CSV
            return await orders_export_csv(request, order_ids)
            
        else:
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/orders?error=无效的操作类型", status_code=302)
        
        # 重定向返回列表页
        from starlette.responses import RedirectResponse
        if result['success']:
            return RedirectResponse(url=f"/orders?message={result['message']}", status_code=302)
        else:
            return RedirectResponse(url=f"/orders?error={result.get('error', '批量操作失败')}", status_code=302)
            
    except Exception as e:
        logger.error(f"批量操作失败: {e}")
        from starlette.responses import RedirectResponse
        return RedirectResponse(url="/orders?error=批量操作异常", status_code=302)


async def orders_export_csv(request: Request, order_ids: List[int] = None):
    """导出订单CSV"""
    try:
        # 获取筛选参数
        params = request.query_params
        status_filter = params.get('status', '') if not order_ids else None
        merchant_filter = params.get('merchant_id', '') if not order_ids else None
        customer_filter = params.get('customer_id', '') if not order_ids else None
        date_from = params.get('date_from', '') if not order_ids else None
        date_to = params.get('date_to', '') if not order_ids else None
        
        # 获取要导出的订单
        if order_ids:
            # 批量导出指定订单
            orders = []
            for order_id in order_ids:
                detail_data = await OrderMgmtService.get_order_detail(order_id)
                if detail_data['success']:
                    order = detail_data.get('order') or {}
                    merchant = detail_data.get('merchant') or {}
                    user = detail_data.get('user') or {}
                    order.update({
                        'merchant_name': merchant.get('name', '未设置'),
                        'customer_username': user.get('username', '未设置')
                    })
                    orders.append(order)
        else:
            # 根据筛选条件导出
            orders_data = await OrderMgmtService.get_orders_list(
                status_filter=status_filter if status_filter else None,
                merchant_filter=merchant_filter if merchant_filter else None,
                user_filter=customer_filter if customer_filter else None,
                date_from=date_from if date_from else None,
                date_to=date_to if date_to else None,
                page=1,
                per_page=10000  # 导出限制
            )
            orders = orders_data['orders']
        
        # 创建CSV内容
        import csv
        import io
        from datetime import datetime
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头（对齐旧版）
        writer.writerow([
            '订单ID', '商户ID', '商户名称', '客户ID', '客户用户名', 
            '价格', '状态', '预约时间', '完成时间', '创建时间'
        ])
        
        # 写入数据
        for order in orders:
            writer.writerow([
                order.get('id', ''),
                order.get('merchant_id', ''),
                order.get('merchant_name', ''),
                order.get('customer_user_id', ''),
                order.get('customer_username', ''),
                order.get('price', ''),
                OrderMgmtService.get_status_display(order.get('status', '')),
                order.get('appointment_time', ''),
                order.get('completion_time', ''),
                order.get('created_at', '')
            ])
        
        # 准备响应
        output.seek(0)
        filename = f"orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        from starlette.responses import StreamingResponse
        
        def generate():
            yield output.getvalue().encode('utf-8-sig')  # BOM for Excel
        
        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出订单CSV失败: {e}")
        from starlette.responses import RedirectResponse
        return RedirectResponse(url="/orders?error=导出失败", status_code=302)
