# -*- coding: utf-8 -*-
"""
评价管理路由模块
处理用户评价、商户确认、双向评价系统
"""

import logging
from fasthtml.common import *
from starlette.requests import Request

# 导入布局和认证组件
from ..layout import create_layout, require_auth, okx_form_group, okx_input, okx_button, okx_select
from ..services.review_mgmt_service import ReviewMgmtService

logger = logging.getLogger(__name__)


@require_auth
async def reviews_list(request: Request):
    """评价管理页面"""
    try:
        # 获取筛选参数（与旧版一致）
        status_filter = request.query_params.get('status', '')
        merchant_filter = request.query_params.get('merchant', '')
        confirmed_filter = request.query_params.get('confirmed', '')
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')
        search_query = request.query_params.get('search', '').strip()
        page = int(request.query_params.get('page', '1'))
        per_page = int(request.query_params.get('per_page', '20'))
        
        # 参数归一化（与旧版等价行为）
        status_filter = status_filter if status_filter else None
        merchant_filter = int(merchant_filter) if merchant_filter.isdigit() else None
        confirmed_filter = (
            True if confirmed_filter == 'true' else 
            False if confirmed_filter == 'false' else 
            None
        )
        date_from = date_from if date_from else None
        date_to = date_to if date_to else None
        search_query = search_query if search_query else None
        
        # 调用服务层获取评价数据
        reviews_data = await ReviewMgmtService.get_reviews_list(
            status_filter=status_filter,
            merchant_filter=merchant_filter,
            confirmed_filter=confirmed_filter,
            date_from=date_from,
            date_to=date_to,
            search_query=search_query,
            page=page,
            per_page=per_page
        )
        
        # 容错读取数据（修复字段命名不一致问题）
        reviews = reviews_data.get("reviews", [])
        statistics = reviews_data["statistics"]
        pagination = reviews_data["pagination"]
        filters = reviews_data.get("filters", {})
        merchants = reviews_data.get("merchants", [])
        status_options = reviews_data.get("status_options", {})
        
        # 兼容旧版键名访问
        stats = {
            'total_reviews': statistics.get('total_reviews', 0),
            'confirmed_reviews': statistics.get('confirmed_reviews', 0),
            'pending_reviews': statistics.get('pending_reviews', 0),
            'average_rating': statistics.get('average_rating', 0.0)
        }
        
        total_reviews = pagination.get('total', 0)
        total_pages = pagination.get('pages', 0)
        
        # 创建评价管理页面
        content = Div(
            # 页面头部
            Div(
                H1("评价管理", cls="page-title"),
                P("管理用户评价和商户确认系统", cls="page-subtitle"),
                cls="page-header"
            ),
            
            # 统计卡片（使用项目统一样式）
            Div(
                # 总评价数
                Div(
                    Div(
                        Span("⭐", cls="text-4xl mb-2"),
                        H3("总评价数", cls="font-bold text-white"),
                        P("系统评价", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats["total_reviews"]), cls="text-4xl font-bold text-blue-400"),
                        P("条评价", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 待确认
                Div(
                    Div(
                        Span("⏳", cls="text-4xl mb-2"),
                        H3("待确认", cls="font-bold text-white"),
                        P("待商户确认", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats["pending_reviews"]), cls="text-4xl font-bold text-yellow-400"),
                        P("条待确认", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 已确认
                Div(
                    Div(
                        Span("✅", cls="text-4xl mb-2"),
                        H3("已确认", cls="font-bold text-white"),
                        P("已确认评价", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats["confirmed_reviews"]), cls="text-4xl font-bold text-green-400"),
                        P("条已确认", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 平均评分
                Div(
                    Div(
                        Span("📊", cls="text-4xl mb-2"),
                        H3("平均评分", cls="font-bold text-white"),
                        P("总体评分", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(f"{stats['average_rating']:.1f}", cls="text-4xl font-bold text-purple-400"),
                        P("/10 分", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                cls="stats-container"
            ),
            
            # 筛选表单（完整版）
            Form(
                Div(
                    # 第一行筛选器
                    Div(
                        Div(
                            Label("状态筛选", cls="label"),
                            okx_select("status", [
                                ('', '全部状态'),
                                ('pending_user_review', '待用户评价'),
                                ('pending_merchant_review', '待商户确认'),
                                ('completed', '已完成')
                            ], selected=request.query_params.get('status', ''), cls="select select-bordered w-full"),
                            cls="form-control"
                        ),
                        Div(
                            Label("商户筛选", cls="label"),
                            okx_select("merchant", [('', '全部商户')] + 
                                      [(str(m.get('id', '')), f"#{m.get('id', '')} - {m.get('name', '')[:20]}") for m in merchants], 
                                      selected=request.query_params.get('merchant', ''), cls="select select-bordered w-full"),
                            cls="form-control"
                        ),
                        Div(
                            Label("确认状态", cls="label"),
                            okx_select("confirmed", [
                                ('', '全部'),
                                ('true', '已确认'),
                                ('false', '未确认')
                            ], selected=request.query_params.get('confirmed', ''), cls="select select-bordered w-full"),
                            cls="form-control"
                        ),
                        Div(
                            Label("每页显示", cls="label"),
                            okx_select("per_page", [
                                ('10', '10条'),
                                ('20', '20条'),
                                ('50', '50条'),
                                ('100', '100条')
                            ], selected=str(per_page), cls="select select-bordered w-full"),
                            cls="form-control"
                        ),
                        cls="grid grid-cols-1 md:grid-cols-4 gap-4"
                    ),
                    
                    # 第二行：日期范围和搜索
                    Div(
                        Div(
                            Label("开始日期", cls="label"),
                            okx_input("date_from", type="date", value=request.query_params.get('date_from', ''),
                                     cls="input input-bordered w-full"),
                            cls="form-control"
                        ),
                        Div(
                            Label("结束日期", cls="label"),
                            okx_input("date_to", type="date", value=request.query_params.get('date_to', ''),
                                     cls="input input-bordered w-full"),
                            cls="form-control"
                        ),
                        Div(
                            Label("评价搜索", cls="label"),
                            okx_input("search", placeholder="用户名或商户名", value=search_query or '',
                                     cls="input input-bordered w-full"),
                            cls="form-control"
                        ),
                        # 操作按钮
                        Div(
                            Label("操作", cls="label opacity-0"),
                            Div(
                                okx_button("🔍 筛选", type="submit", cls="btn btn-primary"),
                                A("🔄 重置", href="/reviews", cls="btn btn-outline ml-2"),
                                cls="flex gap-2"
                            ),
                            cls="form-control"
                        ),
                        cls="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4"
                    ),
                    cls="space-y-4"
                ),
                method="GET",
                action="/reviews",
                cls="card bg-base-100 shadow-xl p-6 mb-6"
            ),
            
            # 工具栏（统一为OKX深色主题的中性工具栏样式）
            Div(
                Div(
                    H3("数据管理", cls="text-lg font-semibold"),
                    P("评价数据分析和管理工具", cls="text-sm text-gray-500"),
                ),
                Div(
                    A(
                        "📋 导出数据",
                        href=f"/reviews/export?{request.url.query}" if request.url.query else "/reviews/export",
                        cls="btn btn-outline btn-sm"
                    ),
                    cls="flex gap-3"
                ),
                cls="toolbar-container flex items-center justify-between"
            ),
            
            # 评价列表表格（对齐旧版列）
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("评价ID"),
                            Th("用户"),
                            Th("商户"),
                            Th("评分", cls="text-center"),
                            Th("状态"),
                            Th("确认", cls="text-center"),
                            Th("时间"),
                            Th("操作", cls="w-24")
                        )
                    ),
                    Tbody(
                        *[
                            Tr(
                                # 评价ID
                                Td(
                                    Div(
                                        Strong(f"#{review.get('id', '-')}", cls="font-mono text-sm"),
                                        P(f"订单: {review.get('order_id', '-')}", cls="text-xs text-gray-500"),
                                        cls="space-y-1"
                                    ),
                                    cls="min-w-20"
                                ),
                                
                                # 用户信息
                                Td(
                                    Div(
                                        P(review.get('customer_username', f"用户{review.get('customer_user_id', '-')}"), cls="font-medium text-sm"),
                                        P(f"ID: {review.get('customer_user_id', '-')}", cls="text-xs text-gray-500"),
                                        cls="space-y-1"
                                    )
                                ),
                                
                                # 商户信息
                                Td(
                                    Div(
                                        P(review.get('merchant_name', '未知商户'), cls="font-medium text-sm"),
                                        P(f"ID: {review.get('merchant_id', '-')}", cls="text-xs text-gray-500"),
                                        cls="space-y-1"
                                    )
                                ),
                                
                                # 评分
                                Td(
                                    Div(
                                        Strong(f"{review.get('overall_rating', 0):.1f}", cls="text-lg text-warning"),
                                        P("平均分", cls="text-xs text-gray-500"),
                                        cls="text-center space-y-1"
                                    )
                                ),
                                
                                # 状态
                                Td(
                                    Div(
                                        ReviewMgmtService.get_status_display(review.get('status')),
                                        cls=f"badge badge-{ReviewMgmtService.get_status_color(review.get('status'))}"
                                    )
                                ),
                                
                                # 确认状态
                                Td(
                                    Span(
                                        "✅ 已确认" if review.get('is_confirmed_by_merchant') else "⏳ 待确认",
                                        cls="text-xs " + ("text-success" if review.get('is_confirmed_by_merchant') else "text-warning")
                                    ),
                                    cls="text-center"
                                ),
                                
                                # 评价时间
                                Td(
                                    review.get('created_at', '-')[:16] if review.get('created_at') else '-',
                                    cls="text-sm"
                                ),
                                
                                # 操作
                                Td(
                                    Div(                                        A("查看", href=f"/reviews/{review.get('id')}/detail", cls="btn btn-sm btn-primary mr-1"),
                                        cls="flex gap-1"
                                    )
                                ),
                                
                                cls="hover:bg-gray-50"
                            )
                            for review in reviews
                        ] if reviews else [
                            Tr(
                                Td("暂无评价数据", colspan="8", cls="text-center text-gray-500")
                            )
                        ]
                    ),
                    cls="table table-zebra w-full"
                ),
                cls="overflow-x-auto card bg-base-100 shadow-xl p-6"
            ),
            
            # 分页组件与显示区间
            Div(
                # 分页按钮
                _generate_pagination(page, total_pages, request.query_params) if total_pages > 1 else Div(),
                # 显示区间文案
                P(f"显示第 {(page-1)*per_page+1}-{min(page*per_page, total_reviews)} 条，共 {total_reviews} 条评价",
                  cls="text-sm text-gray-500"),
                cls="flex justify-between items-center mt-6"
            ),
            
            cls="page-content"
        )
        
        return create_layout("评价管理", content)
        
    except Exception as e:
        logger.error(f"评价管理页面错误: {e}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        error_content = Div(
            H1("评价管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            Pre(f"{str(e)}\n\n{traceback.format_exc()}", cls="bg-gray-100 p-4 rounded text-sm")
        )
        return create_layout("系统错误", error_content)

@require_auth
async def review_detail(request: Request):
    """评价详情页面"""
    review_id = int(request.path_params['id'])
    
    try:
        # 调用服务层获取评价详情
        result = await ReviewMgmtService.get_review_detail(review_id)
        if not result.get('success', False):
            error_content = Div(
                H1("评价不存在", cls="text-2xl font-bold text-red-600 mb-4"),
                P("请检查评价ID是否正确"),
                A("返回评价列表", href="/reviews", cls="btn btn-outline mt-4")
            )
            return create_layout("评价不存在", error_content)
        
        # 提取数据
        review = result.get('review', {})
        order = result.get('order', {})
        merchant = result.get('merchant', {})
        user = result.get('user', {})
            
    except Exception as e:
        logger.error(f"获取评价详情失败: {e}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        error_content = Div(
            H1("评价详情错误", cls="text-2xl font-bold text-red-600 mb-4"),
            Pre(f"{str(e)}\n\n{traceback.format_exc()}", cls="bg-gray-100 p-4 rounded text-sm")
        )
        return create_layout("系统错误", error_content)

    # 评价基本信息卡片
    review_info_card = Div(
        H3("📋 评价信息", cls="text-lg font-semibold mb-4"),
        Div(
            Div(f"评价ID: #{review.get('id', '-')}", cls="font-mono text-lg mb-2"),
            Div(f"订单ID: #{review.get('order_id', '-')}", cls="font-mono mb-2"),
            Div(
                Span(f"状态: ", cls="mr-2"),
                Span(
                    ReviewMgmtService.get_status_display(review.get('status')),
                    cls=f"badge badge-{ReviewMgmtService.get_status_color(review.get('status'))}"
                ),
                cls="mb-2"
            ),
            Div(
                f"确认状态: {'✅ 已确认' if review.get('is_confirmed_by_merchant') else '⏳ 待确认'}", 
                cls=f"{'text-success' if review.get('is_confirmed_by_merchant') else 'text-warning'} mb-2"
            ),
            Div(f"评价时间: {review.get('created_at', '-')}", cls="text-sm text-gray-500"),
            cls="space-y-3"
        ),
        cls="card bg-base-100 shadow-xl p-6"
    )
    
    # 五维评分卡片
    rating_items = [
        ('颜值评分', review.get('rating_appearance', 0), '💄'),
        ('身材评分', review.get('rating_figure', 0), '👗'),
        ('服务评分', review.get('rating_service', 0), '🛏️'),
        ('态度评分', review.get('rating_attitude', 0), '😊'),
        ('环境评分', review.get('rating_environment', 0), '🏠')
    ]
    
    rating_cards = []
    for name, score, icon in rating_items:
        card = Div(
            Div(
                Span(icon, cls="text-2xl"),
                P(name, cls="text-sm font-medium"),
                Strong(f"{score}/10", cls="text-lg text-primary"),
                cls="text-center space-y-1"
            ),
            cls="bg-gray-50 p-4 rounded-lg"
        )
        rating_cards.append(card)
    
    ratings_card = Div(
        H3("⭐ 五维评分", cls="text-lg font-semibold mb-4"),
        Div(*rating_cards, cls="grid grid-cols-1 md:grid-cols-5 gap-4"),
        cls="card bg-base-100 shadow-xl p-6"
    )
    
    # 文字评价卡片
    text_review_card = Div(
        H3("📝 文字评价", cls="text-lg font-semibold mb-4"),
        Div(
            P(review.get('text_review_by_user', '暂无文字评价'), 
              cls="text-gray-700 leading-relaxed" if review.get('text_review_by_user') else "text-gray-500 italic"),
            cls="bg-gray-50 p-4 rounded-lg"
        ),
        cls="card bg-base-100 shadow-xl p-6"
    )
    
    # 用户信息卡片
    user_info_card = Div(
        H3("👤 评价用户", cls="text-lg font-semibold mb-4"),
        Div(
            P(f"用户ID: {review.get('customer_user_id', '-')}", cls="font-mono mb-2"),
            P(f"用户名: {user.get('username', '未设置')}", cls="mb-2"),
            A("查看用户详情", href=f"/users/{review.get('customer_user_id')}/detail", 
              cls="btn btn-outline btn-sm"),
            cls="space-y-2"
        ),
        cls="card bg-base-100 shadow-xl p-6"
    )
    
    # 商户信息卡片
    merchant_info_card = Div(
        H3("🏪 被评价商户", cls="text-lg font-semibold mb-4"),
        Div(
            P(f"商户: {merchant.get('name', '未知商户')}", cls="font-medium mb-2"),
            P(f"商户ID: {review.get('merchant_id', '-')}", cls="font-mono text-sm mb-2"),
            A("查看商户详情", href=f"/posts/{review.get('merchant_id')}", 
              cls="btn btn-outline btn-sm"),
            cls="space-y-2"
        ),
        cls="card bg-base-100 shadow-xl p-6"
    )
    
    content = Div(
        # 页面头部
        Div(
            H1(f"评价详情 - #{review.get('id', '-')}", cls="page-title"),
            A("← 返回评价列表", href="/reviews", cls="btn btn-outline"),
            cls="flex justify-between items-center mb-8"
        ),
        
        # 主要内容区域
        Div(
            # 左侧
            Div(
                review_info_card,
                ratings_card,
                text_review_card,
                cls="space-y-6"
            ),
            
            # 右侧
            Div(
                user_info_card,
                merchant_info_card,
                cls="space-y-6"
            ),
            
            cls="grid grid-cols-1 lg:grid-cols-2 gap-6"
        ),
        
        cls="page-content"
    )
    
    return create_layout("评价详情", content)


@require_auth  
async def export_reviews(request: Request):
    """导出评价数据为CSV"""
    try:
        # 获取筛选参数（与列表页保持一致）
        status_filter = request.query_params.get('status', '')
        merchant_filter = request.query_params.get('merchant', '')
        confirmed_filter = request.query_params.get('confirmed', '')
        date_from = request.query_params.get('date_from', '')
        date_to = request.query_params.get('date_to', '')
        search_query = request.query_params.get('search', '')
        
        # 调用服务层获取评价数据
        reviews_data = await ReviewMgmtService.get_reviews_list(
            status_filter=status_filter if status_filter else None,
            merchant_filter=merchant_filter if merchant_filter else None,
            confirmed_filter=confirmed_filter if confirmed_filter else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            search_query=search_query if search_query else None,
            page=1,
            per_page=10000  # 导出限制
        )
        
        reviews = reviews_data.get("reviews", [])
        
        # 创建CSV
        import io
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            '评价ID', '订单ID', '用户ID', '用户名', '商户ID', '商户名', 
            '颜值评分', '身材评分', '服务评分', '态度评分', '环境评分', 
            '文字评价', '状态', '商户确认', '评价时间'
        ])
        
        # 写入数据
        for review in reviews:
            writer.writerow([
                review.get('id', ''),
                review.get('order_id', ''),
                review.get('customer_user_id', ''),
                review.get('customer_username', ''),
                review.get('merchant_id', ''),
                review.get('merchant_name', ''),
                review.get('rating_appearance', ''),
                review.get('rating_figure', ''),
                review.get('rating_service', ''),
                review.get('rating_attitude', ''),
                review.get('rating_environment', ''),
                review.get('text_review_by_user', ''),
                review.get('status', ''),
                '是' if review.get('is_confirmed_by_merchant') else '否',
                review.get('created_at', '')
            ])
        
        # 准备响应
        from datetime import datetime
        output.seek(0)
        filename = f"reviews_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        from starlette.responses import StreamingResponse
        
        def generate():
            yield output.getvalue().encode('utf-8-sig')  # BOM for Excel
        
        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出评价数据失败: {e}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        error_content = Div(
            H1("导出失败", cls="text-2xl font-bold text-red-600 mb-4"),
            P("无法导出评价数据，请稍后重试"),
            A("返回评价列表", href="/reviews", cls="btn btn-outline mt-4")
        )
        return create_layout("导出失败", error_content)


def _generate_pagination(current_page: int, total_pages: int, query_params) -> Any:
    """生成分页导航"""
    if total_pages <= 1:
        return Div()
    
    # 构建查询字符串
    query_dict = dict(query_params)
    if 'page' in query_dict:
        del query_dict['page']
    query_string = "&".join([f"{k}={v}" for k, v in query_dict.items() if v])
    query_prefix = f"?{query_string}&" if query_string else "?"
    
    pages = []
    
    # 上一页
    if current_page > 1:
        pages.append(A("‹ 上一页", href=f"/reviews{query_prefix}page={current_page-1}",
                      cls="btn btn-outline btn-sm"))
    
    # 页码
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)
    
    for page_num in range(start_page, end_page + 1):
        if page_num == current_page:
            pages.append(Span(str(page_num), cls="btn btn-primary btn-sm"))
        else:
            pages.append(A(str(page_num), href=f"/reviews{query_prefix}page={page_num}",
                          cls="btn btn-outline btn-sm"))
    
    # 下一页
    if current_page < total_pages:
        pages.append(A("下一页 ›", href=f"/reviews{query_prefix}page={current_page+1}",
                      cls="btn btn-outline btn-sm"))
    
    return Div(*pages, cls="join")
