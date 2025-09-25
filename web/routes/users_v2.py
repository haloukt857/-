# -*- coding: utf-8 -*-
"""
DEPRECATED: 本文件为早期基于Starlette Route的用户管理实现，
当前用户管理与用户分析页面已迁移为 FastHTML 原生路由并集成在 `web/app.py`。
此文件不再挂载，仅保留作参考，后续可删除。
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

from database.db_users import user_manager
from database.db_incentives import incentive_manager
from web.layout import create_layout, require_auth, okx_form_group, okx_input, okx_button, okx_textarea, okx_select
from fasthtml.common import *

logger = logging.getLogger(__name__)

@require_auth
async def users_dashboard(request: Request) -> Response:
    """用户管理仪表板"""
    
    # 获取筛选参数
    level_filter = request.query_params.get("level", "")
    search_query = request.query_params.get("search", "")
    page = int(request.query_params.get("page", "1"))
    per_page = int(request.query_params.get("per_page", "20"))
    
    try:
        # 获取用户数据
        users = await user_manager.get_users_with_pagination(
            level_name=level_filter if level_filter else None,
            search=search_query if search_query else None,
            limit=per_page,
            offset=(page - 1) * per_page
        )
        
        # 获取总用户数
        total_users = await user_manager.count_users(
            level_name=level_filter if level_filter else None,
            search=search_query if search_query else None
        )
        
        # 获取统计数据
        stats = await _get_user_statistics()
        
        # 获取等级列表用于筛选
        levels = await incentive_manager.get_all_levels()
        
    except Exception as e:
        logger.error(f"获取用户数据失败: {e}")
        raise HTTPException(status_code=500, detail="无法获取用户数据")
    
    # 统计卡片
    stats_cards = Div(
        # 总用户数
        Div(
            Div(
                Span("👥", cls="text-3xl"),
                Div(
                    P("总用户数", cls="text-sm text-gray-500"),
                    P(str(stats['total_users']), cls="text-2xl font-bold text-primary")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 本周活跃用户
        Div(
            Div(
                Span("🔥", cls="text-3xl"),
                Div(
                    P("本周活跃", cls="text-sm text-gray-500"),
                    P(str(stats['week_active_users']), cls="text-2xl font-bold text-success")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 平均积分
        Div(
            Div(
                Span("⭐", cls="text-3xl"),
                Div(
                    P("平均积分", cls="text-sm text-gray-500"),
                    P(f"{stats['avg_points']:.0f}", cls="text-2xl font-bold text-warning")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 高等级用户
        Div(
            Div(
                Span("👑", cls="text-3xl"),
                Div(
                    P("高等级用户", cls="text-sm text-gray-500"),
                    P(str(stats['high_level_users']), cls="text-2xl font-bold text-info")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        cls="stats-container"
    )
    
    # 搜索和筛选表单
    filter_form = Form(
        Div(
            Div(
                Div(
                    Label("等级筛选", cls="label-text text-sm font-medium"),
                    okx_select("level", [('', '所有等级')] + 
                              [(level['level_name'], level['level_name']) for level in levels], 
                              selected=level_filter, cls="select select-bordered w-full"),
                    cls="form-control"
                ),
                
                Div(
                    Label("用户搜索", cls="label-text text-sm font-medium"),
                    okx_input("search", placeholder="用户名或用户ID", value=search_query,
                             cls="input input-bordered w-full"),
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
                
                Div(
                    Label("操作", cls="label-text text-sm font-medium opacity-0"),
                    Div(
                        okx_button("🔍 搜索", type="submit", cls="btn btn-primary"),
                        A("🔄 重置", href="/users", cls="btn btn-outline"),
                        cls="flex gap-2"
                    ),
                    cls="form-control"
                ),
                
                cls="grid grid-cols-1 md:grid-cols-4 gap-4"
            ),
            cls="bg-gray-50 p-6 rounded-lg"
        ),
        method="get",
        action="/users"
    )
    
    # 快速操作工具栏
    toolbar = Div(
        Div(
            H3("快速操作", cls="text-lg font-semibold"),
            P("用户管理和数据分析", cls="text-sm text-gray-500"),
            cls="mb-4"
        ),
        Div(
            A("📊 数据统计", href="/users/analytics", cls="btn btn-info btn-sm"),
            A("📋 导出数据", href="/users/export" + (f"?{request.url.query}" if request.url.query else ""), 
              cls="btn btn-outline btn-sm"),
            A("⚙️ 等级配置", href="/incentives", cls="btn btn-secondary btn-sm"),
            cls="flex gap-3"
        ),
        cls="bg-blue-50 border border-blue-200 p-4 rounded-lg mb-6"
    )
    
    # 用户列表表格
    table_rows = []
    for user in users:
        badges_count = len(json.loads(user.get('badges', '[]')))
        
        row = Tr(
            # 用户信息
            Td(
                Div(
                    Strong(user.get('username', f"用户{user['user_id']}"), cls="font-medium text-sm"),
                    P(f"ID: {user['user_id']}", cls="text-xs text-gray-500 font-mono"),
                    cls="space-y-1"
                )
            ),
            
            # 等级
            Td(
                Span(
                    user.get('level_name', '新手'), 
                    cls="badge badge-primary text-xs"
                )
            ),
            
            # 经验值
            Td(
                Strong(str(user.get('xp', 0)), cls="text-primary"),
                cls="text-center"
            ),
            
            # 积分
            Td(
                Strong(str(user.get('points', 0)), cls="text-warning"),
                cls="text-center"
            ),
            
            # 订单数
            Td(
                Strong(str(user.get('order_count', 0)), cls="text-success"),
                cls="text-center"
            ),
            
            # 勋章数
            Td(
                Span(f"🏆 {badges_count}", cls="text-sm text-info"),
                cls="text-center"
            ),
            
            # 操作
            Td(
                Div(
                    A("👁️", href=f"/users/{user['user_id']}/detail", 
                      cls="btn btn-ghost btn-xs", title="查看详情"),
                    A("✏️", href=f"/users/{user['user_id']}/edit", 
                      cls="btn btn-ghost btn-xs", title="编辑用户"),
                    cls="flex gap-1"
                )
            ),
            
            cls="hover:bg-gray-50"
        )
        table_rows.append(row)
    
    # 分页
    total_pages = (total_users + per_page - 1) // per_page
    pagination = _generate_pagination(page, total_pages, request.query_params)
    
    # 主表格
    users_table = Div(
        Table(
            Thead(
                Tr(
                    Th("用户"),
                    Th("等级"),
                    Th("经验值", cls="text-center"),
                    Th("积分", cls="text-center"),
                    Th("订单数", cls="text-center"),
                    Th("勋章", cls="text-center"),
                    Th("操作", cls="w-24")
                )
            ),
            Tbody(*table_rows),
            cls="table table-zebra w-full"
        ),
        cls="overflow-x-auto bg-white rounded-lg shadow"
    )
    
    content = Div(
        Div(
            H1("用户管理仪表板", cls="page-title"),
            A("查看分析", href="/users/analytics", cls="btn btn-outline btn-sm"),
            cls="flex justify-between items-center mb-8"
        ),
        
        stats_cards,
        filter_form,
        toolbar,
        users_table,
        
        # 分页信息
        Div(
            pagination,
            P(f"显示第 {(page-1)*per_page+1}-{min(page*per_page, total_users)} 条，共 {total_users} 个用户",
              cls="text-sm text-gray-500"),
            cls="flex justify-between items-center mt-6"
        )
    )
    
    return create_layout("用户管理", content)

@require_auth
async def user_detail_v2(request: Request) -> Response:
    """用户详情页面"""
    user_id = int(request.path_params['id'])
    
    try:
        # 获取用户信息
        user_info = await user_manager.get_user_with_details(user_id)
        if not user_info:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 获取用户的评价记录
        user_reviews = await user_manager.get_user_reviews(user_id, limit=10)
        
        # 获取用户的勋章详情
        user_badges = await user_manager.get_user_badges_detail(user_id)
        
    except Exception as e:
        logger.error(f"获取用户详情失败: {e}")
        raise HTTPException(status_code=500, detail="无法获取用户详情")
    
    # 用户基本信息卡片
    user_info_card = Div(
        H3("👤 基本信息", cls="content-section-title"),
        Div(
            Div(f"用户ID: {user_info['user_id']}", cls="font-mono text-lg"),
            Div(f"用户名: {user_info.get('username', '未设置')}", cls=""),
            Div(f"当前等级: {user_info.get('level_name', '新手')}", cls="badge badge-primary badge-lg"),
            Div(f"经验值: {user_info.get('xp', 0)} XP", cls="text-primary font-bold"),
            Div(f"积分: {user_info.get('points', 0)} 分", cls="text-warning font-bold"),
            Div(f"完成订单: {user_info.get('order_count', 0)} 次", cls="text-success font-bold"),
            cls="space-y-3"
        ),
        cls="bg-white p-6 rounded-lg shadow"
    )
    
    # 勋章展示卡片
    badge_items = []
    for badge in user_badges:
        badge_item = Div(
            Div(
                Span(badge.get('badge_icon', '🏆'), cls="text-2xl"),
                P(badge['badge_name'], cls="font-medium text-sm"),
                P(badge.get('description', ''), cls="text-xs text-gray-500"),
                cls="text-center space-y-1"
            ),
            cls="bg-gray-50 p-3 rounded-lg"
        )
        badge_items.append(badge_item)
    
    badges_card = Div(
        H3("🏆 获得勋章", cls="content-section-title"),
        Div(
            *badge_items if badge_items else [P("暂无勋章", cls="text-gray-500 text-center py-8")],
            cls="grid grid-cols-2 md:grid-cols-3 gap-3"
        ),
        cls="bg-white p-6 rounded-lg shadow"
    )
    
    # 评价记录卡片
    review_rows = []
    for review in user_reviews:
        review_row = Tr(
            Td(f"#{review['order_id']}", cls="font-mono text-sm"),
            Td(review.get('merchant_name', '未知商户')),
            Td(f"{review.get('rating_service', 0)}/10", cls="text-center"),
            Td("有效" if review.get('is_confirmed_by_merchant') else "待确认", 
               cls="text-center"),
            Td(review['created_at'][:10], cls="text-sm")
        )
        review_rows.append(review_row)
    
    reviews_card = Div(
        H3("⭐ 评价记录", cls="content-section-title"),
        Div(
            Table(
                Thead(
                    Tr(Th("订单"), Th("商户"), Th("评分"), Th("状态"), Th("时间"))
                ),
                Tbody(*review_rows),
                cls="table table-sm w-full"
            ) if review_rows else P("暂无评价记录", cls="text-gray-500 text-center py-8"),
            cls="overflow-x-auto"
        ),
        cls="bg-white p-6 rounded-lg shadow"
    )
    
    content = Div(
        H1(f"用户详情 - {user_info.get('username', f'用户{user_id}')}", cls="page-title"),
        
        Div(
            # 左侧
            Div(
                user_info_card,
                reviews_card,
                cls="space-y-6"
            ),
            
            # 右侧
            Div(
                badges_card,
                cls="space-y-6"
            ),
            
            cls="grid grid-cols-1 lg:grid-cols-2 gap-8"
        ),
        
        # 返回按钮
        Div(
            A("← 返回用户列表", href="/users", cls="btn btn-outline"),
            cls="mt-8"
        )
    )
    
    return create_layout("用户详情", content)

async def _get_user_statistics() -> Dict[str, Any]:
    """获取用户统计数据"""
    try:
        # 总用户数
        total_users = await user_manager.count_users()
        
        # 本周活跃用户数
        week_start = datetime.now().date() - timedelta(days=7)
        week_active_users = await user_manager.count_active_users_since(week_start.isoformat())
        
        # 平均积分
        avg_points = await user_manager.get_average_points()
        
        # 高等级用户数（假设经验值>1000为高等级）
        high_level_users = await user_manager.count_users_by_xp_threshold(1000)
        
        return {
            'total_users': total_users,
            'week_active_users': week_active_users,
            'avg_points': avg_points or 0,
            'high_level_users': high_level_users
        }
        
    except Exception as e:
        logger.error(f"获取用户统计数据失败: {e}")
        return {
            'total_users': 0,
            'week_active_users': 0,
            'avg_points': 0,
            'high_level_users': 0
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
        pages.append(A("‹ 上一页", href=f"/users{query_prefix}page={current_page-1}",
                      cls="btn btn-outline btn-sm"))
    
    # 页码
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)
    
    for page_num in range(start_page, end_page + 1):
        if page_num == current_page:
            pages.append(Span(str(page_num), cls="btn btn-primary btn-sm"))
        else:
            pages.append(A(str(page_num), href=f"/users{query_prefix}page={page_num}",
                          cls="btn btn-outline btn-sm"))
    
    # 下一页
    if current_page < total_pages:
        pages.append(A("下一页 ›", href=f"/users{query_prefix}page={current_page+1}",
                      cls="btn btn-outline btn-sm"))
    
    return Div(*pages, cls="join")

@require_auth
async def export_users(request: Request) -> Response:
    """导出用户数据为CSV"""
    try:
        # 获取筛选参数
        level_filter = request.query_params.get("level")
        search_query = request.query_params.get("search")
        
        users = await user_manager.get_users_with_pagination(
            level_name=level_filter if level_filter else None,
            search=search_query if search_query else None,
            limit=10000  # 导出限制
        )
        
        # 创建CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            '用户ID', '用户名', '等级', '经验值', '积分', '订单数', '勋章数', '注册时间'
        ])
        
        # 写入数据
        for user in users:
            badges_count = len(json.loads(user.get('badges', '[]')))
            writer.writerow([
                user['user_id'],
                user.get('username', ''),
                user.get('level_name', '新手'),
                user.get('xp', 0),
                user.get('points', 0),
                user.get('order_count', 0),
                badges_count,
                user.get('created_at', '')
            ])
        
        # 准备响应
        output.seek(0)
        filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        def generate():
            yield output.getvalue().encode('utf-8-sig')  # BOM for Excel
        
        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出用户数据失败: {e}")
        raise HTTPException(status_code=500, detail="导出失败")

# 导出路由列表
users_v2_routes = [
    Route("/", users_dashboard, methods=["GET"]),
    Route("/{id}/detail", user_detail_v2, methods=["GET"]),
    Route("/export", export_users, methods=["GET"]),
]
