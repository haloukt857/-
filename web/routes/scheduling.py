# -*- coding: utf-8 -*-
"""
时间槽管理（管理员）
允许配置固定的每日发送时间(HH:MM)，供商家上榜流程选择
"""

import logging
from fasthtml.common import *
from starlette.requests import Request
from ..layout import create_layout, require_auth
from database.db_scheduling import posting_time_slots_db
from database.db_init import db_initializer

logger = logging.getLogger(__name__)


@require_auth
async def time_slots_page(request: Request):
    try:
        params = request.query_params
        action = params.get('action')
        if request.method == 'POST':
            form = await request.form()
            time_str = (form.get('time_str') or '').strip()
            if time_str:
                await posting_time_slots_db.add_slot(time_str)
        elif action == 'toggle':
            slot_id = int(params.get('id'))
            is_active = params.get('active') == '1'
            await posting_time_slots_db.toggle_slot(slot_id, is_active)
        elif action == 'delete':
            slot_id = int(params.get('id'))
            await posting_time_slots_db.delete_slot(slot_id)

        try:
            slots = await posting_time_slots_db.get_all_slots()
        except Exception:
            # 如果表缺失（首次升级），尝试补齐并重试
            try:
                await db_initializer._ensure_auto_reply_and_keywords_tables()
                slots = await posting_time_slots_db.get_all_slots()
            except Exception as e:
                logger.error(f"时间槽表补齐失败: {e}")
                slots = []

        rows = []
        for s in slots:
            rows.append(
                Tr(
                    Td(str(s['id'])),
                    Td(s.get('time_str', '')),
                    Td('启用' if s.get('is_active') else '停用'),
                    Td(
                        Div(
                            A('启用' if not s.get('is_active') else '停用', href=f"/schedule/time-slots?action=toggle&id={s['id']}&active={'1' if not s.get('is_active') else '0'}", cls='btn btn-xs'),
                            A('删除', href=f"/schedule/time-slots?action=delete&id={s['id']}", cls='btn btn-xs btn-error ml-1', onclick="return confirm('删除该时间槽？');"),
                            cls='flex justify-end'
                        )
                    )
                )
            )

        table = Table(
            Thead(Tr(Th('ID'), Th('时间(HH:MM)'), Th('状态'), Th('操作'))),
            Tbody(*rows),
            cls='table table-zebra table-compact w-full'
        )

        form = Form(
            Div(
                Label('新增时间'),
                # 使用原生 time 选择器，避免手动输入格式错误
                Input(name='time_str', type='time', step='60', cls='input input-bordered input-sm w-40 ml-2'),
                Button('添加', type='submit', cls='btn btn-sm btn-primary ml-2'),
                cls='flex items-center'
            ),
            method='post', action='/schedule/time-slots', cls='mb-4'
        )

        content = Div(
            H1('固定发送时间配置', cls='page-title'),
            P('设置每天可用的固定发送时间（小时:分钟）。商家上榜流程将从这里读取供用户选择。', cls='text-sm text-gray-500 mb-4'),
            form,
            Div(table, cls='bg-base-100 rounded shadow p-4')
        )
        return create_layout('时间配置', content)
    except Exception as e:
        logger.error(f'时间槽页面错误: {e}')
        return create_layout('错误', Div(P('加载失败'))) 

time_slots_routes = [
    ("/schedule/time-slots", time_slots_page, ['GET', 'POST'])
]
