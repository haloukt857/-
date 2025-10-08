# -*- coding: utf-8 -*-
"""
精简版FastHTML Web管理面板 - 主应用入口
负责应用初始化、中间件配置、路由注册和异常处理
"""

import logging
import os
from fasthtml.common import *
import os
import asyncio
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from starlette.requests import Request

# 导入布局组件
from .layout import create_layout

# 导入配置
from config import WEB_CONFIG, bot_config

# 导入所有路由模块
from .routes import (
    auth, dashboard, merchants, users, orders,
    reviews, regions, incentives, subscription,
    binding_codes, posts, templates, debug, media, user_analytics, scheduling, channels, broadcast, keywords
)
if os.getenv('RUN_MODE', 'dev') == 'dev':
    from .routes import dev_tools

logger = logging.getLogger(__name__)

# === 应用初始化 ===

# UI资源
daisyui_css = Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css")
tailwind_css = Script(src="https://cdn.tailwindcss.com")
okx_theme_css = Link(rel="stylesheet", href="/static/css/okx-theme.css")

# 创建应用实例
app = FastHTML(hdrs=[daisyui_css, tailwind_css, okx_theme_css, Meta(name="viewport", content="width=device-width, initial-scale=1.0")])

# === 中间件配置 ===

# 静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")

# Session中间件
app.add_middleware(SessionMiddleware, secret_key=WEB_CONFIG.get("secret_key", "your-secret-key-here"), max_age=86400)

# 启动后台任务队列（异步Telegram I/O）
@app.on_event("startup")
async def _start_bg_queue():
    try:
        from services.task_queue import start_task_workers
        await start_task_workers(worker_count=2)
        logger.info("后台任务队列已启动（web）")
    except Exception as e:
        logger.warning(f"后台任务队列启动失败（web）: {e}")

# === 异常处理 ===

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理HTTP异常"""
    if exc.status_code == 404:
        content = create_layout(
            "页面未找到",
            Div(
                H2("页面未找到", cls="text-2xl font-bold mb-4"),
                P("您访问的页面不存在。"),
                A("返回首页", href="/", cls="btn btn-primary mt-4")
            )
        )
        return HTMLResponse(content, status_code=404)
    
    # 其他HTTP错误的通用处理
    content = create_layout(
        f"错误 {exc.status_code}",
        Div(
            H2(f"服务器错误 {exc.status_code}", cls="text-2xl font-bold mb-4"),
            P(exc.detail or "发生了未知错误"),
            A("返回首页", href="/", cls="btn btn-primary mt-4")
        )
    )
    return HTMLResponse(content, status_code=exc.status_code)

# === 路由注册 ===

# 认证路由
app.get("/login")(auth.login_page)
app.post("/login")(auth.login_submit)
app.get("/logout")(auth.logout)

# 仪表板路由（根路径）
app.get("/")(dashboard.dashboard)

# 商户管理路由
app.get("/merchants")(merchants.merchants_list)
# 商户详情 + 管理动作（仅前端/服务层，不改后端逻辑）
app.get("/merchants/{merchant_id}/detail")(merchants.merchant_detail)
app.post("/merchants/{merchant_id}/status")(merchants.merchant_update_status)
app.post("/merchants/manual-region-toggle")(merchants.manual_region_toggle)
app.post("/merchants/{merchant_id}/region-allow")(merchants.merchant_region_allow)
app.post("/merchants/{merchant_id}/region-remove")(merchants.merchant_region_remove)
app.post("/merchants/{merchant_id}/refresh")(merchants.merchant_refresh_info)

# 用户管理路由
app.get("/users")(users.users_dashboard)
app.get("/users/{user_id}/detail")(users.user_detail)
app.get("/users/export")(users.export_users)
app.get("/users/analytics")(user_analytics.user_analytics_dashboard)
app.get("/users/analytics-data")(user_analytics.user_analytics_data_api)
app.get("/users/leaderboards")(users.users_leaderboards)

# 订单管理路由（完整对齐旧版功能）
app.get("/orders")(orders.orders_list)                                  # 订单列表页
app.get("/orders/{order_id}")(orders.order_detail)                      # 订单详情页  
app.post("/orders/{order_id}/update_status")(orders.order_update_status) # 更新订单状态
app.get("/orders/{order_id}/complete")(orders.order_complete)           # 快速完成
app.get("/orders/{order_id}/cancel")(orders.order_cancel)               # 快速取消
app.get("/orders/{order_id}/mark_reviewed")(orders.order_mark_reviewed) # 标记已评价
app.post("/orders/batch")(orders.orders_batch_operation)                # 批量操作

# 评价管理路由
app.get("/reviews")(reviews.reviews_list)
app.get("/reviews/{id}/detail")(reviews.review_detail)
app.get("/reviews/export")(reviews.export_reviews)

# 地区管理路由
app.get("/regions")(regions.regions_list)

# 城市管理路由
app.post("/regions/city/add")(regions.add_city_route)
app.post("/regions/city/{city_id}/delete")(regions.delete_city_route)
app.get("/regions/city/{city_id}/edit")(regions.edit_city_get_route)
app.post("/regions/city/{city_id}/edit")(regions.edit_city_post_route)
app.post("/regions/city/{city_id}/toggle")(regions.toggle_city_status_route)

# 区县管理路由
app.post("/regions/district/add")(regions.add_district_route)
app.post("/regions/district/{district_id}/delete")(regions.delete_district_route)
app.get("/regions/district/{district_id}/edit")(regions.edit_district_get_route)
app.post("/regions/district/{district_id}/edit")(regions.edit_district_post_route)
app.post("/regions/district/{district_id}/toggle")(regions.toggle_district_status_route)

# 激励系统路由
app.get("/incentives")(incentives.incentives_dashboard)
app.get("/incentives/rules")(incentives.incentive_rules)
app.post("/incentives/rules")(incentives.incentive_rules_post)

# 等级管理路由
app.get("/incentives/levels")(incentives.levels_list)
app.get("/incentives/levels/create")(incentives.levels_create)
app.post("/incentives/levels/create")(incentives.levels_create_post)
app.get("/incentives/levels/{level_id}/edit")(incentives.levels_edit)
app.post("/incentives/levels/{level_id}/edit")(incentives.levels_edit_post)
app.post("/incentives/levels/{level_id}/delete")(incentives.levels_delete_post)

# 勋章管理路由
app.get("/incentives/badges")(incentives.badges_list)
app.get("/incentives/badges/create")(incentives.badges_create)
app.post("/incentives/badges/create")(incentives.badges_create_post)
app.get("/incentives/badges/{badge_id}/edit")(incentives.badges_edit)
app.post("/incentives/badges/{badge_id}/edit")(incentives.badges_edit_post)
app.post("/incentives/badges/{badge_id}/delete")(incentives.badges_delete_post)

# 触发器管理路由
app.get("/incentives/badges/{badge_id}/triggers")(incentives.badge_triggers)
app.get("/incentives/badges/{badge_id}/triggers/create")(incentives.badge_triggers_create)
app.post("/incentives/badges/{badge_id}/triggers/create")(incentives.badge_triggers_create_post)
app.post("/incentives/badges/{badge_id}/triggers/{trigger_id}/delete")(incentives.badge_triggers_delete_post)

# 用户激励管理路由
app.get("/incentives/users")(incentives.user_incentives_management)
app.get("/incentives/users/export")(incentives.users_export)
app.post("/incentives/users/batch-reward")(incentives.users_batch_reward)
app.get("/incentives/users/{user_id}/detail")(incentives.user_detail)

# 激励系统数据分析路由
app.get("/incentives/analytics")(incentives.incentives_analytics)

# 订阅管理路由
app.get("/subscription")(subscription.subscription_dashboard)
app.post("/subscription/toggle")(subscription.subscription_toggle_post)
app.post("/subscription/channels/add")(subscription.subscription_add_channel_post)
app.post("/subscription/channels/remove")(subscription.subscription_remove_channel_post)

# 自动回复管理路由
from .routes import auto_reply
app.get("/auto-reply")(auto_reply.auto_reply_dashboard)
app.post("/auto-reply/triggers/create")(auto_reply.trigger_create_post)
app.post("/auto-reply/triggers/{trigger_id:int}/update")(auto_reply.trigger_update_post)
app.post("/auto-reply/triggers/{trigger_id:int}/delete")(auto_reply.trigger_delete_post)
app.post("/auto-reply/messages/create")(auto_reply.message_create_post)
app.post("/auto-reply/messages/{message_id:int}/update")(auto_reply.message_update_post)
app.post("/auto-reply/messages/{message_id:int}/delete")(auto_reply.message_delete_post)

# 绑定码管理路由
app.get("/binding-codes")(binding_codes.binding_codes_list)
app.get("/binding-codes/generate")(binding_codes.binding_codes_generate_page)
app.post("/binding-codes/generate")(binding_codes.binding_codes_generate_action)
app.get("/binding-codes/{code}/detail")(binding_codes.binding_code_detail)
app.post("/binding-codes/{code}/delete")(binding_codes.binding_code_delete)
app.get("/binding-codes/export")(binding_codes.binding_codes_export)

# 时间槽配置
app.route("/schedule/time-slots", methods=['GET', 'POST'])(scheduling.time_slots_page)

# 频道配置
app.route("/channels/config", methods=['GET', 'POST'])(channels.channel_config_page)

# 关键词管理（配置中心）
try:
    app.get("/config/keywords")(keywords.keywords_list)
    app.post("/config/keywords/create")(keywords.keywords_create)
    app.post("/config/keywords/update")(keywords.keywords_update)
    app.post("/config/keywords/{keyword_id:int}/delete")(keywords.keywords_delete)
except Exception:
    pass

# 手动广播
app.get("/broadcast")(broadcast.broadcast_page)
app.post("/broadcast/send")(broadcast.broadcast_send)
app.get("/broadcast/status")(broadcast.broadcast_status_api)

# 帖子管理路由
app.get("/posts")(posts.posts_list)
app.get("/posts/{post_id:int}")(posts.post_detail)
app.post("/posts/{post_id:int}/update")(posts.post_update)
app.post("/posts/{post_id:int}/approve")(posts.post_approve)
app.post("/posts/{post_id:int}/reject")(posts.post_reject)
app.post("/posts/{post_id:int}/publish")(posts.post_publish)
app.post("/posts/{post_id:int}/expire")(posts.post_expire)
app.post("/posts/{post_id:int}/extend")(posts.post_extend)
app.post("/posts/{post_id:int}/delete")(posts.post_delete)
app.get("/posts/new")(posts.post_new)
app.post("/posts/create")(posts.post_create)
app.get("/posts/{post_id:int}/caption-preview")(posts.post_caption_preview)
app.post("/posts/{post_id:int}/media-order")(posts.post_media_order_save)

# 模板管理路由
app.get("/templates")(templates.templates_list)
app.get("/templates/new")(templates.template_new)
app.post("/templates/create")(templates.template_create)
app.get("/templates/{key:str}/edit")(templates.template_edit)
app.post("/templates/{key:str}/update")(templates.template_update)
app.post("/templates/{key:str}/delete")(templates.template_delete)

# 媒体代理路由
app.get("/media-proxy/{media_id:int}")(media.media_proxy)

# 调试路由（开发环境）
if os.getenv('RUN_MODE', 'dev') == 'dev':
    app.get("/debug/style-check")(debug.debug_dashboard)
    # 开发工具：重置模板
    app.post("/dev/reset-templates")(dev_tools.reset_templates)
    # 开发工具：重置数据库
    app.post("/dev/reset-database")(dev_tools.reset_database)

# === 启动日志 ===

logger.info("Web应用已初始化完成")
logger.info(f"运行模式: {os.getenv('RUN_MODE', 'dev')}")
logger.info("所有路由已注册完成")

# 导出应用实例

# 健康检查端点（供Railway/监控使用）
@app.get("/health")
async def healthcheck():
    return JSONResponse({"status": "ok"})

# 在Web进程内启动调度器（单服务部署时使用）
try:
    # 本地(dev)默认不启动；云端/生产默认启动。可通过 SCHEDULER_ENABLED 显式覆盖。
    _sched_env = os.getenv('SCHEDULER_ENABLED')
    if _sched_env is None:
        enable_scheduler = os.getenv('RUN_MODE', 'dev').lower() != 'dev'
    else:
        enable_scheduler = _sched_env.lower() == 'true'

    if enable_scheduler:
        from scheduler import SchedulerWorker
        _worker = SchedulerWorker()
        # 使用 Starlette 事件钩子启动/停止调度器
        try:
            app.add_event_handler('startup', lambda: asyncio.create_task(_worker.start()))
            app.add_event_handler('shutdown', lambda: asyncio.create_task(_worker.stop()))
            logger.info("Scheduler 已挂接到 Web 应用的启动/停止事件")
        except Exception as e:
            logger.warning(f"注册调度器事件失败（将忽略）：{e}")
    else:
        logger.info("SCHEDULER: 开发/本地模式默认不启动（可用 SCHEDULER_ENABLED=true 覆盖）")
except Exception:
    pass

# 集成 Telegram Webhook 到同一 Web 进程（仅在 Webhook 模式/云端生效）
try:
    if bot_config.use_webhook:
        from bot import TelegramMerchantBot
        from aiogram.types import Update

        _bot_instance = TelegramMerchantBot()

        async def _bot_startup():
            try:
                await _bot_instance._on_startup()
                logger.info("Bot 已随 Web 应用启动 (Webhook 模式)")
            except Exception as e:
                logger.error(f"Bot 启动失败: {e}")

        async def _bot_shutdown():
            try:
                await _bot_instance._on_shutdown()
                logger.info("Bot 已随 Web 应用关闭")
            except Exception as e:
                logger.error(f"Bot 关闭失败: {e}")

        app.add_event_handler('startup', lambda: asyncio.create_task(_bot_startup()))
        app.add_event_handler('shutdown', lambda: asyncio.create_task(_bot_shutdown()))

        @app.post(bot_config.webhook_path)
        async def telegram_webhook(request: Request):
            try:
                payload = await request.json()
                update = Update.model_validate(payload)
                await _bot_instance.dp.feed_update(_bot_instance.bot, update)
                return JSONResponse({"ok": True})
            except Exception as e:
                logger.error(f"Webhook 处理失败: {e}")
                return JSONResponse({"ok": False, "error": str(e)}, status_code=200)
        logger.info(f"已注册 Telegram Webhook 路由: {bot_config.webhook_path}")
    else:
        logger.info("Webhook: 开发/本地模式 (USE_WEBHOOK=false)，不在 Web 应用中集成。")
except Exception as e:
    logger.error(f"集成 Telegram Webhook 失败: {e}")
__all__ = ['app']
