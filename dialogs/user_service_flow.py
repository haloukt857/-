# -*- coding: utf-8 -*-
"""
用户服务流程对话框

包括地区搜索、商家查看、订单创建等FSM流程。
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

# 导入工具函数
from utils.telegram_helpers import safe_edit_message

from .states import UserSearchStates, UserOrderStates # 假设UserOrderStates已在states.py中定义
from database.db_regions import region_manager
from database.db_merchants import merchant_manager
from database.db_orders import order_manager
from utils.keyboard_utils import create_city_keyboard, create_district_keyboard, create_merchants_keyboard, create_merchant_detail_keyboard

logger = logging.getLogger(__name__)
router = Router()

# --- 地区搜索 FSM ---

@router.callback_query(F.data == "search_start")
async def start_search_flow(callback: CallbackQuery, state: FSMContext):
    """FSM入口：用户点击'按地区搜索商家'"""
    await state.clear()
    cities = await region_manager.get_all_cities_with_districts()
    if not cities:
        await safe_edit_message(callback.message, "抱歉，当前没有任何城市提供服务。")
        await callback.answer()
        return

    await state.set_state(UserSearchStates.AwaitingCity)
    await safe_edit_message(callback.message, "请选择您要搜索的城市：", reply_markup=create_city_keyboard(cities))
    await callback.answer()

@router.callback_query(UserSearchStates.AwaitingCity, F.data.startswith("city_"))
async def process_city_search(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split('_')[1])
    districts = await region_manager.get_districts_by_city(city_id)
    if not districts:
        await safe_edit_message(callback.message, "该城市下暂无地区，请重新选择。", reply_markup=create_city_keyboard(await region_manager.get_all_cities_with_districts()))
        await state.set_state(UserSearchStates.AwaitingCity)
        return

    await state.update_data(city_id=city_id)
    await state.set_state(UserSearchStates.AwaitingDistrict)
    await safe_edit_message(callback.message, "请选择地区：", reply_markup=create_district_keyboard(districts, city_id))
    await callback.answer()

@router.callback_query(UserSearchStates.AwaitingDistrict, F.data.startswith("district_"))
async def process_district_search(callback: CallbackQuery, state: FSMContext):
    district_id = int(callback.data.split('_')[1])
    merchants = await merchant_manager.get_merchants(status='published', district_id=district_id) # 假设get_merchants支持district_id
    if not merchants:
        await safe_edit_message(callback.message, "该地区暂无在线商户，请重新选择。", reply_markup=create_district_keyboard(await region_manager.get_districts_by_city((await state.get_data()).get('city_id')), (await state.get_data()).get('city_id')))
        # 保持在AwaitingDistrict状态，但不改变键盘
        return
    await state.update_data(district_id=district_id)
    await state.set_state(UserSearchStates.ViewingMerchants)
    await safe_edit_message(callback.message, "请选择要查看的商家：", reply_markup=create_merchants_keyboard(merchants, (await state.get_data()).get('city_id')))

@router.callback_query(UserSearchStates.ViewingMerchants, F.data.startswith("merchant_"))
async def process_merchant_selection(callback: CallbackQuery, state: FSMContext):
    merchant_id = int(callback.data.split('_')[1])
    merchant = await merchant_manager.get_merchant_details(merchant_id)
    if not merchant or merchant['status'] != 'published':
        await callback.answer("该商家当前不可用。", show_alert=True)
        return
    
    # 格式化商家详情
    details_text = f"**{merchant['name']}**\n\n**优点**: {merchant['advantages']}\n**缺点**: {merchant['disadvantages']}"
    await state.update_data(merchant_id=merchant_id, price_1=merchant['price_1'], price_2=merchant['price_2'])
    await state.set_state(UserSearchStates.ViewingMerchantDetails)
    await safe_edit_message(callback.message, details_text, reply_markup=create_merchant_detail_keyboard(merchant), parse_mode="Markdown")

# --- 订单创建 FSM ---

@router.callback_query(UserSearchStates.ViewingMerchantDetails, F.data == "order_now")
async def start_order_flow(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserOrderStates.ConfirmingOrder) # 切换到订单FSM
    data = await state.get_data()
    # ... 此处省略向用户确认订单信息的逻辑 ...
    await order_manager.create_order(customer_user_id=callback.from_user.id, merchant_id=data['merchant_id'], price=data['price_1']) # 简化处理
    await safe_edit_message(callback.message, "订单已创建！")
    await state.clear()