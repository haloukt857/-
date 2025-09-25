# -*- coding: utf-8 -*-
"""
商户绑定与信息提交流程
使用aiogram FSM状态机实现灵活、可中断的对话式信息收集。
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandObject

# 导入工具函数
from utils.telegram_helpers import safe_edit_message

# 导入数据库管理器
from database.db_binding_codes import binding_codes_manager
from database.db_merchants import merchant_manager
from database.db_regions import region_manager
from database.db_media import media_db

# 导入状态和键盘工具
from dialogs.states import MerchantOnboardingStates
from utils.keyboard_utils import create_city_keyboard, create_district_keyboard, create_final_confirmation_keyboard, create_media_upload_keyboard

logger = logging.getLogger(__name__)
router = Router()

# --- 1. /bind 命令处理器 (FSM入口) ---
@router.message(Command("bind"))
async def cmd_bind(message: Message, state: FSMContext, command: CommandObject):
    if not command.args:
        await message.answer("格式错误！请使用 `/bind <您的绑定码>`。")
        return

    code = command.args.strip()
    binding_data = await binding_codes_manager.get_code_data(code)
    if not binding_data or binding_data['is_used']:
        await message.answer("绑定码无效或已被使用。")
        return

    existing_merchant = await merchant_manager.get_merchant_by_telegram_id(message.from_user.id)
    if existing_merchant:
        await message.answer(f"您的账号已绑定到商户ID: {existing_merchant['id']}，无需重复绑定。")
        return

    try:
        new_merchant_id = await merchant_manager.create_merchant_record(message.from_user.id, message.from_user.username)
        if not new_merchant_id:
            await message.answer("创建商户记录失败，请联系管理员。")
            return

        await binding_codes_manager.mark_code_as_used(code, new_merchant_id, message.from_user.username, message.from_user.full_name)
        
        await state.clear()
        await state.update_data(merchant_id=new_merchant_id, media_files=[])
        await state.set_state(MerchantOnboardingStates.AwaitingName)
        
        await message.answer(f"✅ 绑定成功！您的永久商户ID是 **{new_merchant_id}**。\n\n现在，请发送您的商户名称（例如：莉莉按摩）", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"绑定流程中发生严重错误: {e}")
        await message.answer("绑定过程中发生内部错误，请稍后重试或联系管理员。")

# --- 2. FSM 状态处理器 ---

@router.message(MerchantOnboardingStates.AwaitingName, F.text)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    cities = await region_manager.get_all_cities_with_districts()
    await state.update_data(cities_cache=cities) # 缓存数据以备后用
    await state.set_state(MerchantOnboardingStates.AwaitingCity)
    await message.answer("名称已保存。请选择您所在的 **城市**：", reply_markup=create_city_keyboard(cities))

@router.callback_query(MerchantOnboardingStates.AwaitingCity, F.data.startswith("city_"))
async def process_city_selection(callback: CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split('_')[1])
    await state.update_data(city_id=city_id)
    
    data = await state.get_data()
    cities_cache = data.get('cities_cache', [])
    districts = []
    for city in cities_cache:
        if city['id'] == city_id:
            districts = city['districts']
            break

    await state.set_state(MerchantOnboardingStates.AwaitingDistrict)
    await safe_edit_message(callback.message, "请选择您所在的 **地区**：", reply_markup=create_district_keyboard(districts, city_id))
    await callback.answer()

@router.callback_query(MerchantOnboardingStates.AwaitingDistrict, F.data.startswith("district_"))
async def process_district_selection(callback: CallbackQuery, state: FSMContext):
    district_id = int(callback.data.split('_')[1])
    await state.update_data(district_id=district_id)
    await state.set_state(MerchantOnboardingStates.AwaitingPrice1)
    await safe_edit_message(callback.message, "地区已保存。请输入您的第一档价格（纯数字）：")
    await callback.answer()

# ... (为 Price1, Price2, Advantages, Disadvantages, BasicSkills 添加类似的文本处理器) ...

@router.message(MerchantOnboardingStates.AwaitingPrice1, F.text)
async def process_price1(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price_1=price)
        await state.set_state(MerchantOnboardingStates.AwaitingPrice2)
        await message.answer("价格已保存。请输入第二档价格（纯数字）：")
    except ValueError:
        await message.answer("请输入有效的数字价格。")

# ... (此处省略其他文本状态的处理器，逻辑类似) ...

@router.message(MerchantOnboardingStates.AwaitingMedia, F.photo | F.video)
async def process_media(message: Message, state: FSMContext):
    data = await state.get_data()
    media_files = data.get('media_files', [])

    if len(media_files) >= 6:
        await message.answer("您最多只能上传6个媒体文件。请点击下方的“完成上传”。")
        return

    file_id = message.photo[-1].file_id if message.photo else message.video.file_id
    media_type = 'photo' if message.photo else 'video'
    media_files.append({"file_id": file_id, "type": media_type})
    await state.update_data(media_files=media_files)
    await message.answer(f"已收到 {len(media_files)}/6 个文件。您可以继续发送，或点击“完成上传”。", reply_markup=create_media_upload_keyboard())

@router.callback_query(MerchantOnboardingStates.AwaitingMedia, F.data == "done_uploading")
async def done_uploading_media(callback: CallbackQuery, state: FSMContext):
    # ... (显示最终确认信息的逻辑) ...
    await state.set_state(MerchantOnboardingStates.AwaitingConfirmation)
    # ... (此处省略生成确认文本和键盘的代码) ...
    await safe_edit_message(callback.message, "所有信息已收集完毕，请确认：\n...", reply_markup=create_final_confirmation_keyboard())

@router.callback_query(MerchantOnboardingStates.AwaitingConfirmation, F.data == "confirm_submission")
async def process_final_submission(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    merchant_id = data['merchant_id']

    try:
        # 更新商家主表
        update_data = {
            "name": data.get('name'),
            "district_id": data.get('district_id'),
            "price_1": data.get('price_1'),
            # ... 其他字段 ...
            "status": "pending_approval" # 关键步骤
        }
        await merchant_manager.update_merchant(merchant_id, update_data)

        # 插入媒体文件
        for media in data.get('media_files', []):
            await media_db.add_media(merchant_id, media['file_id'], media['type'])

        await state.clear()
        await safe_edit_message(callback.message, "✅ 您的资料已成功提交，请等待管理员审核。" )
    except Exception as e:
        logger.error(f"最终提交失败，商户ID {merchant_id}: {e}")
        await safe_edit_message(callback.message, "提交失败，发生内部错误，请联系管理员。")
    finally:
        await callback.answer()
