# -*- coding: utf-8 -*-
"""
键盘工具
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any

def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="🔍 按地区搜索商家", callback_data="search_start")],
        [InlineKeyboardButton(text="👤 我的资料", callback_data="profile")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_city_keyboard(cities: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=city['name'], callback_data=f"city_{city['id']}") for city in cities]
    keyboard = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_district_keyboard(districts: List[Dict[str, Any]], city_id: int) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=dist['name'], callback_data=f"district_{dist['id']}") for dist in districts]
    keyboard = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
    keyboard.append([InlineKeyboardButton(text="⬅️ 返回城市选择", callback_data="search_start")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_merchants_keyboard(merchants: List[Dict[str, Any]], city_id: int) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=m['name'], callback_data=f"merchant_{m['id']}") for m in merchants]
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton(text="⬅️ 返回地区选择", callback_data=f"city_{city_id}")]) 
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_merchant_detail_keyboard(merchant: Dict[str, Any]) -> InlineKeyboardMarkup:
    """商家详情页键盘：仅显示预约与返回。
    注意：频道链接与联系方式不在此处展示，按需求在用户点击“立即预约”后再显示。
    """
    keyboard = [[InlineKeyboardButton(text=f"✅ 立即预约", callback_data=f"order_now_{merchant.get('id')}")]]
    ch = merchant.get('channel_chat_id') or merchant.get('channel_link')
    if isinstance(ch, str) and ch.strip():
        keyboard.append([InlineKeyboardButton(text="📣 查看频道", callback_data=f"view_channel_{merchant.get('id')}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ 返回商家列表", callback_data=f"district_{merchant['district_id']}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_rating_keyboard() -> InlineKeyboardMarkup:
    dims = {'颜值': 'appearance', '身材': 'figure', '服务': 'service', '态度': 'attitude', '环境': 'environment'}
    keyboard = []
    for name, dim in dims.items():
        row = [InlineKeyboardButton(text=name, callback_data="noop")] # No-op button for label
        row.extend([InlineKeyboardButton(text=f"{i}⭐", callback_data=f"rating_{dim}_{i}") for i in range(1, 6)])
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_text_review_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(text="跳过文字评价并提交", callback_data="skip_text_review")]    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_final_confirmation_keyboard() -> InlineKeyboardMarkup:
    """创建最终确认键盘"""
    keyboard = [
        [InlineKeyboardButton(text="✅ 确认提交", callback_data="confirm_submit")],
        [InlineKeyboardButton(text="✏️ 修改信息", callback_data="edit_info")],
        [InlineKeyboardButton(text="❌ 取消", callback_data="cancel_submit")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_media_upload_keyboard() -> InlineKeyboardMarkup:
    """创建媒体上传键盘"""
    keyboard = [
        [InlineKeyboardButton(text="📷 上传照片", callback_data="upload_photo")],
        [InlineKeyboardButton(text="🎥 上传视频", callback_data="upload_video")],
        [InlineKeyboardButton(text="✅ 跳过", callback_data="skip_media")],
        [InlineKeyboardButton(text="➡️ 继续", callback_data="continue_flow")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_region_selection_keyboard(regions: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """创建地区选择键盘"""
    buttons = []
    for region in regions:
        buttons.append([InlineKeyboardButton(
            text=region['name'], 
            callback_data=f"select_region_{region['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="❌ 取消", callback_data="cancel_region_selection")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_category_selection_keyboard() -> InlineKeyboardMarkup:
    """创建商户类型选择键盘"""
    keyboard = [
        [InlineKeyboardButton(text="👩‍🏫 教师", callback_data="category_teacher")],
        [InlineKeyboardButton(text="💼 商务", callback_data="category_business")],
        [InlineKeyboardButton(text="🎭 艺人", callback_data="category_artist")],
        [InlineKeyboardButton(text="🏥 医护", callback_data="category_medical")],
        [InlineKeyboardButton(text="🔧 其他", callback_data="category_other")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
