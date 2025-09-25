# -*- coding: utf-8 -*-
"""
订单管理模块V2 - FastHTML原生路由实现
完全符合设计文档规范的订单生命周期管理，包含所有模块关联功能
"""

import logging
from datetime import datetime, timedelta
from fasthtml.common import *

# 导入数据库管理器
from database.db_orders import OrderManager
from database.db_merchants import merchant_manager
from database.db_users import user_manager
from database.db_reviews import ReviewManager
from utils.enums import ORDER_STATUS
from config import DEEPLINK_BOT_USERNAME

logger = logging.getLogger(__name__)

# 实例化管理器
order_manager = OrderManager()
review_manager = ReviewManager()

# 订单状态显示映射
ORDER_STATUS_DISPLAY_MAP = {
    ORDER_STATUS.ATTEMPT_BOOKING.value: "尝试预约",
    ORDER_STATUS.COMPLETED.value: "已完成", 
    ORDER_STATUS.REVIEWED.value: "已评价",
    ORDER_STATUS.MUTUAL_REVIEW.value: "双方评价",
    ORDER_STATUS.SINGLE_REVIEW.value: "单方评价"
}

# 订单状态颜色映射
ORDER_STATUS_COLORS = {
    ORDER_STATUS.ATTEMPT_BOOKING.value: "warning",
    ORDER_STATUS.COMPLETED.value: "success", 
    ORDER_STATUS.REVIEWED.value: "info",
    ORDER_STATUS.MUTUAL_REVIEW.value: "primary",
    ORDER_STATUS.SINGLE_REVIEW.value: "secondary"
}

# 订单状态图标映射
ORDER_STATUS_ICONS = {
    ORDER_STATUS.ATTEMPT_BOOKING.value: "⏳",
    ORDER_STATUS.COMPLETED.value: "✅",
    ORDER_STATUS.REVIEWED.value: "⭐", 
    ORDER_STATUS.MUTUAL_REVIEW.value: "🤝",
    ORDER_STATUS.SINGLE_REVIEW.value: "📝"
}

def get_order_status_color(status: str) -> str:
    """根据订单状态返回对应的颜色样式"""
    return ORDER_STATUS_COLORS.get(status, "ghost")

def get_order_status_icon(status: str) -> str:
    """根据订单状态返回对应的图标"""
    return ORDER_STATUS_ICONS.get(status, "❓")

def get_order_next_status_options(current_status: str) -> list:
    """根据当前状态返回可转换的下一状态选项"""
    status_transitions = {
        ORDER_STATUS.ATTEMPT_BOOKING.value: [
            (ORDER_STATUS.ATTEMPT_BOOKING.value, "尝试预约"),
            (ORDER_STATUS.COMPLETED.value, "标记完成")
        ],
        ORDER_STATUS.COMPLETED.value: [
            (ORDER_STATUS.COMPLETED.value, "已完成"),
            (ORDER_STATUS.REVIEWED.value, "用户已评价"),
            (ORDER_STATUS.ATTEMPT_BOOKING.value, "退回预约中")
        ],
        ORDER_STATUS.REVIEWED.value: [
            (ORDER_STATUS.REVIEWED.value, "已评价"),
            (ORDER_STATUS.MUTUAL_REVIEW.value, "双方已评价"),
            (ORDER_STATUS.SINGLE_REVIEW.value, "单方评价")
        ],
        ORDER_STATUS.MUTUAL_REVIEW.value: [
            (ORDER_STATUS.MUTUAL_REVIEW.value, "双方评价"),
            (ORDER_STATUS.REVIEWED.value, "退回已评价")
        ],
        ORDER_STATUS.SINGLE_REVIEW.value: [
            (ORDER_STATUS.SINGLE_REVIEW.value, "单方评价"),
            (ORDER_STATUS.MUTUAL_REVIEW.value, "补充对方评价")
        ]
    }
    
    return status_transitions.get(current_status, [(current_status, "当前状态")])

def generate_order_action_buttons(order_id: str, current_status: str, merchant_id: int = None, customer_user_id: int = None) -> list:
    """根据当前状态生成订单操作按钮，包含所有模块关联功能"""
    buttons = []
    
    # 基础状态操作按钮
    if current_status == ORDER_STATUS.ATTEMPT_BOOKING.value:
        buttons.extend([
            Form(
                Button("标记完成", type="submit", cls="btn btn-success btn-sm"),
                method="post", action=f"/orders/{order_id}/complete"
            ),
            Form(
                Button("取消订单", type="submit", cls="btn btn-error btn-sm"),
                method="post", action=f"/orders/{order_id}/cancel"
            )
        ])
    
    elif current_status == ORDER_STATUS.COMPLETED.value:
        buttons.extend([
            Form(
                Button("标记已评价", type="submit", cls="btn btn-info btn-sm"),
                method="post", action=f"/orders/{order_id}/mark_reviewed"
            )
        ])
    
    # 模块关联按钮
    
    # 1. 商家管理模块关联 - 查看商户详情
    if merchant_id:
        buttons.append(
            A("查看商户", href=f"/merchants/{merchant_id}", 
              cls="btn btn-outline btn-primary btn-sm", title="跳转到商家管理模块")
        )
        
        # Telegram深度链接到商户
        buttons.append(
            A("联系商户", href=f"https://t.me/{DEEPLINK_BOT_USERNAME}?start=merchant_{merchant_id}", 
              target="_blank", cls="btn btn-outline btn-info btn-sm", 
              title="通过Telegram联系商户")
        )
    
    # 2. 用户管理模块关联 - 查看用户资料
    if customer_user_id:
        buttons.append(
            A("查看用户", href=f"/users/{customer_user_id}", 
              cls="btn btn-outline btn-secondary btn-sm", title="跳转到用户管理模块")
        )
    
    # 3. 双向评价系统关联 - 查看/管理评价
    if current_status in [ORDER_STATUS.REVIEWED.value, ORDER_STATUS.MUTUAL_REVIEW.value, ORDER_STATUS.SINGLE_REVIEW.value]:
        buttons.extend([
            A("查看评价", href=f"/reviews/order/{order_id}", 
              cls="btn btn-outline btn-warning btn-sm", title="查看该订单的评价详情"),
            A("评价管理", href=f"/reviews?order_id={order_id}", 
              cls="btn btn-outline btn-accent btn-sm", title="跳转到评价管理模块")
        ])
    
    # 4. 数据分析按钮
    buttons.append(
        A("订单分析", href=f"/orders/analytics?merchant_id={merchant_id}&customer_id={customer_user_id}", 
          cls="btn btn-outline btn-neutral btn-sm", title="查看相关数据分析")
    )
    
    return buttons

def generate_order_batch_operations() -> Div:
    """生成批量操作组件"""
    return Div(
        H4("批量操作", cls="text-lg font-semibold mb-2"),
        Form(
            Div(
                Select(
                    Option("选择批量操作", value="", selected=True, disabled=True),
                    Option("批量标记完成", value="batch_complete"),
                    Option("批量标记已评价", value="batch_reviewed"),
                    Option("批量取消", value="batch_cancel"),
                    Option("批量导出", value="batch_export"),
                    name="batch_action", cls="select select-bordered"
                ),
                Button("执行", type="submit", cls="btn btn-primary ml-2"),
                cls="flex items-center gap-2"
            ),
            P("请先选择要操作的订单，然后选择批量操作", cls="text-sm text-gray-500 mt-1"),
            method="post", action="/orders/batch"
        ),
        cls="bg-base-200 p-4 rounded-lg mb-4"
    )

def generate_order_statistics_panel(stats: dict) -> Div:
    """生成订单统计面板"""
    return Div(
        H3("订单统计", cls="text-xl font-bold mb-4"),
        
        # 状态统计
        Div(
            *[
                Div(
                    Div(
                        Span(get_order_status_icon(status), cls="text-2xl"),
                        Span(str(count), cls="text-2xl font-bold ml-2"),
                        cls="flex items-center"
                    ),
                    P(ORDER_STATUS_DISPLAY_MAP.get(status, status), 
                      cls="text-sm text-gray-500"),
                    cls=f"stat bg-base-200 rounded-lg p-4"
                )
                for status, count in stats.get('by_status', {}).items()
            ],
            cls="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6"
        ),
        
        # 趋势统计
        Div(
            Div(
                Div("今日新订单", cls="stat-title"),
                Div(str(stats.get('today_orders', 0)), cls="stat-value text-primary"),
                cls="stat"
            ),
            Div(
                Div("本周完成", cls="stat-title"),
                Div(str(stats.get('week_completed', 0)), cls="stat-value text-success"),
                cls="stat"
            ),
            Div(
                Div("总成交额", cls="stat-title"),
                Div(f"¥{stats.get('total_amount', 0)}", cls="stat-value text-info"),
                cls="stat"
            ),
            cls="stats stats-vertical lg:stats-horizontal shadow mb-6"
        ),
        
        cls="bg-base-100 p-6 rounded-lg shadow mb-6"
    )

# 导出所有FastHTML路由函数供app.py使用
__all__ = [
    'ORDER_STATUS_DISPLAY_MAP',
    'ORDER_STATUS_COLORS', 
    'ORDER_STATUS_ICONS',
    'get_order_status_color',
    'get_order_status_icon',
    'get_order_next_status_options',
    'generate_order_action_buttons',
    'generate_order_batch_operations',
    'generate_order_statistics_panel'
]
