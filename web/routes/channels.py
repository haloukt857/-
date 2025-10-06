# -*- coding: utf-8 -*-
"""
发布频道配置页面
"""

import logging
from fasthtml.common import *
from starlette.requests import Request
from ..layout import create_layout, require_auth
from database.db_channels import posting_channels_db

logger = logging.getLogger(__name__)


@require_auth
async def channel_config_page(request: Request):
    try:
        params = request.query_params
        action = params.get('action')

        if request.method == 'POST':
            form = await request.form()
            name = (form.get('display_name') or '').strip() or '默认频道'
            raw = (form.get('channel_chat_id') or '').strip()
            role = (form.get('role') or 'post').strip() or 'post'
            chat_id = None
            link = None
            # 允许多种输入，统一归一化：
            # - @username → chat_id='@username', link=https://t.me/username
            # - https://t.me/username → 同上
            # - 数字/负号开头(-100...) → chat_id保留，不生成链接
            if raw:
                if raw.startswith('http') and '/t.me/' in raw:
                    username = raw.split('/t.me/')[-1].split('/')[0]
                    if username:
                        chat_id = f"@{username}"
                        link = f"https://t.me/{username}"
                elif raw.startswith('@'):
                    username = raw.lstrip('@')
                    chat_id = f"@{username}"
                    link = f"https://t.me/{username}"
                else:
                    # 非@/链接，按chat_id原样保存（例如-100xxx或直接username）
                    chat_id = raw if raw.startswith('-') else f"@{raw}"
                    if chat_id.startswith('@'):
                        link = f"https://t.me/{chat_id.lstrip('@')}"
            await posting_channels_db.add_channel(name, chat_id, link, is_active=True, role=role)
        elif action == 'activate':
            cid = int(params.get('id'))
            await posting_channels_db.set_active_channel_for_role(cid)
        elif action == 'delete':
            cid = int(params.get('id'))
            await posting_channels_db.delete_channel(cid)

        channels = await posting_channels_db.get_all_channels()
        rows = []
        for c in channels:
            rows.append(
                Tr(
                    Td(str(c['id'])),
                    Td(c.get('display_name', '') or '-'),
                    Td(c.get('channel_chat_id', '') or '-'),
                    Td(A(c.get('channel_link') or '-', href=c.get('channel_link') or '#', cls='link', **({} if c.get('channel_link') else {"onclick": "return false;"}))),
                    Td(c.get('role','post')),
                    Td('启用' if c.get('is_active') else '停用'),
                    Td(
                        Div(
                            A('设为当前', href=f"/channels/config?action=activate&id={c['id']}", cls='btn btn-xs'),
                            A('删除', href=f"/channels/config?action=delete&id={c['id']}", cls='btn btn-xs btn-error ml-1', onclick="return confirm('删除该频道？');"),
                            cls='flex justify-end'
                        )
                    )
                )
            )

        table = Table(
            Thead(Tr(Th('ID'), Th('显示名'), Th('@用户名/ID'), Th('链接'), Th('用途'), Th('状态'), Th('操作'))),
            Tbody(*rows),
            cls='table table-zebra table-compact w-full'
        )

        form = Form(
            Div(
                Div(Label('显示名'), Input(name='display_name', placeholder='如：主发布频道', cls='input input-bordered input-sm w-60 ml-2'), cls='form-control'),
                Div(Label('频道 @用户名/ID'), Input(name='channel_chat_id', placeholder='@channel 或 -100xxx', cls='input input-bordered input-sm w-60 ml-2'), cls='form-control'),
                Div(Label('用途'), Select(
                    Option('贴文发布', value='post'),
                    Option('用户→商户评价 (u2m)', value='review_u2m'),
                    Option('商户→用户评价 (m2u)', value='review_m2u'),
                    name='role', cls='select select-bordered select-sm w-60 ml-2'
                ), cls='form-control'),
                Div(Button('新增并设为当前', type='submit', cls='btn btn-sm btn-primary'), cls='form-control'),
                cls='flex items-end gap-3 flex-wrap'
            ),
            method='post', action='/channels/config', cls='mb-4'
        )

        content = Div(
            H1('频道配置', cls='page-title'),
            P('可配置多用途频道：贴文发布、u2m评价、m2u评价；同一用途仅一个“当前频道”。', cls='text-sm text-gray-500 mb-4'),
            form,
            Div(table, cls='bg-base-100 rounded shadow p-4')
        )
        return create_layout('频道配置', content)
    except Exception as e:
        logger.error(f'频道配置页面错误: {e}')
        return create_layout('错误', Div(P('加载失败'))) 

channels_routes = [
    ("/channels/config", channel_config_page, ['GET', 'POST'])
]
