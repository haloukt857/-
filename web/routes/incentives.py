# -*- coding: utf-8 -*-
"""
激励系统路由模块
处理积分、等级、勋章管理功能
"""

import logging
import json
from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.responses import Response

# 导入布局和认证组件
from ..layout import (
    create_layout, require_auth, okx_button, okx_input, okx_textarea, 
    okx_select, okx_form_group, get_or_create_csrf_token, validate_csrf
)

def verify_csrf_token(request: Request, token: str) -> bool:
    """CSRF令牌验证适配函数"""
    return validate_csrf(request, token)
from ..services.incentive_mgmt_service import IncentiveMgmtService
from database.db_incentives import incentive_manager
from database.db_users import user_manager

logger = logging.getLogger(__name__)


@require_auth
async def user_incentives_management(request: Request):
    """用户激励管理页面"""
    try:
        # 获取用户列表和激励数据
        users_data = await user_manager.get_users_with_incentives()
        levels_data = await incentive_manager.get_all_levels()
        badges_data = await incentive_manager.get_all_badges()
        
        content = Div(
            # 页面标题
            Div(
                H1("用户激励管理", cls="page-title"),
                P("管理用户的积分、经验和勋章奖励", cls="page-subtitle"),
                cls="page-header mb-6"
            ),
            
            # 统计卡片
            Div(
                Div(
                    Div(
                        H3("总用户数", cls="text-lg font-semibold text-base-content"),
                        P(f"{len(users_data)}", cls="text-3xl font-bold text-primary mt-2"),
                        cls="stat"
                    ),
                    cls="stat bg-base-100 rounded-lg shadow"
                ),
                Div(
                    Div(
                        H3("有勋章用户", cls="text-lg font-semibold text-base-content"),
                        P(f"{len([u for u in users_data if u.get('badges', [])])}", cls="text-3xl font-bold text-secondary mt-2"),
                        cls="stat"
                    ),
                    cls="stat bg-base-100 rounded-lg shadow"
                ),
                Div(
                    Div(
                        H3("平均等级", cls="text-lg font-semibold text-base-content"),
                        P(f"{sum(u.get('level', 0) for u in users_data) / len(users_data) if users_data else 0:.1f}", cls="text-3xl font-bold text-accent mt-2"),
                        cls="stat"
                    ),
                    cls="stat bg-base-100 rounded-lg shadow"
                ),
                cls="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8"
            ),
            
            # 操作工具栏
            Div(
                okx_button("批量奖励积分", onclick="showBatchRewardModal()", cls="btn-primary"),
                okx_button("批量授予勋章", onclick="showBatchBadgeModal()", cls="btn-secondary ml-2"),
                okx_button("导出用户数据", href="/incentives/users/export", cls="btn-outline ml-2"),
                cls="flex justify-end mb-6"
            ),
            
            # 用户列表表格
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("用户ID", cls="text-left"),
                            Th("用户名", cls="text-left"),
                            Th("当前等级", cls="text-center"),
                            Th("积分", cls="text-center"),
                            Th("经验值", cls="text-center"),
                            Th("勋章数量", cls="text-center"),
                            Th("操作", cls="text-center")
                        )
                    ),
                    Tbody(
                        *[
                            Tr(
                                Td(str(user.get('id', 'N/A'))),
                                Td(user.get('first_name', 'N/A') + (f" {user.get('last_name', '')}" if user.get('last_name') else "")),
                                Td(f"等级 {user.get('level', 0)}", cls="text-center"),
                                Td(str(user.get('points', 0)), cls="text-center"),
                                Td(str(user.get('experience', 0)), cls="text-center"),
                                Td(str(len(user.get('badges', []))), cls="text-center"),
                                Td(
                                    Div(
                                        okx_button("详情", href=f"/incentives/users/{user.get('id')}/detail", cls="btn-sm btn-primary mr-1"),
                                        okx_button("奖励", onclick=f"showRewardModal({user.get('id')})", cls="btn-sm btn-secondary"),
                                        cls="flex justify-center space-x-1"
                                    ),
                                    cls="text-center"
                                )
                            )
                            for user in users_data
                        ] if users_data else [
                            Tr(
                                Td("暂无用户数据", colspan="7", cls="text-center text-gray-500 py-8")
                            )
                        ]
                    ),
                    cls="table table-zebra w-full"
                ),
                cls="bg-base-100 rounded-lg shadow p-6"
            ),
            
            # 批量奖励模态框
            Dialog(
                Div(
                    H3("批量奖励积分", cls="font-bold text-lg mb-4"),
                    Form(
                        okx_form_group("选择用户", 
                            Select(
                                Option("全部用户", value="all"),
                                Option("指定等级用户", value="level"),
                                Option("指定用户ID", value="specific"),
                                name="user_selection",
                                id="userSelection",
                                onchange="toggleUserSelection()"
                            ),
                            "选择要奖励的用户范围"
                        ),
                        okx_form_group("奖励积分", okx_input("reward_points", type="number", min="1", required=True), "要奖励的积分数量"),
                        okx_form_group("奖励原因", okx_textarea("reward_reason", required=True), "奖励的原因或活动说明"),
                        Div(
                            Button("取消", type="button", cls="btn btn-ghost", onclick="closeBatchRewardModal()"),
                            Button("确认奖励", type="submit", cls="btn btn-primary ml-2"),
                            cls="modal-action"
                        ),
                        method="post",
                        action="/incentives/users/batch-reward"
                    ),
                    cls="modal-box"
                ),
                cls="modal",
                id="batchRewardModal"
            ),
            
            cls="container mx-auto px-4 py-8"
        )
        
        # 添加JavaScript脚本
        script = Script("""
            function showBatchRewardModal() {
                document.getElementById('batchRewardModal').showModal();
            }
            
            function closeBatchRewardModal() {
                document.getElementById('batchRewardModal').close();
            }
            
            function showRewardModal(userId) {
                // 实现单个用户奖励模态框
                alert('奖励用户 ' + userId + ' 的功能待实现');
            }
            
            function toggleUserSelection() {
                const selection = document.getElementById('userSelection').value;
                // 根据选择显示/隐藏相应的输入框
            }
        """)
        
        return create_layout("用户激励管理", Div(content, script))
        
    except Exception as e:
        logger.error(f"用户激励管理页面错误: {e}")
        error_content = Div(
            H2("页面加载失败", cls="text-2xl font-bold mb-4"),
            P(f"错误信息: {str(e)}"),
            A("返回激励系统", href="/incentives", cls="btn btn-primary mt-4")
        )
        return create_layout("错误", error_content)


@require_auth
async def incentives_analytics(request: Request):
    """激励系统数据分析页面"""
    try:
        # 获取分析数据
        analytics_data = await IncentiveMgmtService.get_incentives_analytics()
        
        if not analytics_data.get('success'):
            raise Exception(analytics_data.get('error', '获取分析数据失败'))
            
        stats = analytics_data.get('statistics', {})
        trends = analytics_data.get('trends', {})
        level_dist = analytics_data.get('level_distribution', {})
        badge_dist = analytics_data.get('badge_distribution', {})
        
        content = Div(
            # 页面标题
            Div(
                H1("激励系统数据分析", cls="page-title"),
                P("用户激励系统的深度数据分析和趋势洞察", cls="page-subtitle"),
                cls="page-header mb-6"
            ),
            
            # 核心指标卡片
            Div(
                Div(
                    Div(
                        Div(
                            H3("总用户数", cls="text-sm font-medium text-base-content/70"),
                            P(f"{stats.get('total_users', 0)}", cls="text-2xl font-bold text-primary"),
                            P(f"+{stats.get('new_users_this_month', 0)}本月", cls="text-xs text-success"),
                            cls="stat"
                        ),
                        cls="stat bg-base-100 rounded-lg shadow p-4"
                    ),
                    cls="col-span-1"
                ),
                Div(
                    Div(
                        Div(
                            H3("活跃用户", cls="text-sm font-medium text-base-content/70"),
                            P(f"{stats.get('active_users', 0)}", cls="text-2xl font-bold text-secondary"),
                            P(f"{stats.get('active_rate', 0):.1f}%活跃率", cls="text-xs text-info"),
                            cls="stat"
                        ),
                        cls="stat bg-base-100 rounded-lg shadow p-4"
                    ),
                    cls="col-span-1"
                ),
                Div(
                    Div(
                        Div(
                            H3("平均等级", cls="text-sm font-medium text-base-content/70"),
                            P(f"{stats.get('avg_level', 0):.1f}", cls="text-2xl font-bold text-accent"),
                            P(f"+{stats.get('level_growth', 0):.1f}本月", cls="text-xs text-success"),
                            cls="stat"
                        ),
                        cls="stat bg-base-100 rounded-lg shadow p-4"
                    ),
                    cls="col-span-1"
                ),
                Div(
                    Div(
                        Div(
                            H3("勋章获得", cls="text-sm font-medium text-base-content/70"),
                            P(f"{stats.get('total_badges_awarded', 0)}", cls="text-2xl font-bold text-warning"),
                            P(f"{stats.get('badge_award_rate', 0):.1f}%获得率", cls="text-xs text-info"),
                            cls="stat"
                        ),
                        cls="stat bg-base-100 rounded-lg shadow p-4"
                    ),
                    cls="col-span-1"
                ),
                cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8"
            ),
            
            # 图表区域
            Div(
                # 等级分布图表
                Div(
                    Div(
                        H3("用户等级分布", cls="text-lg font-semibold mb-4"),
                        Div(
                            Canvas(id="levelDistChart", width="400", height="200"),
                            cls="w-full"
                        ),
                        cls="bg-base-100 rounded-lg shadow p-6"
                    ),
                    cls="col-span-1 lg:col-span-2"
                ),
                
                # 勋章获得统计
                Div(
                    Div(
                        H3("勋章获得统计", cls="text-lg font-semibold mb-4"),
                        Div(
                            *[
                                Div(
                                    Div(
                                        Span(badge['name'], cls="font-medium"),
                                        Span(f"{badge['count']}人", cls="text-primary font-bold"),
                                        cls="flex justify-between items-center p-3 bg-base-200 rounded mb-2"
                                    )
                                )
                                for badge in badge_dist.get('badges', [])
                            ] if badge_dist.get('badges') else [
                                P("暂无勋章数据", cls="text-center text-gray-500 py-4")
                            ],
                            cls="max-h-64 overflow-y-auto"
                        ),
                        cls="bg-base-100 rounded-lg shadow p-6"
                    ),
                    cls="col-span-1"
                ),
                
                # 积分趋势图表
                Div(
                    Div(
                        H3("积分增长趋势", cls="text-lg font-semibold mb-4"),
                        Div(
                            Canvas(id="pointsTrendChart", width="400", height="200"),
                            cls="w-full"
                        ),
                        cls="bg-base-100 rounded-lg shadow p-6"
                    ),
                    cls="col-span-1 lg:col-span-3"
                ),
                
                cls="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8"
            ),
            
            # 详细统计表格
            Div(
                H3("等级详细统计", cls="text-lg font-semibold mb-4"),
                Table(
                    Thead(
                        Tr(
                            Th("等级", cls="text-left"),
                            Th("等级名称", cls="text-left"),
                            Th("用户数量", cls="text-center"),
                            Th("占比", cls="text-center"),
                            Th("平均积分", cls="text-center"),
                            Th("平均勋章数", cls="text-center")
                        )
                    ),
                    Tbody(
                        *[
                            Tr(
                                Td(f"等级 {level['level']}"),
                                Td(level['name']),
                                Td(str(level['user_count']), cls="text-center"),
                                Td(f"{level['percentage']:.1f}%", cls="text-center"),
                                Td(str(level['avg_points']), cls="text-center"),
                                Td(f"{level['avg_badges']:.1f}", cls="text-center")
                            )
                            for level in level_dist.get('levels', [])
                        ] if level_dist.get('levels') else [
                            Tr(
                                Td("暂无等级数据", colspan="6", cls="text-center text-gray-500 py-4")
                            )
                        ]
                    ),
                    cls="table table-zebra w-full"
                ),
                cls="bg-base-100 rounded-lg shadow p-6"
            ),
            
            cls="container mx-auto px-4 py-8"
        )
        
        # 添加Chart.js图表脚本
        chart_script = Script("""
            // 等级分布图表
            const levelCtx = document.getElementById('levelDistChart').getContext('2d');
            new Chart(levelCtx, {
                type: 'doughnut',
                data: {
                    labels: %s,
                    datasets: [{
                        data: %s,
                        backgroundColor: [
                            '#3B82F6', '#EF4444', '#10B981', '#F59E0B',
                            '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
            
            // 积分趋势图表
            const trendCtx = document.getElementById('pointsTrendChart').getContext('2d');
            new Chart(trendCtx, {
                type: 'line',
                data: {
                    labels: %s,
                    datasets: [{
                        label: '平均积分',
                        data: %s,
                        borderColor: '#3B82F6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        """ % (
            json.dumps([f"等级{level['level']}" for level in level_dist.get('levels', [])]),
            json.dumps([level['user_count'] for level in level_dist.get('levels', [])]),
            json.dumps(trends.get('dates', [])),
            json.dumps(trends.get('avg_points', []))
        ))
        
        # Chart.js CDN
        chart_cdn = Script(src="https://cdn.jsdelivr.net/npm/chart.js")
        
        return create_layout("激励系统数据分析", Div(content, chart_cdn, chart_script), include_charts=True)
        
    except Exception as e:
        logger.error(f"激励系统数据分析页面错误: {e}")
        error_content = Div(
            H2("数据分析加载失败", cls="text-2xl font-bold mb-4"),
            P(f"错误信息: {str(e)}"),
            A("返回激励系统", href="/incentives", cls="btn btn-primary mt-4")
        )
        return create_layout("错误", error_content)


# =========== 补充：用户激励 辅助路由（占位/轻实现） ==========

@require_auth
async def users_export(request: Request):
    """导出用户数据为CSV（user_id, username, level_name, xp, points, badges）。"""
    try:
        users = await user_manager.get_users_with_incentives()
        rows = ["user_id,username,level_name,xp,points,badges"]
        for u in users:
            badges = u.get('badges')
            if isinstance(badges, list):
                import json as _json
                badges = _json.dumps(badges, ensure_ascii=False)
            # 映射正确的字段名：数据库返回 id, username, level, experience, points
            username = u.get('username') or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            line = f"{u.get('id','')},{username},{u.get('level','')},{u.get('experience','')},{u.get('points','')},{badges or ''}"
            rows.append(line)
        csv = "\n".join(rows)
        return Response(csv, media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="users_export.csv"'})
    except Exception as e:
        logger.error(f"导出用户数据失败: {e}")
        return create_layout("导出失败", Div(P("导出失败"), P(str(e), cls="text-error")))


@require_auth
async def users_batch_reward(request: Request):
    """批量奖励占位实现：仅校验参数，返回成功提示，不做实际修改。"""
    try:
        form = await request.form()
        points = int(form.get('reward_points') or '0')
        if points <= 0:
            raise ValueError("积分必须为正整数")
        # 占位：不执行写操作，避免误发奖励
        return create_layout("批量奖励",
            Div(
                Div(Strong("已接收请求："), Span(f"本功能为占位，未实际发放积分（{points}分）"), cls="alert"
                ),
                A("返回", href="/incentives/users", cls="btn btn-primary mt-4")
            )
        )
    except Exception as e:
        logger.error(f"批量奖励失败: {e}")
        return create_layout("批量奖励失败", Div(P("失败"), P(str(e), cls="text-error")))


@require_auth
async def user_detail(request: Request):
    """用户激励详情（简版）。"""
    try:
        user_id = int(request.path_params.get('user_id'))
        data = await IncentiveMgmtService.get_user_incentive_info(user_id)
        if not data.get('success'):
            raise Exception(data.get('error','获取失败'))
        user = data.get('user', {})
        level_prog = data.get('level_progress', {})
        badges = data.get('badges', [])
        content = Div(
            H1("用户激励详情", cls="page-title"),
            P(f"用户ID：{user.get('user_id')}，用户名：{user.get('username')}", cls="mb-2"),
            P(f"等级：{user.get('level_name')} | XP：{user.get('xp')} | 积分：{user.get('points')}", cls="mb-4"),
            H3("等级进度", cls="text-lg font-semibold"),
            P(f"进度：{level_prog.get('progress_percentage',0):.1f}% ，距离下一等级还需 {level_prog.get('needed_experience',0)} XP"),
            H3("勋章", cls="text-lg font-semibold mt-4"),
            Ul(*[Li(str(b)) for b in badges] or [Li("无")]),
            A("返回", href="/incentives/users", cls="btn btn-primary mt-6")
        )
        return create_layout("用户激励详情", content)
    except Exception as e:
        logger.error(f"用户详情失败: {e}")
        return create_layout("错误", Div(P("加载失败"), P(str(e), cls="text-error")))


@require_auth
async def incentives_dashboard(request: Request):
    """激励系统仪表板 - 概览页面"""
    try:
        # 获取激励系统数据
        dashboard_data = await IncentiveMgmtService.get_incentives_dashboard()
        
        if not dashboard_data.get('success'):
            raise Exception(dashboard_data.get('error', '获取数据失败'))
            
        levels = dashboard_data.get('levels', [])
        badges = dashboard_data.get('badges', [])
        stats = dashboard_data.get('statistics', {})
        level_dist = dashboard_data.get('level_distribution', {})
        badge_stats = dashboard_data.get('badge_stats', {})
        
        content = Div(
            # 页面标题
            Div(
                H1("激励系统管理", cls="page-title"),
                P("管理用户积分、等级和勋章系统", cls="page-subtitle"),
                cls="page-header mb-6"
            ),
            
            # 统计卡片
            Div(
                # 等级数量
                Div(
                    Div(
                        Span("🏆", cls="text-4xl mb-2"),
                        H3("等级配置", cls="font-bold text-white"),
                        P("系统等级数量", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats.get('total_levels', 0)), cls="text-4xl font-bold text-blue-400"),
                        P("个等级", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 勋章数量
                Div(
                    Div(
                        Span("🎖️", cls="text-4xl mb-2"),
                        H3("勋章配置", cls="font-bold text-white"),
                        P("系统勋章数量", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats.get('total_badges', 0)), cls="text-4xl font-bold text-green-400"),
                        P("个勋章", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 拥有勋章用户数
                Div(
                    Div(
                        Span("👥", cls="text-4xl mb-2"),
                        H3("活跃用户", cls="font-bold text-white"),
                        P("拥有勋章用户", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(str(stats.get('total_users_with_badges', 0)), cls="text-4xl font-bold text-purple-400"),
                        P("个用户", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                # 最常见等级
                Div(
                    Div(
                        Span("📊", cls="text-4xl mb-2"),
                        H3("主流等级", cls="font-bold text-white"),
                        P("最常见等级", cls="text-gray-300 text-sm"),
                        cls="text-center"
                    ),
                    Div(
                        Span(stats.get('most_common_level', '新手'), cls="text-2xl font-bold text-yellow-400"),
                        P("等级名称", cls="text-gray-400 text-sm mt-1"),
                        cls="text-center"
                    ),
                    cls="stat-card"
                ),
                
                cls="stats-container mb-8"
            ),
            
            # 快速操作
            Div(
                H2("快速操作", cls="text-xl font-bold mb-4"),
                Div(
                    A(
                        Div(
                            Span("🏆", cls="text-2xl"),
                            Span("等级管理", cls="font-semibold"),
                            P("配置用户等级和经验要求", cls="text-sm text-gray-500"),
                            cls="flex flex-col items-center p-4"
                        ),
                        href="/incentives/levels",
                        cls="card bg-base-100 shadow hover:shadow-lg transition-shadow"
                    ),
                    A(
                        Div(
                            Span("🎖️", cls="text-2xl"),
                            Span("勋章管理", cls="font-semibold"),
                            P("配置勋章和触发条件", cls="text-sm text-gray-500"),
                            cls="flex flex-col items-center p-4"
                        ),
                        href="/incentives/badges",
                        cls="card bg-base-100 shadow hover:shadow-lg transition-shadow"
                    ),
                    A(
                        Div(
                            Span("👥", cls="text-2xl"),
                            Span("用户激励", cls="font-semibold"),
                            P("查看和管理用户激励状态", cls="text-sm text-gray-500"),
                            cls="flex flex-col items-center p-4"
                        ),
                        href="/incentives/users",
                        cls="card bg-base-100 shadow hover:shadow-lg transition-shadow"
                    ),
                    A(
                        Div(
                            Span("📈", cls="text-2xl"),
                            Span("数据分析", cls="font-semibold"),
                            P("激励系统效果分析", cls="text-sm text-gray-500"),
                            cls="flex flex-col items-center p-4"
                        ),
                        href="/incentives/analytics",
                        cls="card bg-base-100 shadow hover:shadow-lg transition-shadow"
                    ),
                    cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"
                ),
                cls="mb-8"
            ),
            
            # 等级分布概览
            (
                Div(
                    H2("等级分布概览", cls="text-xl font-bold mb-4"),
                    Div(
                        *[
                            Div(
                                Span(level_name, cls="font-semibold"),
                                Span(f"{count} 用户", cls="text-sm text-gray-500"),
                                cls="flex justify-between items-center p-3 bg-base-200 rounded"
                            )
                            for level_name, count in (level_dist.items() if level_dist else [('新手', 0)])
                        ],
                        cls="space-y-2"
                    ),
                    cls="card card-body bg-base-100 mb-8"
                ) if level_dist else ""
            ),
            
            cls="page-content"
        )
        
        return create_layout("激励系统管理", content)
        
    except Exception as e:
        logger.error(f"激励系统仪表板错误: {e}")
        error_content = Div(
            H1("激励系统错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600"),
            A("返回首页", href="/", cls="btn btn-primary mt-4")
        )
        return create_layout("系统错误", error_content)


# ==================== 等级管理路由 ==================== #

@require_auth
async def levels_list(request: Request):
    """等级管理列表页面"""
    try:
        # 获取所有等级配置
        levels_data = await IncentiveMgmtService.get_all_levels()
        
        if not levels_data.get('success'):
            raise Exception(levels_data.get('error', '获取等级数据失败'))
            
        levels = levels_data.get('levels', [])
        
        content = Div(
            # 页面头部
            Div(
                H1("等级管理", cls="page-title"),
                P("配置用户等级和经验要求", cls="page-subtitle"),
                cls="page-header mb-6"
            ),
            
            # 操作工具栏
            Div(
                A("新增等级", href="/incentives/levels/create", cls="btn btn-primary"),
                A("返回概览", href="/incentives", cls="btn btn-ghost"),
                cls="flex gap-2 mb-6"
            ),
            
            # 等级列表
            Div(
                H2("等级配置列表", cls="text-xl font-bold mb-4"),
                (
                    Div(
                        Table(
                            Thead(
                                Tr(
                                    Th("等级名称", cls="text-left"),
                                    Th("所需经验", cls="text-center"),
                                    Th("创建时间", cls="text-center"),
                                    Th("操作", cls="text-center"),
                                )
                            ),
                            Tbody(
                                *[
                                    Tr(
                                        Td(level['level_name'], cls="font-semibold"),
                                        Td(str(level['xp_required']), cls="text-center"),
                                        Td("--", cls="text-center text-sm text-gray-500"),  # 创建时间暂无
                                        Td(
                                            Div(
                                                A("编辑", href=f"/incentives/levels/{level['id']}/edit", 
                                                  cls="btn btn-sm btn-outline btn-primary"),
                                                Button("删除", 
                                                       onclick=f"confirmDeleteLevel({level['id']}, '{level['level_name']}')",
                                                       cls="btn btn-sm btn-outline btn-error ml-1"),
                                                cls="flex gap-1 justify-center"
                                            ),
                                            cls="text-center"
                                        ),
                                    )
                                    for level in levels
                                ]
                            ),
                            cls="table table-zebra table-hover w-full"
                        ),
                        cls="overflow-x-auto"
                    ) if levels else Div(
                        P("暂无等级配置，", cls="text-gray-500 inline"),
                        A("立即创建", href="/incentives/levels/create", cls="link link-primary"),
                        cls="text-center py-8"
                    )
                ),
                cls="card card-body bg-base-100"
            ),
            
            cls="page-content"
        )
        
        # 添加删除确认的JavaScript
        content = Div(
            content,
            Script(
                """
                function confirmDeleteLevel(levelId, levelName) {
                    if (confirm(`确定要删除等级 "${levelName}" 吗？\\n\\n注意：删除后不可恢复！`)) {
                        fetch(`/incentives/levels/${levelId}/delete`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({})
                        }).then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                alert('等级删除成功！');
                                location.reload();
                            } else {
                                alert('删除失败: ' + (data.error || '未知错误'));
                            }
                        }).catch(error => {
                            alert('删除失败: ' + error);
                        });
                    }
                }
                """
            )
        )
        
        return create_layout("等级管理", content)
        
    except Exception as e:
        logger.error(f"等级管理页面错误: {e}")
        error_content = Div(
            H1("等级管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600"),
            A("返回激励系统", href="/incentives", cls="btn btn-primary mt-4")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def levels_create(request: Request):
    """等级创建页面"""
    try:
        csrf_token = get_or_create_csrf_token(request)
        
        content = Div(
            # 页面头部
            Div(
                H1("创建等级", cls="page-title"),
                P("新增用户等级配置", cls="page-subtitle"),
                cls="page-header mb-6"
            ),
            
            # 创建表单
            Div(
                H2("等级信息", cls="text-xl font-bold mb-4"),
                Form(
                    # CSRF Token
                    Input(type="hidden", name="csrf_token", value=csrf_token),
                    
                    # 等级名称
                    okx_form_group(
                        "等级名称",
                        okx_input("level_name", placeholder="如：新手、老司机、大师等", required=True),
                        "用户达到此等级时显示的名称"
                    ),
                    
                    # 所需经验
                    okx_form_group(
                        "所需经验值",
                        okx_input("xp_required", type="number", placeholder="0", min="0", required=True),
                        "用户需要多少经验值才能达到此等级"
                    ),
                    
                    # 操作按钮
                    Div(
                        okx_button("创建等级", type="submit", cls="btn btn-primary"),
                        A("取消", href="/incentives/levels", cls="btn btn-ghost ml-2"),
                        cls="flex gap-2 mt-6"
                    ),
                    
                    method="POST",
                    action="/incentives/levels/create",
                    cls="space-y-4"
                ),
                cls="card card-body bg-base-100 max-w-2xl"
            ),
            
            cls="page-content"
        )
        
        return create_layout("创建等级", content)
        
    except Exception as e:
        logger.error(f"等级创建页面错误: {e}")
        error_content = Div(
            H1("页面错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600"),
            A("返回等级列表", href="/incentives/levels", cls="btn btn-primary mt-4")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def levels_create_post(request: Request):
    """处理等级创建提交"""
    try:
        # 获取表单数据
        form_data = await request.form()
        csrf_token = form_data.get('csrf_token')
        level_name = form_data.get('level_name', '').strip()
        xp_required = form_data.get('xp_required', '0')
        
        # 验证CSRF令牌
        if not validate_csrf(request, csrf_token):
            raise Exception("安全验证失败，请重新提交")
        
        # 数据验证
        if not level_name:
            raise Exception("等级名称不能为空")
            
        try:
            xp_required = int(xp_required)
            if xp_required < 0:
                raise ValueError
        except ValueError:
            raise Exception("经验值必须是非负整数")
        
        # 调用服务层创建等级
        result = await IncentiveMgmtService.create_level(level_name, xp_required)
        
        if result.get('success'):
            # 创建成功，重定向到列表页
            return RedirectResponse(url="/incentives/levels?created=1", status_code=302)
        else:
            raise Exception(result.get('error', '等级创建失败'))
            
    except Exception as e:
        logger.error(f"等级创建失败: {e}")
        # 返回带错误信息的创建页面
        csrf_token = get_or_create_csrf_token(request)
        
        content = Div(
            # 错误提示
            Div(
                Div(
                    Strong("创建失败："),
                    Span(str(e)),
                    cls="alert alert-error mb-4"
                )
            ),
            
            # 页面头部
            Div(
                H1("创建等级", cls="page-title"),
                P("新增用户等级配置", cls="page-subtitle"),
                cls="page-header mb-6"
            ),
            
            # 创建表单（保留用户输入）
            Div(
                H2("等级信息", cls="text-xl font-bold mb-4"),
                Form(
                    Input(type="hidden", name="csrf_token", value=csrf_token),
                    
                    okx_form_group(
                        "等级名称",
                        okx_input("level_name", placeholder="如：新手、老司机、大师等", 
                                value=form_data.get('level_name', '') if 'form_data' in locals() else '', required=True),
                        "用户达到此等级时显示的名称"
                    ),
                    
                    okx_form_group(
                        "所需经验值",
                        okx_input("xp_required", type="number", placeholder="0", min="0", 
                                value=form_data.get('xp_required', '') if 'form_data' in locals() else '', required=True),
                        "用户需要多少经验值才能达到此等级"
                    ),
                    
                    Div(
                        okx_button("创建等级", type="submit", cls="btn btn-primary"),
                        A("取消", href="/incentives/levels", cls="btn btn-ghost ml-2"),
                        cls="flex gap-2 mt-6"
                    ),
                    
                    method="POST",
                    action="/incentives/levels/create",
                    cls="space-y-4"
                ),
                cls="card card-body bg-base-100 max-w-2xl"
            ),
            
            cls="page-content"
        )
        
        return create_layout("创建等级", content)


@require_auth
async def levels_edit(request: Request):
    """等级编辑页面"""
    try:
        # 获取等级ID
        level_id = request.path_params.get('level_id')
        if not level_id:
            raise Exception("缺少等级ID参数")
        
        try:
            level_id = int(level_id)
        except ValueError:
            raise Exception("无效的等级ID")
        
        # 获取等级信息
        levels_data = await IncentiveMgmtService.get_all_levels()
        if not levels_data.get('success'):
            raise Exception("获取等级数据失败")
        
        levels = levels_data.get('levels', [])
        level = next((l for l in levels if l['id'] == level_id), None)
        if not level:
            raise Exception("等级不存在")
        
        csrf_token = get_or_create_csrf_token(request)
        
        content = Div(
            # 页面头部
            Div(
                H1(f"编辑等级：{level['level_name']}", cls="page-title"),
                P("修改等级配置信息", cls="page-subtitle"),
                cls="page-header mb-6"
            ),
            
            # 编辑表单
            Div(
                H2("等级信息", cls="text-xl font-bold mb-4"),
                Form(
                    Input(type="hidden", name="csrf_token", value=csrf_token),
                    Input(type="hidden", name="level_id", value=str(level_id)),
                    
                    okx_form_group(
                        "等级名称",
                        okx_input("level_name", placeholder="如：新手、老司机、大师等", 
                                value=level['level_name'], required=True),
                        "用户达到此等级时显示的名称"
                    ),
                    
                    okx_form_group(
                        "所需经验值",
                        okx_input("xp_required", type="number", placeholder="0", min="0", 
                                value=str(level['xp_required']), required=True),
                        "用户需要多少经验值才能达到此等级"
                    ),
                    
                    Div(
                        okx_button("保存修改", type="submit", cls="btn btn-primary"),
                        A("取消", href="/incentives/levels", cls="btn btn-ghost ml-2"),
                        cls="flex gap-2 mt-6"
                    ),
                    
                    method="POST",
                    action=f"/incentives/levels/{level_id}/edit",
                    cls="space-y-4"
                ),
                cls="card card-body bg-base-100 max-w-2xl"
            ),
            
            cls="page-content"
        )
        
        return create_layout("编辑等级", content)
        
    except Exception as e:
        logger.error(f"等级编辑页面错误: {e}")
        error_content = Div(
            H1("页面错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600"),
            A("返回等级列表", href="/incentives/levels", cls="btn btn-primary mt-4")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def levels_edit_post(request: Request):
    """处理等级编辑提交"""
    try:
        # 获取等级ID
        level_id = request.path_params.get('level_id')
        if not level_id:
            raise Exception("缺少等级ID参数")
        
        level_id = int(level_id)
        
        # 获取表单数据
        form_data = await request.form()
        csrf_token = form_data.get('csrf_token')
        level_name = form_data.get('level_name', '').strip()
        xp_required = form_data.get('xp_required', '0')
        
        # 验证CSRF令牌
        if not validate_csrf(request, csrf_token):
            raise Exception("安全验证失败，请重新提交")
        
        # 数据验证
        if not level_name:
            raise Exception("等级名称不能为空")
            
        try:
            xp_required = int(xp_required)
            if xp_required < 0:
                raise ValueError
        except ValueError:
            raise Exception("经验值必须是非负整数")
        
        # 调用服务层更新等级
        result = await IncentiveMgmtService.update_level(level_id, level_name, xp_required)
        
        if result.get('success'):
            # 更新成功，重定向到列表页
            return RedirectResponse(url="/incentives/levels?updated=1", status_code=302)
        else:
            raise Exception(result.get('error', '等级更新失败'))
            
    except Exception as e:
        logger.error(f"等级编辑失败: {e}")
        return RedirectResponse(url=f"/incentives/levels/{level_id}/edit?error={str(e)}", status_code=302)


@require_auth
async def levels_delete_post(request: Request):
    """处理等级删除"""
    try:
        # 获取等级ID
        level_id = request.path_params.get('level_id')
        if not level_id:
            return {"success": False, "error": "缺少等级ID参数"}
        
        level_id = int(level_id)
        
        # 调用服务层删除等级
        result = await IncentiveMgmtService.delete_level(level_id)
        
        return result
        
    except Exception as e:
        logger.error(f"等级删除失败: {e}")
        return {"success": False, "error": str(e)}


# ==================== 勋章管理页面 ==================== #

@require_auth
async def badges_list(request: Request):
    """勋章管理列表页面"""
    
    # 获取勋章数据
    badges_data = await IncentiveMgmtService.get_all_badges_with_triggers()
    
    content = Div(
        # 页面头部
        Div(
            H1("勋章管理", cls="page-title"),
            P("管理系统勋章和触发条件", cls="page-subtitle"),
            cls="page-header"
        ),
        
        # 操作按钮
        Div(
            A("新建勋章", href="/incentives/badges/create", cls="okx-button okx-button-primary"),
            cls="mb-4"
        ),
        
        # 勋章列表
        Div(
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("ID", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                            Th("勋章名称", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                            Th("图标", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                            Th("描述", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                            Th("触发器数量", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                            Th("操作", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                        )
                    ),
                    Tbody(
                        *[
                            Tr(
                                Td(str(badge["id"]), cls="px-4 py-4 whitespace-nowrap text-sm text-gray-300"),
                                Td(badge["badge_name"], cls="px-4 py-4 whitespace-nowrap text-sm text-white font-medium"),
                                Td(badge["badge_icon"], cls="px-4 py-4 whitespace-nowrap text-sm text-gray-300"),
                                Td(badge["description"] or "无描述", cls="px-4 py-4 whitespace-nowrap text-sm text-gray-300"),
                                Td(str(len(badge.get("triggers", []))), cls="px-4 py-4 whitespace-nowrap text-sm text-gray-300"),
                                Td(
                                    Div(
                                        A("编辑", href=f"/incentives/badges/{badge['id']}/edit", 
                                          cls="okx-button okx-button-sm mr-2"),
                                        A("触发器", href=f"/incentives/badges/{badge['id']}/triggers", 
                                          cls="okx-button okx-button-sm okx-button-info mr-2"),
                                        Form(
                                            Input(type="hidden", name="csrf_token", value=request.session.get('csrf_token', '')),
                                            Button("删除", type="submit", 
                                                   cls="okx-button okx-button-sm okx-button-danger",
                                                   onclick=f"return confirm('确认删除勋章 \"{badge['badge_name']}\" 吗？')"),
                                            method="post",
                                            action=f"/incentives/badges/{badge['id']}/delete"
                                        ),
                                        cls="flex"
                                    ),
                                    cls="px-4 py-4 whitespace-nowrap text-sm"
                                ),
                            )
                            for badge in badges_data.get("badges", [])
                        ] if badges_data.get("success") else [
                            Tr(
                                Td("暂无勋章数据", colspan="6", cls="px-4 py-4 text-center text-gray-400"),
                            )
                        ]
                    ),
                    cls="min-w-full divide-y divide-gray-700"
                ),
                cls="overflow-x-auto"
            ),
            cls="table-container"
        ),
        
        cls="page-content"
    )
    
    return create_layout("勋章管理", content)


@require_auth
async def badges_create(request: Request):
    """勋章创建页面"""
    
    content = Div(
        # 页面头部
        Div(
            H1("新建勋章", cls="page-title"),
            P("创建新的系统勋章", cls="page-subtitle"),
            cls="page-header"
        ),
        
        # 创建表单
        Div(
            Form(
                Input(type="hidden", name="csrf_token", value=request.session.get('csrf_token', '')),
                
                # 勋章名称
                okx_form_group(
                    "勋章名称",
                    okx_input("badge_name", placeholder="请输入勋章名称", required=True),
                    "勋章的显示名称"
                ),
                
                # 勋章图标
                okx_form_group(
                    "勋章图标",
                    okx_input("badge_icon", placeholder="请输入勋章图标（emoji或URL）"),
                    "勋章显示的图标"
                ),
                
                # 勋章描述
                okx_form_group(
                    "勋章描述",
                    okx_textarea("description", placeholder="请输入勋章描述"),
                    "勋章的详细描述"
                ),
                
                # 提交按钮
                Div(
                    Button("创建勋章", type="submit", cls="okx-button okx-button-primary mr-2"),
                    A("返回", href="/incentives/badges", cls="okx-button okx-button-secondary"),
                    cls="flex"
                ),
                
                method="post",
                action="/incentives/badges/create",
                cls="form-container"
            ),
            cls="max-w-2xl"
        ),
        
        cls="page-content"
    )
    
    return create_layout("新建勋章", content)


@require_auth
async def badges_create_post(request: Request):
    """处理勋章创建"""
    
    form_data = await request.form()
    
    # CSRF验证
    if not verify_csrf_token(request, form_data.get('csrf_token')):
        return Response("CSRF token invalid", status_code=403)
    
    badge_name = form_data.get('badge_name', '').strip()
    badge_icon = form_data.get('badge_icon', '').strip()
    description = form_data.get('description', '').strip()
    
    # 输入验证
    if not badge_name:
        return Response("勋章名称不能为空", status_code=400)
    
    try:
        # 调用服务层创建勋章
        result = await IncentiveMgmtService.create_badge(
            name=badge_name,
            description=description,
            icon=badge_icon or "🏆"
        )
        
        if result.get('success'):
            return RedirectResponse(url="/incentives/badges", status_code=302)
        else:
            return Response(f"创建失败: {result.get('error', '未知错误')}", status_code=400)
            
    except Exception as e:
        logger.error(f"创建勋章时发生错误: {e}")
        return Response("服务器内部错误", status_code=500)


@require_auth  
async def badges_edit(request: Request):
    """勋章编辑页面"""
    
    badge_id = int(request.path_params['badge_id'])
    
    # 获取勋章数据
    badges_data = await IncentiveMgmtService.get_all_badges_with_triggers()
    badge = None
    
    if badges_data.get('success'):
        for b in badges_data.get('badges', []):
            if b['id'] == badge_id:
                badge = b
                break
    
    if not badge:
        return Response("勋章不存在", status_code=404)
    
    content = Div(
        # 页面头部
        Div(
            H1(f"编辑勋章 - {badge['badge_name']}", cls="page-title"),
            P("修改勋章信息", cls="page-subtitle"),
            cls="page-header"
        ),
        
        # 编辑表单
        Div(
            Form(
                Input(type="hidden", name="csrf_token", value=request.session.get('csrf_token', '')),
                
                # 勋章名称
                okx_form_group(
                    "勋章名称",
                    okx_input("badge_name", value=badge['badge_name'], required=True),
                    "勋章的显示名称"
                ),
                
                # 勋章图标
                okx_form_group(
                    "勋章图标",
                    okx_input("badge_icon", value=badge['badge_icon']),
                    "勋章显示的图标"
                ),
                
                # 勋章描述
                okx_form_group(
                    "勋章描述",
                    okx_textarea("description", value=badge['description'] or ""),
                    "勋章的详细描述"
                ),
                
                # 提交按钮
                Div(
                    Button("保存修改", type="submit", cls="okx-button okx-button-primary mr-2"),
                    A("返回", href="/incentives/badges", cls="okx-button okx-button-secondary"),
                    cls="flex"
                ),
                
                method="post",
                action=f"/incentives/badges/{badge_id}/edit",
                cls="form-container"
            ),
            cls="max-w-2xl"
        ),
        
        cls="page-content"
    )
    
    return create_layout("编辑勋章", content)


@require_auth
async def badges_edit_post(request: Request):
    """处理勋章编辑"""
    
    badge_id = int(request.path_params['badge_id'])
    form_data = await request.form()
    
    # CSRF验证
    if not verify_csrf_token(request, form_data.get('csrf_token')):
        return Response("CSRF token invalid", status_code=403)
    
    badge_name = form_data.get('badge_name', '').strip()
    badge_icon = form_data.get('badge_icon', '').strip()
    description = form_data.get('description', '').strip()
    
    # 输入验证
    if not badge_name:
        return Response("勋章名称不能为空", status_code=400)
    
    try:
        # 调用数据库管理器直接更新勋章
        result = await incentive_manager.update_badge(
            badge_id=badge_id,
            badge_name=badge_name,
            badge_icon=badge_icon,
            description=description
        )
        
        if result:
            return RedirectResponse(url="/incentives/badges", status_code=302)
        else:
            return Response("更新失败", status_code=400)
            
    except Exception as e:
        logger.error(f"更新勋章时发生错误: {e}")
        return Response(f"更新失败: {str(e)}", status_code=500)


@require_auth
async def badges_delete_post(request: Request):
    """处理勋章删除"""
    
    badge_id = int(request.path_params['badge_id'])
    form_data = await request.form()
    
    # CSRF验证
    if not verify_csrf_token(request, form_data.get('csrf_token')):
        return Response("CSRF token invalid", status_code=403)
    
    try:
        # 调用数据库管理器删除勋章
        result = await incentive_manager.delete_badge(badge_id)
        
        if result:
            return RedirectResponse(url="/incentives/badges", status_code=302)
        else:
            return Response("删除失败", status_code=400)
            
    except Exception as e:
        logger.error(f"删除勋章时发生错误: {e}")
        return Response(f"删除失败: {str(e)}", status_code=500)


# ==================== 触发器管理页面 ==================== #

@require_auth
async def badge_triggers(request: Request):
    """勋章触发器管理页面"""
    
    badge_id = int(request.path_params['badge_id'])
    
    # 获取勋章数据
    badges_data = await IncentiveMgmtService.get_all_badges_with_triggers()
    badge = None
    
    if badges_data.get('success'):
        for b in badges_data.get('badges', []):
            if b['id'] == badge_id:
                badge = b
                break
    
    if not badge:
        return Response("勋章不存在", status_code=404)
    
    content = Div(
        # 页面头部
        Div(
            H1(f"触发器管理 - {badge['badge_name']}", cls="page-title"),
            P("管理勋章获得条件", cls="page-subtitle"),
            cls="page-header"
        ),
        
        # 操作按钮
        Div(
            A("新建触发器", href=f"/incentives/badges/{badge_id}/triggers/create", 
              cls="okx-button okx-button-primary mr-2"),
            A("返回勋章列表", href="/incentives/badges", cls="okx-button okx-button-secondary"),
            cls="mb-4"
        ),
        
        # 触发器列表
        Div(
            Div(
                Table(
                    Thead(
                        Tr(
                            Th("ID", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                            Th("触发类型", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                            Th("触发值", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                            Th("操作", cls="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider"),
                        )
                    ),
                    Tbody(
                        *[
                            Tr(
                                Td(str(trigger["id"]), cls="px-4 py-4 whitespace-nowrap text-sm text-gray-300"),
                                Td(trigger["trigger_type"], cls="px-4 py-4 whitespace-nowrap text-sm text-white font-medium"),
                                Td(str(trigger["trigger_value"]), cls="px-4 py-4 whitespace-nowrap text-sm text-gray-300"),
                                Td(
                                    Form(
                                        Input(type="hidden", name="csrf_token", value=request.session.get('csrf_token', '')),
                                        Button("删除", type="submit", 
                                               cls="okx-button okx-button-sm okx-button-danger",
                                               onclick=f"return confirm('确认删除这个触发器吗？')"),
                                        method="post",
                                        action=f"/incentives/badges/{badge_id}/triggers/{trigger['id']}/delete"
                                    ),
                                    cls="px-4 py-4 whitespace-nowrap text-sm"
                                ),
                            )
                            for trigger in badge.get("triggers", [])
                        ] if badge.get("triggers") else [
                            Tr(
                                Td("暂无触发器", colspan="4", cls="px-4 py-4 text-center text-gray-400"),
                            )
                        ]
                    ),
                    cls="min-w-full divide-y divide-gray-700"
                ),
                cls="overflow-x-auto"
            ),
            cls="table-container"
        ),
        
        cls="page-content"
    )
    
    return create_layout("触发器管理", content)


@require_auth
async def badge_triggers_create(request: Request):
    """触发器创建页面"""
    
    badge_id = int(request.path_params['badge_id'])
    
    # 获取勋章名称
    badges_data = await IncentiveMgmtService.get_all_badges_with_triggers()
    badge_name = "未知勋章"
    
    if badges_data.get('success'):
        for b in badges_data.get('badges', []):
            if b['id'] == badge_id:
                badge_name = b['badge_name']
                break
    
    content = Div(
        # 页面头部
        Div(
            H1(f"新建触发器 - {badge_name}", cls="page-title"),
            P("为勋章添加获得条件", cls="page-subtitle"),
            cls="page-header"
        ),
        
        # 创建表单
        Div(
            Form(
                Input(type="hidden", name="csrf_token", value=request.session.get('csrf_token', '')),
                
                # 触发类型
                okx_form_group(
                    "触发类型",
                    okx_select("trigger_type", [
                        ("", "请选择触发类型"),
                        ("order_count", "订单完成数量"),
                        ("perfect_reviews", "完美评价数量"),
                        ("total_points", "累计积分"),
                        ("total_experience", "累计经验"),
                        ("consecutive_good_reviews", "连续好评")
                    ], required=True),
                    "选择勋章的触发条件类型"
                ),
                
                # 触发值
                okx_form_group(
                    "触发值",
                    okx_input("trigger_value", type="number", min="1", required=True, 
                             placeholder="请输入触发条件的数值"),
                    "达到此数值时获得勋章"
                ),
                
                # 提交按钮
                Div(
                    Button("创建触发器", type="submit", cls="okx-button okx-button-primary mr-2"),
                    A("返回", href=f"/incentives/badges/{badge_id}/triggers", cls="okx-button okx-button-secondary"),
                    cls="flex"
                ),
                
                method="post",
                action=f"/incentives/badges/{badge_id}/triggers/create",
                cls="form-container"
            ),
            cls="max-w-2xl"
        ),
        
        cls="page-content"
    )
    
    return create_layout("新建触发器", content)


@require_auth
async def badge_triggers_create_post(request: Request):
    """处理触发器创建"""
    
    badge_id = int(request.path_params['badge_id'])
    form_data = await request.form()
    
    # CSRF验证
    if not verify_csrf_token(request, form_data.get('csrf_token')):
        return Response("CSRF token invalid", status_code=403)
    
    trigger_type = form_data.get('trigger_type', '').strip()
    trigger_value = form_data.get('trigger_value', '').strip()
    
    # 输入验证
    if not trigger_type or not trigger_value:
        return Response("触发类型和触发值不能为空", status_code=400)
    
    try:
        trigger_value_int = int(trigger_value)
        if trigger_value_int <= 0:
            return Response("触发值必须大于0", status_code=400)
    except ValueError:
        return Response("触发值必须是有效数字", status_code=400)
    
    try:
        # 调用服务层创建触发器
        result = await IncentiveMgmtService.create_badge_trigger(
            badge_id=badge_id,
            trigger_type=trigger_type,
            trigger_condition=str(trigger_value_int),
            points_reward=0  # 暂时不使用积分奖励
        )
        
        if result.get('success'):
            return RedirectResponse(url=f"/incentives/badges/{badge_id}/triggers", status_code=302)
        else:
            return Response(f"创建失败: {result.get('error', '未知错误')}", status_code=400)
            
    except Exception as e:
        logger.error(f"创建触发器时发生错误: {e}")
        return Response(f"创建失败: {str(e)}", status_code=500)


@require_auth
async def badge_triggers_delete_post(request: Request):
    """处理触发器删除"""
    
    badge_id = int(request.path_params['badge_id'])
    trigger_id = int(request.path_params['trigger_id'])
    form_data = await request.form()
    
    # CSRF验证
    if not verify_csrf_token(request, form_data.get('csrf_token')):
        return Response("CSRF token invalid", status_code=403)
    
    try:
        # 调用数据库管理器删除触发器
        result = await incentive_manager.delete_trigger(trigger_id)
        
        if result:
            return RedirectResponse(url=f"/incentives/badges/{badge_id}/triggers", status_code=302)
        else:
            return Response("删除失败", status_code=400)
            
    except Exception as e:
        logger.error(f"删除触发器时发生错误: {e}")
        return Response(f"删除失败: {str(e)}", status_code=500)
