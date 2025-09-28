# -*- coding: utf-8 -*-
"""
评价系统管理路由 V2.0
包含用户评价记录管理、商户评分统计、双向评价系统管理
"""

import logging
from typing import Any, Dict, List, Optional
from starlette.routing import Route
from starlette.responses import RedirectResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException
from starlette.requests import Request
from datetime import datetime, timedelta
import csv
import io
import json

from database.db_reviews import review_manager
from database.db_merchants import merchant_manager
from database.db_users import user_manager
from web.layout import create_layout, require_auth, okx_form_group, okx_input, okx_button, okx_textarea, okx_select
from fasthtml.common import *

logger = logging.getLogger(__name__)

# 评价状态映射




@require_auth
async def reviews_dashboard(request: Request) -> Response:
    """评价管理仪表板"""
    
    # 获取筛选参数
    status_filter = request.query_params.get("status", "")
    merchant_filter = request.query_params.get("merchant", "")
    confirmed_filter = request.query_params.get("confirmed", "")
    date_from = request.query_params.get("date_from", "")
    date_to = request.query_params.get("date_to", "")
    page = int(request.query_params.get("page", "1"))
    per_page = int(request.query_params.get("per_page", "20"))
    
    try:
        # 构建查询参数
        query_params = {
            'status': status_filter if status_filter else None,
            'merchant_id': int(merchant_filter) if merchant_filter.isdigit() else None,
            'is_confirmed': confirmed_filter == 'true' if confirmed_filter else None,
            'date_from': date_from if date_from else None,
            'date_to': date_to if date_to else None,
            'limit': per_page,
            'offset': (page - 1) * per_page
        }
        
        # 获取评价数据
        reviews = await review_manager.get_reviews_with_details(**query_params)
        
        # 获取总数用于分页
        total_reviews = await review_manager.count_reviews(
            status=query_params['status'],
            merchant_id=query_params['merchant_id'],
            is_confirmed=query_params['is_confirmed'],
            date_from=query_params['date_from'],
            date_to=query_params['date_to']
        )
        
        # 获取统计数据
        stats = await _get_review_statistics()
        
        # 获取商户列表用于筛选
        merchants = await merchant_manager.get_merchants(limit=100)
        
    except Exception as e:
        logger.error(f"获取评价数据失败: {e}")
        raise HTTPException(status_code=500, detail="无法获取评价数据")
    
    # 统计卡片
    stats_cards = Div(
        # 总评价数
        Div(
            Div(
                Span("⭐", cls="text-3xl"),
                Div(
                    P("总评价数", cls="text-sm text-gray-500"),
                    P(str(stats['total_reviews']), cls="text-2xl font-bold text-primary")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 有效评价
        Div(
            Div(
                Span("✅", cls="text-3xl"),
                Div(
                    P("有效评价", cls="text-sm text-gray-500"),
                    P(str(stats['confirmed_reviews']), cls="text-2xl font-bold text-success")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 平均评分
        Div(
            Div(
                Span("📊", cls="text-3xl"),
                Div(
                    P("平均评分", cls="text-sm text-gray-500"),
                    P(f"{stats['avg_rating']:.1f}", cls="text-2xl font-bold text-warning")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 本周新增
        Div(
            Div(
                Span("🔥", cls="text-3xl"),
                Div(
                    P("本周新增", cls="text-sm text-gray-500"),
                    P(str(stats['week_reviews']), cls="text-2xl font-bold text-info")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        cls="stats-container"
    )
    
    # 高级搜索和筛选表单
    filter_form = Form(
        Div(
            # 第一行筛选器
            Div(
                Div(
                    Label("评价状态", cls="label-text text-sm font-medium"),
                    okx_select("status", [
                        ('', '所有状态'),
                    ], selected=status_filter, cls="select select-bordered w-full"),
                    cls="form-control"
                ),
                
                Div(
                    Label("商户筛选", cls="label-text text-sm font-medium"),
                    okx_select("merchant", [('', '所有商户')] + 
                              [(str(m['id']), m['name']) for m in merchants], 
                              selected=merchant_filter, cls="select select-bordered w-full"),
                    cls="form-control"
                ),
                
                Div(
                    Label("确认状态", cls="label-text text-sm font-medium"),
                    okx_select("confirmed", [
                        ('', '全部'),
                        ('true', '已确认'),
                        ('false', '未确认')
                    ], selected=confirmed_filter, cls="select select-bordered w-full"),
                    cls="form-control"
                ),
                
                Div(
                    Label("每页显示", cls="label-text text-sm font-medium"),
                    okx_select("per_page", [
                        ('10', '10条'),
                        ('20', '20条'),
                        ('50', '50条'),
                        ('100', '100条')
                    ], selected=str(per_page), cls="select select-bordered w-full"),
                    cls="form-control"
                ),
                
                cls="content-grid grid-4"
            ),
            
            # 第二行：日期范围
            Div(
                Div(
                    Label("开始日期", cls="label-text text-sm font-medium"),
                    okx_input("date_from", type="date", value=date_from, 
                             cls="input input-bordered w-full"),
                    cls="form-control"
                ),
                
                Div(
                    Label("结束日期", cls="label-text text-sm font-medium"),
                    okx_input("date_to", type="date", value=date_to,
                             cls="input input-bordered w-full"),
                    cls="form-control"
                ),
                
                # 操作按钮
                Div(
                    Label("操作", cls="label-text text-sm font-medium opacity-0"),
                    Div(
                        okx_button("🔍 筛选", type="submit", cls="btn btn-primary"),
                        A("🔄 重置", href="/reviews", cls="btn btn-outline"),
                        cls="flex gap-2"
                    ),
                    cls="form-control"
                ),
                
                cls="content-grid grid-3"
            ),
            
            cls="filter-container"
        ),
        method="get",
        action="/reviews"
    )
    
    # 快速操作工具栏（统一深色主题样式）
    toolbar = Div(
        Div(
            H3("数据管理", cls="text-lg font-semibold"),
            P("评价数据分析和管理工具", cls="text-sm text-gray-500"),
        ),
        Div(
            A("📊 数据分析", href="/reviews/analytics", cls="btn btn-info btn-sm"),
            A(
                "📋 导出数据",
                href="/reviews/export" + (f"?{request.url.query}" if request.url.query else ""),
                cls="btn btn-outline btn-sm"
            ),
            A("🏆 商户评分榜", href="/reviews/merchant-ranking", cls="btn btn-secondary btn-sm"),
            cls="flex gap-3"
        ),
        cls="toolbar-container flex items-center justify-between"
    )
    
    # 评价列表表格
    table_rows = []
    for review in reviews:
        
        # 计算平均评分
        ratings = [
            review.get('rating_appearance', 0),
            review.get('rating_figure', 0), 
            review.get('rating_service', 0),
            review.get('rating_attitude', 0),
            review.get('rating_environment', 0)
        ]
        avg_rating = sum(r for r in ratings if r > 0) / len([r for r in ratings if r > 0]) if any(r > 0 for r in ratings) else 0
        
        row = Tr(
            # 评价ID
            Td(
                Div(
                    Strong(f"#{review['id']}", cls="font-mono text-sm"),
                    P(f"订单: {review['order_id']}", cls="text-xs text-gray-500"),
                    cls="space-y-1"
                ),
                cls="min-w-20"
            ),
            
            # 用户信息
            Td(
                Div(
                    P(review.get('customer_username', f"用户{review['customer_user_id']}"), cls="font-medium text-sm"),
                    P(f"ID: {review['customer_user_id']}", cls="text-xs text-gray-500"),
                    cls="space-y-1"
                )
            ),
            
            # 商户信息
            Td(
                Div(
                    P(review.get('merchant_name', '未知商户'), cls="font-medium text-sm"),
                    P(f"ID: {review['merchant_id']}", cls="text-xs text-gray-500"),
                    cls="space-y-1"
                )
            ),
            
            # 平均评分
            Td(
                Div(
                    Strong(f"{avg_rating:.1f}", cls="text-lg text-warning"),
                    P("平均分", cls="text-xs text-gray-500"),
                    cls="text-center space-y-1"
                )
            ),
            
            # 状态
            Td(
                Span(
                    f"{status_icon} {review['status']}", 
                    cls=f"badge badge-{status_color} text-xs"
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
                review['created_at'][:16] if review.get('created_at') else '-',
                cls="text-sm"
            ),
            
            # 操作
            Td(
                Div(
                    A("👁️", href=f"/reviews/{review['id']}/detail", 
                      cls="btn btn-ghost btn-xs", title="查看详情"),
                    A("✏️", href=f"/reviews/{review['id']}/manage", 
                      cls="btn btn-ghost btn-xs", title="管理评价"),
                    cls="flex gap-1"
                )
            ),
            
            cls="hover:bg-gray-50"
        )
        table_rows.append(row)
    
    # 分页信息
    total_pages = (total_reviews + per_page - 1) // per_page
    pagination = _generate_pagination(page, total_pages, request.query_params)
    
    # 主表格
    reviews_table = Div(
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
            Tbody(*table_rows),
            cls="table table-zebra w-full"
        ),
        cls="data-table-container"
    )
    
    content = Div(
        Div(
            H1("评价系统管理", cls="page-title"),
            A("查看分析", href="/reviews/analytics", cls="btn btn-outline btn-sm"),
            cls="flex justify-between items-center mb-8"
        ),
        
        stats_cards,
        filter_form,
        toolbar,
        reviews_table,
        
        # 分页
        Div(
            pagination,
            P(f"显示第 {(page-1)*per_page+1}-{min(page*per_page, total_reviews)} 条，共 {total_reviews} 条评价",
              cls="text-sm text-gray-500"),
            cls="flex justify-between items-center mt-6"
        )
    )
    
    return create_layout("评价管理", content)

@require_auth
async def review_detail_v2(request: Request) -> Response:
    """评价详情页面"""
    review_id = int(request.path_params['id'])
    
    try:
        review = await review_manager.get_review_detail(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="评价不存在")
            
    except Exception as e:
        logger.error(f"获取评价详情失败: {e}")
        raise HTTPException(status_code=500, detail="无法获取评价详情")

    # 评价基本信息卡片
    review_info_card = Div(
        H3("📋 评价信息", cls="content-section-title"),
        Div(
            Div(f"评价ID: #{review['id']}", cls="font-mono text-lg"),
            Div(f"订单ID: #{review['order_id']}", cls="font-mono"),
            Div(f"确认状态: {'✅ 已确认' if review.get('is_confirmed_by_merchant') else '⏳ 待确认'}", 
                cls=f"{'text-success' if review.get('is_confirmed_by_merchant') else 'text-warning'}"),
            Div(f"评价时间: {review['created_at']}", cls="text-sm text-gray-500"),
            cls="space-y-3"
        ),
        cls="content-section"
    )
    
    # 五维评分卡片
    rating_items = [
        ('颜值评分', review.get('rating_appearance', 0), '💄'),
        ('身材评分', review.get('rating_figure', 0), '👗'),
        ('服务评分', review.get('rating_service', 0), '🛎️'),
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
        H3("⭐ 五维评分", cls="content-section-title"),
        Div(*rating_cards, cls="content-grid grid-5"),
        cls="content-section"
    )
    
    # 文字评价卡片
    text_review_card = Div(
        H3("📝 文字评价", cls="content-section-title"),
        Div(
            P(review.get('text_review_by_user', '暂无文字评价'), 
              cls="text-gray-700 leading-relaxed" if review.get('text_review_by_user') else "text-gray-500 italic"),
            cls="bg-gray-50 p-4 rounded-lg"
        ),
        cls="content-section"
    )
    
    # 用户信息卡片
    user_info_card = Div(
        H3("👤 评价用户", cls="content-section-title"),
        Div(
            P(f"用户ID: {review['customer_user_id']}", cls="font-mono"),
            P(f"用户名: {review.get('customer_username', '未设置')}", cls=""),
            A("查看用户详情", href=f"/users/{review['customer_user_id']}/detail", 
              cls="btn btn-outline btn-sm mt-2"),
            cls="space-y-2"
        ),
        cls="content-section"
    )
    
    # 商户信息卡片
    merchant_info_card = Div(
        H3("🏪 被评价商户", cls="content-section-title"),
        Div(
            P(f"商户: {review.get('merchant_name', '未知商户')}", cls="font-medium"),
            P(f"商户ID: {review['merchant_id']}", cls="font-mono text-sm"),
            A("查看商户详情", href=f"/posts/{review['merchant_id']}", 
              cls="btn btn-outline btn-sm mt-2"),
            cls="space-y-2"
        ),
        cls="content-section"
    )
    
    content = Div(
        H1(f"评价详情 - #{review['id']}", cls="page-title"),
        
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
            
            cls="content-grid grid-2"
        ),
        
        # 返回按钮
        Div(
            A("← 返回评价列表", href="/reviews", cls="btn btn-outline"),
            cls="mt-8"
        )
    )
    
    return create_layout("评价详情", content)

async def _get_review_statistics() -> Dict[str, Any]:
    """获取评价统计数据"""
    try:
        # 总评价数
        total_reviews = await review_manager.count_reviews()
        
        # 已确认评价数
        confirmed_reviews = await review_manager.count_reviews(is_confirmed=True)
        
        # 平均评分
        avg_rating = await review_manager.get_average_rating()
        
        # 本周新增评价
        week_start = datetime.now().date() - timedelta(days=7)
        week_reviews = await review_manager.count_reviews(
            date_from=week_start.isoformat()
        )
        
        return {
            'total_reviews': total_reviews,
            'confirmed_reviews': confirmed_reviews,
            'avg_rating': avg_rating or 0,
            'week_reviews': week_reviews
        }
        
    except Exception as e:
        logger.error(f"获取评价统计数据失败: {e}")
        return {
            'total_reviews': 0,
            'confirmed_reviews': 0,
            'avg_rating': 0,
            'week_reviews': 0
        }

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
