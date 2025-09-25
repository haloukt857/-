# -*- coding: utf-8 -*-
"""
频道订阅验证管理路由 V2.0
提供频道订阅验证系统的完整Web管理界面
"""

import logging
from typing import Any, Dict, List, Optional
from starlette.routing import Route
from starlette.responses import RedirectResponse, Response, StreamingResponse, HTMLResponse
from starlette.exceptions import HTTPException
from starlette.requests import Request
from datetime import datetime, timedelta
import csv
import io
import json

from database.db_system_config import system_config_manager
from database.db_users import user_manager
from web.layout import create_layout, require_auth, okx_form_group, okx_input, okx_button, okx_textarea, okx_select
from fasthtml.common import *

logger = logging.getLogger(__name__)

@require_auth
async def subscription_dashboard(request: Request) -> Response:
    """频道订阅验证管理仪表板"""
    
    try:
        # 获取当前配置
        config = await system_config_manager.get_config(
            'subscription_verification_config',
            {"enabled": False, "required_subscriptions": []}
        )
        
        # 获取统计数据
        stats = await _get_subscription_statistics()
        
    except Exception as e:
        logger.error(f"获取订阅验证数据失败: {e}")
        raise HTTPException(status_code=500, detail="无法获取订阅验证数据")
    
    # 状态指示器
    status_indicator = Div(
        Div(
            Span("🟢" if config.get("enabled") else "🔴", cls="text-2xl"),
            Div(
                H3("订阅验证状态", cls="text-lg font-semibold"),
                P("已启用" if config.get("enabled") else "已禁用", 
                  cls=f"text-sm {'text-success' if config.get('enabled') else 'text-error'}"),
                cls="ml-3"
            ),
            cls="flex items-center"
        ),
        cls="bg-white p-6 rounded-lg shadow mb-6"
    )
    
    # 统计卡片
    stats_cards = Div(
        # 配置的频道数
        Div(
            Div(
                Span("📺", cls="text-3xl"),
                Div(
                    P("配置频道", cls="text-sm text-gray-500"),
                    P(str(len(config.get("required_subscriptions", []))), cls="text-2xl font-bold text-primary")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 今日验证次数
        Div(
            Div(
                Span("🔍", cls="text-3xl"),
                Div(
                    P("今日验证", cls="text-sm text-gray-500"),
                    P(str(stats['daily_verifications']), cls="text-2xl font-bold text-info")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 通过率
        Div(
            Div(
                Span("✅", cls="text-3xl"),
                Div(
                    P("通过率", cls="text-sm text-gray-500"),
                    P(f"{stats['pass_rate']:.1f}%", cls="text-2xl font-bold text-success")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        # 失败用户数
        Div(
            Div(
                Span("❌", cls="text-3xl"),
                Div(
                    P("今日失败", cls="text-sm text-gray-500"),
                    P(str(stats['daily_failures']), cls="text-2xl font-bold text-warning")
                ),
                cls="flex items-center gap-3"
            ),
            cls="stat-card"
        ),
        
        cls="stats-container"
    )
    
    # 快速操作工具栏
    toolbar = Div(
        Div(
            H3("系统控制", cls="content-section-title"),
            P("频道订阅验证系统的开关和管理", cls="text-sm text-gray-500"),
        ),
        Div(
            # 启用/禁用按钮
            Form(
                okx_button(
                    "🔴 禁用验证" if config.get("enabled") else "🟢 启用验证",
                    type="submit",
                    cls=f"btn {'btn-error' if config.get('enabled') else 'btn-success'} btn-sm"
                ),
                method="post",
                action="/subscription/toggle",
                cls="inline-block mr-3"
            ),
            
            A("📊 验证日志", href="/subscription/logs", cls="btn btn-info btn-sm mr-3"),
            A("⚙️ 频道配置", href="/subscription/channels", cls="btn btn-secondary btn-sm mr-3"),
            A("📈 数据分析", href="/subscription/analytics", cls="btn btn-outline btn-sm"),
            cls="action-buttons"
        ),
        cls="toolbar-container"
    )
    
    # 频道配置表格
    channels = config.get("required_subscriptions", [])
    channel_rows = []
    
    for i, channel in enumerate(channels):
        row = Tr(
            Td(str(i + 1), cls="font-mono text-sm"),
            Td(
                Div(
                    Strong(channel.get("display_name", "未命名")),
                    P(channel.get("chat_id", ""), cls="text-xs text-gray-500 font-mono"),
                    cls="space-y-1"
                )
            ),
            Td(
                A("🔗", href=channel.get("join_link", "#"), target="_blank", 
                  cls="btn btn-ghost btn-xs") if channel.get("join_link") else "无链接",
                cls="text-center"
            ),
            Td(
                Div(
                    A("✏️", href=f"/subscription/channel/{i}/edit", 
                      cls="btn btn-ghost btn-xs", title="编辑"),
                    A("🗑️", href=f"/subscription/channel/{i}/delete", 
                      cls="btn btn-ghost btn-xs text-error", title="删除",
                      onclick="return confirm('确定删除此频道配置？')"),
                    cls="flex gap-1"
                )
            )
        )
        channel_rows.append(row)
    
    channels_table = Div(
        H3("📺 频道配置", cls="content-section-title"),
        Div(
            Table(
                Thead(
                    Tr(Th("#"), Th("频道信息"), Th("加入链接", cls="text-center"), Th("操作", cls="w-20"))
                ),
                Tbody(*channel_rows),
                cls="table table-zebra w-full"
            ) if channel_rows else Div(
                P("暂无配置频道", cls="text-gray-500 text-center py-8"),
                A("+ 添加频道", href="/subscription/channel/add", cls="btn btn-primary btn-sm")
            ),
            cls="data-table-container"
        )
    )
    
    # 添加频道表单
    add_channel_form = Form(
        Div(
            H3("➕ 添加频道", cls="text-lg font-semibold mb-4"),
            okx_form_group("频道名称", okx_input("display_name", placeholder="如：官方频道")),
            okx_form_group("频道ID", okx_input("chat_id", placeholder="@channel 或 -1001234567890")),
            okx_form_group("加入链接", okx_input("join_link", placeholder="https://t.me/channel")),
            okx_button("添加频道", type="submit", cls="btn btn-primary w-full"),
            cls="space-y-4"
        ),
        method="post",
        action="/subscription/channel/add",
        cls="card bg-base-100 shadow-lg p-6"
    )
    
    # 验证设置表单
    verification_settings_form = Form(
        Div(
            H3("⚙️ 验证设置", cls="text-lg font-semibold mb-4"),
            
            # 基础设置
            Div(
                Label("验证模式", cls="label-text font-medium"),
                okx_select("verification_mode", [
                    ("strict", "严格模式 - 必须订阅所有频道"),
                    ("flexible", "灵活模式 - 订阅任意频道即可")
                ], selected="strict", cls="select select-bordered w-full"),
                cls="form-control mb-4"
            ),
            
            Div(
                Label("提醒消息模板", cls="label-text font-medium"),
                okx_textarea("reminder_template", 
                           content="❌ 您需要先关注以下频道才能使用机器人功能：",
                           placeholder="自定义提醒消息...",
                           rows=3),
                cls="form-control mb-4"
            ),
            
            Div(
                Label("缓存时间（分钟）", cls="label-text font-medium"),
                okx_input("cache_duration", type="number", value="30", min="5", max="1440"),
                P("设置用户订阅状态的缓存时间", cls="text-xs text-gray-500 mt-1"),
                cls="form-control mb-4"
            ),
            
            okx_button("保存设置", type="submit", cls="btn btn-success w-full"),
            cls="space-y-4"
        ),
        method="post",
        action="/subscription/settings/update",
        cls="card bg-base-100 shadow-lg p-6"
    )
    
    content = Div(
        Div(
            H1("频道订阅验证管理", cls="page-title"),
            A("📊 查看分析", href="/subscription/analytics", cls="btn btn-outline btn-sm"),
            cls="page-header"
        ),
        
        status_indicator,
        stats_cards,
        toolbar,
        
        # 主要内容区域
        Div(
            Div(channels_table, cls="lg:col-span-2"),
            Div(
                add_channel_form,
                verification_settings_form,
                cls="space-y-6"
            ),
            cls="content-grid grid-3"
        )
    )
    
    return HTMLResponse(str(create_layout("频道订阅验证管理", content)))

@require_auth
async def toggle_subscription_verification(request: Request) -> Response:
    """切换订阅验证状态"""
    try:
        # 获取当前配置
        config = await system_config_manager.get_config(
            'subscription_verification_config',
            {"enabled": False, "required_subscriptions": []}
        )
        
        # 切换状态
        config["enabled"] = not config.get("enabled", False)
        
        # 保存配置
        await system_config_manager.set_config(
            'subscription_verification_config',
            config,
            '频道订阅验证配置'
        )
        
        status = "启用" if config["enabled"] else "禁用"
        logger.info(f"频道订阅验证已{status}")
        
        return RedirectResponse(url="/subscription?status_changed=1", status_code=302)
        
    except Exception as e:
        logger.error(f"切换订阅验证状态失败: {e}")
        return RedirectResponse(url="/subscription?error=toggle_failed", status_code=302)

@require_auth
async def add_channel(request: Request) -> Response:
    """添加频道配置"""
    form = await request.form()
    
    try:
        display_name = form.get('display_name', '').strip()
        chat_id = form.get('chat_id', '').strip()
        join_link = form.get('join_link', '').strip()
        
        if not display_name or not chat_id:
            return RedirectResponse(url="/subscription?error=missing_fields", status_code=302)
        
        # 获取当前配置
        config = await system_config_manager.get_config(
            'subscription_verification_config',
            {"enabled": False, "required_subscriptions": []}
        )
        
        # 检查chat_id是否已存在
        existing_ids = [sub.get("chat_id") for sub in config.get("required_subscriptions", [])]
        if chat_id in existing_ids:
            return RedirectResponse(url="/subscription?error=duplicate_chat_id", status_code=302)
        
        # 添加新频道
        new_channel = {
            "chat_id": chat_id,
            "display_name": display_name,
            "join_link": join_link if join_link else None
        }
        
        config.setdefault("required_subscriptions", []).append(new_channel)
        
        # 保存配置
        await system_config_manager.set_config(
            'subscription_verification_config',
            config,
            '频道订阅验证配置'
        )
        
        logger.info(f"频道 {display_name} ({chat_id}) 添加成功")
        return RedirectResponse(url="/subscription?channel_added=1", status_code=302)
        
    except Exception as e:
        logger.error(f"添加频道失败: {e}")
        return RedirectResponse(url="/subscription?error=add_failed", status_code=302)

@require_auth
async def delete_channel(request: Request) -> Response:
    """删除频道配置"""
    try:
        channel_index = int(request.path_params['index'])
        
        # 获取当前配置
        config = await system_config_manager.get_config(
            'subscription_verification_config',
            {"enabled": False, "required_subscriptions": []}
        )
        
        subscriptions = config.get("required_subscriptions", [])
        
        if 0 <= channel_index < len(subscriptions):
            deleted_channel = subscriptions.pop(channel_index)
            
            # 保存配置
            await system_config_manager.set_config(
                'subscription_verification_config',
                config,
                '频道订阅验证配置'
            )
            
            logger.info(f"频道 {deleted_channel.get('display_name')} 删除成功")
            return RedirectResponse(url="/subscription?channel_deleted=1", status_code=302)
        else:
            return RedirectResponse(url="/subscription?error=invalid_index", status_code=302)
            
    except Exception as e:
        logger.error(f"删除频道失败: {e}")
        return RedirectResponse(url="/subscription?error=delete_failed", status_code=302)

async def _get_subscription_statistics() -> Dict[str, Any]:
    try:
        return {
            'daily_verifications': 0,
            'daily_failures': 0,
            'pass_rate': 100.0,
            'weekly_verifications': 0,
        }
    except Exception:
        return {
            'daily_verifications': 0,
            'daily_failures': 0,
            'pass_rate': 0.0,
            'weekly_verifications': 0,
        }

# 导出路由列表
subscription_v2_routes = [
    Route("/", subscription_dashboard, methods=["GET"]),
    Route("/toggle", toggle_subscription_verification, methods=["POST"]),
    Route("/channel/add", add_channel, methods=["POST"]),
    Route("/channel/{index}/delete", delete_channel, methods=["GET"]),
]
