# -*- coding: utf-8 -*-
"""
最小化单测：验证“优势一句话”输入后会返回“确认并继续”按钮，
确保上榜流程在步骤6→7不再卡住。

依赖现有fixtures（tests/conftest.py）中的 mock_message 与 asyncio 事件循环。
"""

import pytest
from unittest.mock import AsyncMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup

from dialogs.states import MerchantStates


@pytest.mark.asyncio
async def test_adv_sentence_confirms_and_moves_on(mock_message):
    # 在导入 handlers.merchant 前，注入 web.services.* 轻量桩，避免依赖 starlette
    import sys, types
    pkg_web = types.ModuleType("web")
    pkg_services = types.ModuleType("web.services")
    mod_mgmt = types.ModuleType("web.services.merchant_mgmt_service")

    class _DummyMgmt:
        @staticmethod
        async def refresh_telegram_user_info(merchant_id: int):
            return True

    mod_mgmt.MerchantMgmtService = _DummyMgmt
    sys.modules.setdefault("web", pkg_web)
    sys.modules.setdefault("web.services", pkg_services)
    sys.modules.setdefault("web.services.merchant_mgmt_service", mod_mgmt)

    # 延迟导入以便fixtures和桩准备完成
    from handlers import merchant as merchant_mod
    from handlers.merchant import handle_binding_text_input

    # 准备 message 的可await方法
    from unittest.mock import AsyncMock as _AsyncMock
    mock_message.answer = _AsyncMock()

    # 模拟FSM上下文
    state = AsyncMock(spec=FSMContext)
    state.get_state.return_value = MerchantStates.entering_adv_sentence
    state.get_data.return_value = {"user_choices": {}}

    # 准备用户输入
    mock_message.text = "很有优势，服务到位"

    # 建立最小的 merchant_handler 桩
    import types as _types
    dummy_handler = _types.SimpleNamespace(
        flow_state_name="merchant_binding_flow",
        _update_merchant_draft=AsyncMock(return_value=True),
        binding_flow_manager=None,
    )
    merchant_mod.merchant_handler = dummy_handler

    # 避免真实落库：打桩 fsm_db.save_user_state（由 handlers.merchant 内部引用）
    with patch("handlers.merchant.fsm_db.save_user_state", new=AsyncMock(return_value=True)):
        await handle_binding_text_input(mock_message, state)

    # 断言出现了“已记录优势”提示并携带了内联按钮
    assert mock_message.answer.await_count >= 1
    text_arg = mock_message.answer.call_args.kwargs.get("text") or mock_message.answer.call_args.args[0]
    reply_markup = (
        mock_message.answer.call_args.kwargs.get("reply_markup")
        or (len(mock_message.answer.call_args.args) > 1 and mock_message.answer.call_args.args[1])
        or None
    )

    assert "已记录优势" in text_arg
    assert isinstance(reply_markup, InlineKeyboardMarkup)

    # 校验按钮中包含“确认并继续”对应的回调数据
    all_cb = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert "binding_confirm_step7" in all_cb


@pytest.mark.asyncio
async def test_p_price_confirms_and_moves_on(mock_message):
    from handlers import merchant as merchant_mod
    from handlers.merchant import handle_binding_text_input
    from unittest.mock import AsyncMock as _AsyncMock

    mock_message.answer = _AsyncMock()

    # FSM
    state = AsyncMock(spec=FSMContext)
    state.get_state.return_value = MerchantStates.entering_p_price
    state.get_data.return_value = {"user_choices": {}}

    # minimal handler stub
    import types as _types
    merchant_mod.merchant_handler = _types.SimpleNamespace(
        flow_state_name="merchant_binding_flow",
        _update_merchant_draft=_AsyncMock(return_value=True),
        binding_flow_manager=None,
    )

    # input
    mock_message.text = "88"

    with patch("handlers.merchant.fsm_db.save_user_state", new=_AsyncMock(return_value=True)):
        await handle_binding_text_input(mock_message, state)

    text_arg = mock_message.answer.call_args.kwargs.get("text") or mock_message.answer.call_args.args[0]
    reply_markup = (
        mock_message.answer.call_args.kwargs.get("reply_markup")
        or (len(mock_message.answer.call_args.args) > 1 and mock_message.answer.call_args.args[1])
        or None
    )
    assert "已记录 P 价格" in text_arg
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    all_cb = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert "binding_confirm_step5" in all_cb


@pytest.mark.asyncio
async def test_pp_price_confirms_and_moves_on(mock_message):
    from handlers import merchant as merchant_mod
    from handlers.merchant import handle_binding_text_input
    from unittest.mock import AsyncMock as _AsyncMock

    mock_message.answer = _AsyncMock()

    state = AsyncMock(spec=FSMContext)
    state.get_state.return_value = MerchantStates.entering_pp_price
    state.get_data.return_value = {"user_choices": {}}

    import types as _types
    merchant_mod.merchant_handler = _types.SimpleNamespace(
        flow_state_name="merchant_binding_flow",
        _update_merchant_draft=_AsyncMock(return_value=True),
        binding_flow_manager=None,
    )

    mock_message.text = "188"
    with patch("handlers.merchant.fsm_db.save_user_state", new=_AsyncMock(return_value=True)):
        await handle_binding_text_input(mock_message, state)

    text_arg = mock_message.answer.call_args.kwargs.get("text") or mock_message.answer.call_args.args[0]
    reply_markup = (
        mock_message.answer.call_args.kwargs.get("reply_markup")
        or (len(mock_message.answer.call_args.args) > 1 and mock_message.answer.call_args.args[1])
        or None
    )
    assert "已记录 PP 价格" in text_arg
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    all_cb = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert "binding_confirm_step6" in all_cb


@pytest.mark.asyncio
async def test_channel_username_confirms_and_moves_on(mock_message):
    from handlers import merchant as merchant_mod
    from handlers.merchant import handle_binding_text_input
    from unittest.mock import AsyncMock as _AsyncMock

    mock_message.answer = _AsyncMock()

    state = AsyncMock(spec=FSMContext)
    state.get_state.return_value = MerchantStates.entering_channel_username
    state.get_data.return_value = {"user_choices": {}}

    import types as _types
    merchant_mod.merchant_handler = _types.SimpleNamespace(
        flow_state_name="merchant_binding_flow",
        _update_merchant_draft=_AsyncMock(return_value=True),
        binding_flow_manager=None,
    )

    mock_message.text = "@myvalidch"
    with patch("handlers.merchant.fsm_db.save_user_state", new=_AsyncMock(return_value=True)):
        await handle_binding_text_input(mock_message, state)

    reply_markup = (
        mock_message.answer.call_args.kwargs.get("reply_markup")
        or (len(mock_message.answer.call_args.args) > 1 and mock_message.answer.call_args.args[1])
        or None
    )
    assert isinstance(reply_markup, InlineKeyboardMarkup)
    all_cb = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert "binding_confirm_step8" in all_cb


@pytest.mark.asyncio
async def test_publish_time_has_confirm_final():
    # 直接调用 BindingFlowManager.show_step，打桩 load_dynamic_options 和 safe_edit_message
    from handlers.merchant import BindingFlowManager
    from unittest.mock import AsyncMock as _AsyncMock
    import types as _types
    from handlers import merchant as merchant_mod

    bfm = BindingFlowManager(bot=None)
    # 打桩时间槽
    bfm.load_dynamic_options = _AsyncMock(return_value=[{"text": "10:00", "value": "10:00"}])

    # 捕获输出的键盘
    captured = {}
    async def _fake_edit(msg, text, reply_markup=None, parse_mode=None):
        captured["reply_markup"] = reply_markup
    merchant_mod.safe_edit_message = _AsyncMock(side_effect=_fake_edit)

    # 构造回调与已选日期/时间
    cb = _types.SimpleNamespace(message=object())
    user_choices = {"publish_date": "2025-01-01", "publish_time_str": "10:00"}

    await bfm.show_step(cb, user_choices, 9)

    km = captured.get("reply_markup")
    assert isinstance(km, InlineKeyboardMarkup)
    all_cb = [btn.callback_data for row in km.inline_keyboard for btn in row if getattr(btn, 'callback_data', None)]
    assert "binding_confirm_final" in all_cb
