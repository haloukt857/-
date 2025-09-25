# -*- coding: utf-8 -*-
"""
用户管理路由模块
处理用户列表、等级管理、积分统计等功能
"""

import logging
from fasthtml.common import *
from starlette.requests import Request

# 导入布局和认证组件
from ..layout import create_layout, require_auth, okx_form_group, okx_input, okx_button, okx_select
from ..services.user_mgmt_service import UserMgmtService

logger = logging.getLogger(__name__)


@require_auth
async def users_dashboard(request: Request):
    """用户管理仪表板"""
    
    # 获取筛选参数
    level_filter = request.query_params.get("level", "")
    search_query = request.query_params.get("search", "")
    page = int(request.query_params.get("page", "1"))
    per_page = int(request.query_params.get("per_page", "20"))
    
    try:
        # 调用服务层获取用户数据
        users_data = await UserMgmtService.get_users_list(
            level_filter=level_filter,
            search_query=search_query,
            page=page,
            per_page=per_page
        )
        
        users = users_data["users"]
        stats = users_data["statistics"]  # 对齐服务层返回字段
        levels = users_data["levels"]
        pagination = users_data["pagination"]
        total_users = pagination["total"]
        
    except Exception as e:
        logger.error(f"获取用户数据失败: {e}")
        error_content = Div(
            H1("用户管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"无法获取用户数据: {str(e)}", cls="text-gray-600")
        )
        return create_layout("系统错误", error_content)
    
    # 统计卡片（对齐旧版字段命名）
    stats_cards = Div(
        Div(
            Div("用户总数", cls="stat-title"),
            Div(str(stats.get('total_users', 0)), cls="stat-value text-primary"),
            cls="stat"
        ),
        Div(
            Div("本周活跃", cls="stat-title"),
            Div(str(stats.get('week_active_users', 0)), cls="stat-value text-success"),
            cls="stat"
        ),
        Div(
            Div("平均积分", cls="stat-title"),
            Div(f"{stats.get('avg_points', 0):.0f}", cls="stat-value text-warning"),
            cls="stat"
        ),
        Div(
            Div("高等级用户", cls="stat-title"),
            Div(str(stats.get('high_level_users', 0)), cls="stat-value text-info"),
            cls="stat"
        ),
        cls="stats shadow mb-6"
    )
    
    # 搜索和筛选表单（对齐旧版布局）
    filter_form = Form(
        Div(
            Div(
                Label("等级筛选", cls="label"),
                Select(
                    Option("所有等级", value="", selected=(not level_filter)),
                    *[Option(level['level_name'], value=level['level_name'], 
                            selected=(level_filter == level['level_name'])) 
                      for level in levels],
                    name="level", cls="select select-bordered w-full"
                ),
                cls="form-control"
            ),
            Div(
                Label("用户搜索", cls="label"),
                Input(
                    name="search", placeholder="用户名或用户ID", value=search_query,
                    cls="input input-bordered w-full"
                ),
                cls="form-control"
            ),
            Div(
                Label("每页显示", cls="label"),
                Select(
                    Option("10条", value="10", selected=(per_page == 10)),
                    Option("20条", value="20", selected=(per_page == 20)),
                    Option("50条", value="50", selected=(per_page == 50)),
                    Option("100条", value="100", selected=(per_page == 100)),
                    name="per_page", cls="select select-bordered w-full"
                ),
                cls="form-control"
            ),
            Div(
                Button("搜索", type="submit", cls="btn btn-primary"),
                A("重置", href="/users", cls="btn btn-ghost ml-2"),
                cls="form-control mt-6"
            ),
            cls="grid grid-cols-1 md:grid-cols-4 gap-4"
        ),
        method="GET",
        action="/users",
        cls="card bg-base-100 shadow-xl p-6 mb-6"
    )
    
    # 工具栏按钮（对齐旧版功能）
    toolbar = Div(
        H3("操作工具", cls="text-xl font-semibold mb-4"),
        Div(
            A("📋 导出数据", 
              href=f"/users/export?level={level_filter}&search={search_query}",
              cls="btn btn-info mr-2"),
            A("📊 查看分析", href="/users/analytics", cls="btn btn-secondary"),
            cls="flex gap-2"
        ),
        cls="card bg-base-100 shadow p-4 mb-6"
    )
    
    # 用户列表表格（对齐旧版列结构）
    user_table = Div(
        Table(
            Thead(
                Tr(
                    Th("用户"),
                    Th("等级"),
                    Th("经验值"),
                    Th("积分"),
                    Th("订单数"),
                    Th("勋章"),
                    Th("操作")
                )
            ),
            Tbody(
                *[
                    Tr(
                        # 用户信息：ID + 用户名
                        Td(
                            Div(
                                P(f"#{user.get('user_id', '-')}", cls="font-mono text-sm text-gray-500"),
                                P(user.get('username', '未设置'), cls="font-semibold"),
                                cls="space-y-1"
                            )
                        ),
                        # 等级徽章
                        Td(
                            Span(user.get('level_name', '新手'), cls="badge badge-primary")
                        ),
                        # 经验值
                        Td(f"{user.get('xp', 0)} XP", cls="font-mono"),
                        # 积分
                        Td(f"{user.get('points', 0)} 分", cls="font-bold text-warning"),
                        # 订单数
                        Td(str(user.get('order_count', 0)), cls="text-success"),
                        # 勋章数
                        Td(
                            # 直接使用已解析的badges列表
                            f"🏆 {len(user.get('badges', []))}"
                        ),
                        # 操作列
                        Td(
                            Div(
                                A("查看详情", href=f"/users/{user.get('user_id')}/detail", 
                                  cls="btn btn-sm btn-primary mr-1"),
                                A("编辑", href=f"/users/{user.get('user_id')}/edit", 
                                  cls="btn btn-sm btn-secondary"),
                                cls="flex gap-1"
                            )
                        )
                    )
                    for user in users
                ] if users else [
                    Tr(
                        Td("暂无用户数据", colspan="7", cls="text-center text-gray-500")
                    )
                ]
            ),
            cls="table table-zebra w-full"
        ),
        cls="overflow-x-auto card bg-base-100 shadow-xl p-6"
    )
    
    # 分页组件（对齐旧版显示格式）
    total_pages = pagination['pages']
    pagination_component = Div(
        Div(f"显示第 {(pagination['page'] - 1) * pagination['per_page'] + 1}–{min(pagination['page'] * pagination['per_page'], pagination['total'])} 条，共 {pagination['total']} 个用户", 
            cls="text-sm text-gray-500 mb-4"),
        Div(
            *([A(str(p), 
                href=f"/users?page={p}&level={level_filter}&search={search_query}&per_page={per_page}",
                cls=f"btn btn-sm {'btn-primary' if p == pagination['page'] else 'btn-ghost'} mr-1")
              for p in range(max(1, pagination['page'] - 2), min(total_pages + 1, pagination['page'] + 3))]
             if total_pages > 1 else []),
            cls="flex flex-wrap gap-1"
        ),
        cls="mt-6" if total_pages > 1 else "mt-6"
    )
    
    content = Div(
        # 页面头部
        Div(
            H1("用户管理", cls="page-title"),
            P("管理系统用户、等级和积分", cls="page-subtitle"),
            cls="page-header"
        ),
        
        # 页面内容（对齐旧版布局）
        Div(
            stats_cards,
            filter_form,
            toolbar,
            user_table,
            pagination_component,
            cls="page-content"
        )
    )
    
    return create_layout("用户管理", content)


@require_auth
async def user_detail(request: Request):
    """用户详情页面（对齐旧版功能）"""
    user_id = int(request.path_params['user_id'])
    
    try:
        # 获取用户详情
        detail_data = await UserMgmtService.get_user_detail(user_id)
        
        if not detail_data['success']:
            error_content = Div(
                H2("用户不存在", cls="text-2xl font-bold text-red-600 mb-4"),
                P(detail_data.get('error', '未知错误')),
                A("返回用户列表", href="/users", cls="btn btn-primary mt-4")
            )
            return create_layout("用户不存在", error_content)
        
        user = detail_data['user']
        activity_history = detail_data['activity_history']
        order_stats = detail_data['order_stats']
        review_stats = detail_data['review_stats']
        badges = detail_data['badges']
        
        # 解析用户勋章JSON
        import json
        user_badges = []
        try:
            if user.get('badges'):
                user_badges = json.loads(user['badges'])
        except:
            user_badges = []
        
        # 基本信息卡片
        user_info_card = Div(
            H3("👤 基本信息", cls="text-xl font-semibold mb-4"),
            Div(
                Div(f"用户ID: #{user.get('user_id', '-')}", cls="font-mono text-lg mb-2"),
                Div(f"用户名: {user.get('username', '未设置')}", cls="text-lg font-semibold mb-3"),
                Div(
                    Span(user.get('level_name', '新手'), cls="badge badge-primary badge-lg mr-2"),
                    f"经验值: {user.get('xp', 0)} XP",
                    cls="mb-2"
                ),
                Div(f"积分: {user.get('points', 0)} 分", cls="text-warning font-bold mb-2"),
                Div(f"完成订单: {user.get('order_count', 0)} 次", cls="text-success font-bold mb-2"),
                Div(f"注册时间: {user.get('created_at', '未知')}", cls="text-gray-500"),
                cls="space-y-2"
            ),
            cls="bg-base-200 p-6 rounded mb-6"
        )
        
        # 勋章展示卡片
        badge_items = []
        for badge in user_badges[:10]:  # 显示最多10个勋章
            badge_items.append(Div(
                Div("🏆", cls="text-2xl mb-1"),
                P(badge if isinstance(badge, str) else badge.get('name', '未知勋章'), 
                  cls="font-medium text-sm text-center"),
                cls="bg-gray-50 p-3 rounded-lg text-center"
            ))
        
        badges_card = Div(
            H3(f"🏆 获得勋章 ({len(user_badges)})", cls="text-xl font-semibold mb-4"),
            Div(
                *badge_items if badge_items else [P("暂无勋章", cls="text-gray-500 text-center py-8")],
                cls="grid grid-cols-2 md:grid-cols-4 gap-3"
            ),
            cls="bg-base-200 p-6 rounded mb-6"
        )
        
        # 统计卡片
        stats_card = Div(
            H3("📊 用户统计", cls="text-xl font-semibold mb-4"),
            Div(
                Div(
                    Div("完成订单", cls="stat-title"),
                    Div(str(order_stats.get('completed_orders', 0)), cls="stat-value text-success"),
                    cls="stat"
                ),
                Div(
                    Div("待处理订单", cls="stat-title"), 
                    Div(str(order_stats.get('pending_orders', 0)), cls="stat-value text-warning"),
                    cls="stat"
                ),
                Div(
                    Div("发表评价", cls="stat-title"),
                    Div(str(review_stats.get('total_reviews', 0)), cls="stat-value text-info"),
                    cls="stat"
                ),
                cls="stats shadow"
            ),
            cls="mb-6"
        )
        
        content = Div(
            H1(f"用户详情 - {user.get('username', f'用户{user_id}')}", cls="page-title"),
            P("查看用户详细信息和统计数据", cls="page-subtitle"),
            
            A("← 返回用户列表", href="/users", cls="btn btn-outline mb-6"),
            
            # 布局：基本信息和勋章
            Div(
                user_info_card,
                badges_card,
                stats_card,
                cls="space-y-6"
            ),
            
            # 快捷入口
            Div(
                A("📊 查看用户分析", href="/users/analytics", cls="btn btn-info mr-2"),
                A("⚙️ 激励管理", href="/incentives", cls="btn btn-secondary"),
                cls="mt-6"
            ),
            
            cls="page-content"
        )
        
        return create_layout("用户详情", content)
        
    except Exception as e:
        logger.error(f"用户详情页面错误: user_id={user_id}, error={e}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        error_content = Div(
            H1("用户详情错误", cls="text-2xl font-bold text-red-600 mb-4"),
            Pre(f"{str(e)}\n\n{traceback.format_exc()}", cls="bg-gray-100 p-4 rounded text-sm")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def export_users(request: Request):
    """导出用户数据为CSV（对齐旧版格式）"""
    try:
        # 获取筛选参数
        params = request.query_params
        level_filter = params.get("level") if params.get("level") else None
        search_query = params.get("search") if params.get("search") else None
        
        # 调用服务层获取导出数据
        users = await UserMgmtService.export_users_csv(
            level_filter=level_filter,
            search_query=search_query,
            limit=10000  # 导出限制
        )
        
        # 创建CSV内容
        import csv
        import io
        from datetime import datetime
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头（对齐旧版）
        writer.writerow([
            '用户ID', '用户名', '等级', '经验值', '积分', '订单数', '勋章数', '注册时间'
        ])
        
        # 写入数据
        for user in users:
            writer.writerow([
                user['user_id'],
                user['username'],
                user['level_name'],
                user['xp'],
                user['points'],
                user['order_count'],
                user['badges_count'],
                user['created_at']
            ])
        
        # 准备响应
        output.seek(0)
        filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        from starlette.responses import StreamingResponse
        
        def generate():
            yield output.getvalue().encode('utf-8-sig')  # BOM for Excel
        
        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"导出用户数据失败: {e}")
        error_content = Div(
            H1("导出失败", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"导出用户数据时发生错误: {str(e)}"),
            A("返回用户管理", href="/users", cls="btn btn-primary mt-4")
        )
        return create_layout("导出失败", error_content)