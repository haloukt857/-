# -*- coding: utf-8 -*-
"""
对话管理器
"""

from aiogram import Dispatcher

from . import admin_keyword_management, admin_region_management, binding_flow_new, user_service_flow, review_flow
from handlers import admin, user, merchant, statistics, auto_reply, advanced_analytics

def register_all_dialogs(dp: Dispatcher):
    dp.include_router(admin.router)
    dp.include_router(admin_keyword_management.router)
    dp.include_router(admin_region_management.router)
    dp.include_router(statistics.router)
    dp.include_router(advanced_analytics.router)

    dp.include_router(merchant.router)
    dp.include_router(binding_flow_new.router)

    dp.include_router(user.router)
    dp.include_router(user_service_flow.router)
    dp.include_router(review_flow.router)
    
    dp.include_router(auto_reply.router)