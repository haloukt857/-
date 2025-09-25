# -*- coding: utf-8 -*-
"""
帖子管理模块V2 - FastHTML原生路由实现
完全符合设计文档规范的帖子生命周期管理
"""

import logging
from datetime import datetime, timedelta
from starlette.requests import Request
from starlette.responses import RedirectResponse
from fasthtml.common import *

# 导入数据库管理器
from database.db_merchants import merchant_manager
from database.db_media import media_db
from database.db_regions import region_manager
from utils.enums import MERCHANT_STATUS

logger = logging.getLogger(__name__)

# 帖子状态显示映射
POST_STATUS_DISPLAY_MAP = {
    MERCHANT_STATUS.PENDING_SUBMISSION.value: "待提交",
    MERCHANT_STATUS.PENDING_APPROVAL.value: "待审核", 
    MERCHANT_STATUS.APPROVED.value: "已审核",
    MERCHANT_STATUS.PUBLISHED.value: "已发布",
    MERCHANT_STATUS.EXPIRED.value: "已过期"
}

# 帖子状态操作映射
POST_STATUS_ACTIONS = {
    MERCHANT_STATUS.PENDING_APPROVAL.value: ["批准发布", "驳回修改"],
    MERCHANT_STATUS.APPROVED.value: ["立即发布", "修改时间", "暂停发布"],
    MERCHANT_STATUS.PUBLISHED.value: ["设为过期", "延长时间"],
    MERCHANT_STATUS.EXPIRED.value: ["重新发布", "删除帖子"]
}

def get_posts_status_color(status: str) -> str:
    """根据帖子状态返回对应的颜色样式"""
    color_map = {
        MERCHANT_STATUS.PENDING_SUBMISSION.value: "secondary",
        MERCHANT_STATUS.PENDING_APPROVAL.value: "warning", 
        MERCHANT_STATUS.APPROVED.value: "info",
        MERCHANT_STATUS.PUBLISHED.value: "success",
        MERCHANT_STATUS.EXPIRED.value: "error"
    }
    return color_map.get(status, "ghost")

def get_posts_next_status_options(current_status: str) -> list:
    """根据当前状态返回可转换的下一状态选项"""
    status_transitions = {
        MERCHANT_STATUS.PENDING_SUBMISSION.value: [
            (MERCHANT_STATUS.PENDING_SUBMISSION.value, "待提交"),
            (MERCHANT_STATUS.PENDING_APPROVAL.value, "提交审核")
        ],
        MERCHANT_STATUS.PENDING_APPROVAL.value: [
            (MERCHANT_STATUS.PENDING_APPROVAL.value, "待审核"),
            (MERCHANT_STATUS.APPROVED.value, "批准发布"),
            (MERCHANT_STATUS.PENDING_SUBMISSION.value, "退回修改")
        ],
        MERCHANT_STATUS.APPROVED.value: [
            (MERCHANT_STATUS.APPROVED.value, "已审核"),
            (MERCHANT_STATUS.PUBLISHED.value, "立即发布"),
            (MERCHANT_STATUS.PENDING_APPROVAL.value, "退回审核")
        ],
        MERCHANT_STATUS.PUBLISHED.value: [
            (MERCHANT_STATUS.PUBLISHED.value, "已发布"),
            (MERCHANT_STATUS.EXPIRED.value, "设为过期"),
            (MERCHANT_STATUS.APPROVED.value, "暂停发布")
        ],
        MERCHANT_STATUS.EXPIRED.value: [
            (MERCHANT_STATUS.EXPIRED.value, "已过期"),
            (MERCHANT_STATUS.APPROVED.value, "重新发布")
        ]
    }
    
    return status_transitions.get(current_status, [(current_status, "当前状态")])

def generate_posts_quick_action_buttons(post_id: str, current_status: str) -> list:
    """根据当前状态生成快速操作按钮"""
    buttons = []
    
    if current_status == MERCHANT_STATUS.PENDING_APPROVAL.value:
        buttons.extend([
            Form(
                Button("立即批准", type="submit", cls="btn btn-success btn-sm"),
                method="post", action=f"/posts/{post_id}/approve"
            ),
            Form(
                Button("驳回修改", type="submit", cls="btn btn-warning btn-sm"),
                method="post", action=f"/posts/{post_id}/reject"
            )
        ])
    
    elif current_status == MERCHANT_STATUS.APPROVED.value:
        buttons.extend([
            Form(
                Button("立即发布", type="submit", cls="btn btn-info btn-sm"),
                method="post", action=f"/posts/{post_id}/publish"
            ),
            Form(
                Button("延长1天", type="submit", cls="btn btn-ghost btn-sm"),
                Input(type="hidden", name="days", value="1"),
                method="post", action=f"/posts/{post_id}/extend"
            )
        ])
    
    elif current_status == MERCHANT_STATUS.PUBLISHED.value:
        buttons.extend([
            Form(
                Button("设为过期", type="submit", cls="btn btn-warning btn-sm"),
                method="post", action=f"/posts/{post_id}/expire"
            ),
            Form(
                Button("延长1天", type="submit", cls="btn btn-ghost btn-sm"),
                Input(type="hidden", name="days", value="1"),
                method="post", action=f"/posts/{post_id}/extend"
            )
        ])
    
    return buttons

# 导出所有FastHTML路由函数供app.py使用
__all__ = [
    'POST_STATUS_DISPLAY_MAP',
    'POST_STATUS_ACTIONS', 
    'get_posts_status_color',
    'get_posts_next_status_options',
    'generate_posts_quick_action_buttons'
]