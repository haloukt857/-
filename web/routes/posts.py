# -*- coding: utf-8 -*-
"""
帖子管理路由模块
处理商户帖子生命周期管理和发布功能
"""

import logging
from datetime import datetime, timedelta
from fasthtml.common import *
from config import DEEPLINK_BOT_USERNAME
from starlette.requests import Request
from starlette.responses import RedirectResponse

# 导入布局和认证组件
from ..layout import create_layout, require_auth
from ..services.post_mgmt_service import PostMgmtService
from ..services.merchant_mgmt_service import MerchantMgmtService
from database.db_connection import db_manager
from database.db_fsm import create_fsm_db_manager
from database.db_merchants import merchant_manager
from database.db_media import media_db
from utils.caption_renderer import render_channel_caption_md, render_channel_caption_html
from starlette.responses import HTMLResponse

logger = logging.getLogger(__name__)

# 时间格式化工具：统一展示/输入
def _fmt_dt_display(value) -> str:
    try:
        if not value:
            return '未设置'
        if isinstance(value, str):
            s = value.strip().replace('T', ' ')
            if '.' in s:
                s = s.split('.', 1)[0]
            return s[:16] if len(s) >= 16 else s
        # datetime
        from datetime import datetime as _dt
        if isinstance(value, _dt):
            return value.strftime('%Y-%m-%d %H:%M')
        return str(value)
    except Exception:
        return '未设置'

def _fmt_dt_input(value) -> str:
    """转为 datetime-local 需要的 YYYY-MM-DDTHH:MM。"""
    try:
        if not value:
            return ''
        if isinstance(value, str):
            s = value.strip().replace(' ', 'T')
            if '.' in s:
                s = s.split('.', 1)[0]
            return s[:16]
        from datetime import datetime as _dt
        if isinstance(value, _dt):
            return value.strftime('%Y-%m-%dT%H:%M')
        return ''
    except Exception:
        return ''

# 帖子状态显示映射
POST_STATUS_DISPLAY_MAP = {
    'pending_submission': "待提交",
    'pending_approval': "待审核", 
    'approved': "已审核",
    'published': "已发布",
    'expired': "已过期"
}

def get_posts_status_color(status: str) -> str:
    """根据帖子状态返回对应的颜色样式"""
    color_map = {
        'pending_submission': "badge-warning",
        'pending_approval': "badge-warning", 
        'approved': "badge-info",
        'published': "badge-success",
        'expired': "badge-error"
    }
    return color_map.get(status, "badge-ghost")


@require_auth
async def post_caption_preview(request: Request, post_id: int):
    """Caption 预览（上方文字纯服务端 HTML，保留媒体区逻辑在外层页面）。"""
    try:
        # 使用最直接的数据源，避免服务层改动带来的不确定性
        post = await merchant_manager.get_merchant_by_id(post_id)
        if not post:
            return HTMLResponse('<div style="padding:8px;color:#f00;">预览失败：帖子不存在</div>', status_code=404)
        caption_styled = await render_channel_caption_md(post, (DEEPLINK_BOT_USERNAME or '').lstrip('@'))
        html_caption = await render_channel_caption_html(post, (DEEPLINK_BOT_USERNAME or '').lstrip('@'))
        html = f"""
<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  
  
  <style>
    /* 深色背景，避免白色大块区域 */
    body {{ margin: 0; background: #1f1f1f; color: #e6e6e6; }}
    .wrap {{ max-width: 720px; margin: 0 auto; padding: 16px; font: 14px/1.6 -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; color: inherit; background: transparent; }}
    .tg-adv {{ margin: 0 0 8px; padding: 8px 12px; border-left: 3px solid #3a3a3a; background: #2a2a2a; }}
    .line {{ margin: 4px 0; }}
    .caption {{ white-space: pre-wrap; }}
    a {{ color: #7cb1ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
  <title>Caption Preview</title>
</head>
<body>
  <section id="caption-preview" class="wrap">
    {html_caption}
  </section>
</body>
</html>
"""
        return html
    except Exception as e:
        logger.error(f"caption预览失败: {e}")
        return '<div style="padding:8px;color:#f00;">预览失败</div>'

def generate_posts_quick_action_buttons(post_id: str, current_status: str) -> list:
    """根据当前状态生成快速操作按钮"""
    buttons = []
    
    if current_status == 'pending_approval':
        buttons.extend([
            Form(
                Button("立即批准", type="submit", cls="btn btn-success btn-xs"),
                method="post", action=f"/posts/{post_id}/approve"
            ),
            Form(
                Button("驳回修改", type="submit", cls="btn btn-warning btn-xs"),
                method="post", action=f"/posts/{post_id}/reject"
            )
        ])
    
    elif current_status == 'approved':
        buttons.extend([
            Form(
                Button("立即发布", type="submit", cls="btn btn-info btn-xs"),
                method="post", action=f"/posts/{post_id}/publish"
            ),
            Form(
                Button("延长1天", type="submit", cls="btn btn-ghost btn-xs"),
                Input(type="hidden", name="days", value="1"),
                method="post", action=f"/posts/{post_id}/extend"
            )
        ])
    
    elif current_status == 'published':
        buttons.extend([
            Form(
                Button("设为过期", type="submit", cls="btn btn-warning btn-xs"),
                method="post", action=f"/posts/{post_id}/expire"
            ),
            Form(
                Button("延长1天", type="submit", cls="btn btn-ghost btn-xs"),
                Input(type="hidden", name="days", value="1"),
                method="post", action=f"/posts/{post_id}/extend"
            )
        ])
    
    return buttons


@require_auth
async def posts_list(request: Request):
    """帖子管理页面"""
    try:
        # 解析查询参数
        params = dict(request.query_params)
        page = int(params.get('page', 1))
        per_page = int(params.get('per_page', 20))
        
        # 筛选参数
        status_filter = params.get('status', '')
        district_filter = params.get('district', '')
        search_query = params.get('search', '')
        sort_by = params.get('sort', 'publish_time')
        kw_id = int(params.get('kw')) if params.get('kw') else None
        price_p = int(params.get('price_p')) if params.get('price_p') else None
        price_pp = int(params.get('price_pp')) if params.get('price_pp') else None
        
        # 调用服务层获取帖子数据，传递完整参数
        posts_data = await PostMgmtService.get_posts_list(
            status_filter=status_filter if status_filter else None,
            region_filter=district_filter if district_filter else None,
            search_query=search_query if search_query else None,
            page=page,
            per_page=per_page,
            kw_id=kw_id,
            price_p=price_p,
            price_pp=price_pp,
            sort_by=sort_by
        )
        
        posts = posts_data["posts"]
        stats = posts_data["statistics"]
        pagination = posts_data["pagination"]
        regions = posts_data.get("regions", [])
        
        # 构建筛选表单（与商户管理风格一致：一行四项+按钮对齐）
        filter_form = Form(
            Div(
                # 状态筛选（使用服务层提供的映射，避免前后端不一致）
                Div(
                    Label("状态筛选:", cls="label"),
                    Select(
                        Option("全部状态", value="", selected=not status_filter),
                        *[Option(posts_data.get('status_options', {}).get(k, k), value=k, selected=(status_filter==k)) for k in posts_data.get('status_options', {}).keys()],
                        name="status", cls="select select-bordered w-full"
                    ),
                    cls="form-control min-w-[200px]"
                ),
                # 区县筛选
                Div(
                    Label("区县筛选:", cls="label"),
                    Select(
                        Option("全部地区", value="", selected=not district_filter),
                        *[Option(f"{region.get('city_name', '')} - {region.get('name', '')}", 
                               value=str(region['id']),
                               selected=district_filter==str(region['id'])) 
                          for region in regions],
                        name="district", cls="select select-bordered w-full"
                    ),
                    cls="form-control min-w-[240px]"
                ),
                # 搜索框
                Div(
                    Label("搜索:", cls="label"),
                    Input(type="text", name="search", value=search_query,
                          placeholder="搜索商户名称或用户名", cls="input input-bordered w-full"),
                    cls="form-control flex-1"
                ),
                # 排序选择
                Div(
                    Label("排序:", cls="label"),
                    Select(
                        Option("创建时间", value="created_at", selected=sort_by=="created_at"),
                        Option("更新时间", value="updated_at", selected=sort_by=="updated_at"),
                        Option("发布时间", value="publish_time", selected=sort_by=="publish_time"),
                        name="sort", cls="select select-bordered w-full"
                    ),
                    cls="form-control min-w-[180px]"
                ),
                # 按钮
                Div(
                    Div(
                        Button("搜索", type="submit", cls="btn btn-primary"),
                        A("重置", href="/posts", cls="btn btn-ghost ml-2"),
                        cls="flex gap-2"
                    ),
                    cls="form-control md:self-end"
                ),
                cls="flex flex-col md:flex-row md:items-end gap-4"
            ),
            method="get",
            cls="card bg-base-100 shadow-xl p-6 mb-6"
        )
        
        # 构建帖子表格
        posts_table = Table(
            Thead(
                Tr(
                    Th("ID", cls="px-2 py-1 text-xs"),
                    Th("商户名称", cls="whitespace-nowrap px-2 py-1 text-xs"),
                    Th("状态", cls="whitespace-nowrap px-2 py-1 text-xs"),
                    Th("地区", cls="whitespace-nowrap px-2 py-1 text-xs"),
                    Th("频道用户名", cls="whitespace-nowrap px-2 py-1 text-xs"),
                    Th("频道链接", cls="whitespace-nowrap px-2 py-1 text-xs"),
                    Th("发布时间", cls="whitespace-nowrap px-2 py-1 text-xs"),
                    Th("到期时间", cls="whitespace-nowrap px-2 py-1 text-xs"),
                    Th("创建时间", cls="whitespace-nowrap px-2 py-1 text-xs"),
                    Th("操作", cls="whitespace-nowrap px-2 py-1 text-xs text-right")
                )
            ),
            Tbody(
                *[
                    Tr(
                        Td(str(post['id']), cls="whitespace-nowrap text-sm"),
                        Td(post.get('name', '未设置'), cls="whitespace-nowrap text-sm"),
                        Td(
                            Span(
                                POST_STATUS_DISPLAY_MAP.get(post['status'], post['status']),
                                cls=f"badge badge-sm {get_posts_status_color(post['status'])}"
                            )
                        ),
                        Td(f"{post.get('city_name', '')} - {post.get('district_name', '')}", cls="whitespace-nowrap text-xs px-2 py-1"),
                        Td((post.get('channel_chat_id') or '-') if isinstance(post.get('channel_chat_id'), str) else '-', cls="whitespace-nowrap font-mono text-xs px-2 py-1"),
                        Td(
                            Div(
                                A(post.get('channel_link') or '-', href=post.get('channel_link') or '#', 
                                  cls='link truncate inline-block max-w-xs',
                                  **({} if post.get('channel_link') else {"onclick": "return false;"})),
                                cls="whitespace-nowrap"
                            )
                        ),
                        Td(post.get('publish_time', '未设置'), cls="whitespace-nowrap text-xs px-2 py-1"),
                        Td(_fmt_dt_display(post.get('expiration_time')), cls="whitespace-nowrap text-xs px-2 py-1"),
                        Td(post.get('created_at', ''), cls="whitespace-nowrap text-xs px-2 py-1"),
                        Td(
                            Div(
                                A("详情", href=f"/posts/{post['id']}", 
                                  cls="btn btn-sm btn-info mr-1"),
                                *generate_posts_quick_action_buttons(
                                    str(post['id']), post['status']
                                ),
                                cls="flex gap-1 flex-nowrap justify-end"
                            )
                        )
                    )
                    for post in posts
                ]
            ),
            cls="table table-zebra w-full"
        )
        
        # 分页组件
        total_pages = (pagination.get('total', 0) + per_page - 1) // per_page
        pagination_component = Div(
            Div(f"共 {pagination.get('total', 0)} 条记录", cls="text-sm text-gray-500"),
            Div(
                *[
                    A(
                        str(p),
                        href=f"/posts?page={p}&per_page={per_page}&status={status_filter}&district={district_filter}&search={search_query}&sort={sort_by}",
                        cls=f"btn btn-sm {'btn-active' if p == page else 'btn-ghost'}"
                    )
                    for p in range(max(1, page-2), min(total_pages+1, page+3))
                ],
                cls="btn-group"
            ),
            cls="flex justify-between items-center mt-4"
        ) if total_pages > 1 else Div()
        
        content = Div(
            # 页面头部
            Div(
                H1("帖子管理", cls="page-title"),
                Div(
                    P("管理商户帖子的生命周期和发布状态", cls="page-subtitle flex-1"),
                    Div(
                        A("时间配置", href="/schedule/time-slots", cls="btn btn-ghost btn-xs mr-2"),
                        A("+ 新建帖子", href="/posts/new", cls="btn btn-primary btn-sm"),
                        cls="flex items-center"
                    ),
                    cls="flex items-center justify-between"
                ),
                cls="page-header"
            ),
            
            # 统计卡片
            Div(
                Div(
                    Div("帖子总数", cls="stat-title"),
                    Div(str(stats.get("total_posts", 0)), cls="stat-value text-primary"),
                    cls="stat"
                ),
                Div(
                    Div("待审核", cls="stat-title"),
                    Div(str(stats.get("pending_approval", 0)), cls="stat-value text-warning"),
                    cls="stat"
                ),
                Div(
                    Div("已发布", cls="stat-title"),
                    Div(str(stats.get("published", 0)), cls="stat-value text-success"),
                    cls="stat"
                ),
                Div(
                    Div("当前筛选", cls="stat-title"),
                    Div(str(len(posts)), cls="stat-value text-info"),
                    cls="stat"
                ),
                cls="stats shadow mb-6"
            ),
            
            # 筛选表单
            Div(filter_form, cls="bg-base-100 p-4 rounded-lg shadow mb-6"),
            
            # 帖子表格
            Div(posts_table, cls="overflow-x-auto"),
            
            # 分页
            pagination_component,
            
            cls="page-content"
        )
        
        return create_layout("帖子管理", content)
        
    except Exception as e:
        logger.error(f"帖子管理页面错误: {e}")
        error_content = Div(
            H1("帖子管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"错误信息: {str(e)}", cls="text-gray-600")
        )
        return create_layout("系统错误", error_content)


@require_auth
async def post_detail(request: Request, post_id: int):
    """帖子详情和编辑页面"""
    try:
        # 获取帖子详情
        post_data = await PostMgmtService.get_post_detail(post_id)
        if not post_data.get('success', False):
            raise ValueError("帖子不存在")
        
        post = post_data['post']
        media_files = post_data.get('media_files', [])

        # 若名称为“待完善”或空，自动刷新Telegram用户信息并回填写库，然后重新获取
        try:
            nm = str(post.get('name') or '').strip()
            if nm == '' or nm == '待完善':
                await MerchantMgmtService.refresh_telegram_user_info(post_id)
                # 重新读取以展示最新写库结果
                post_data = await PostMgmtService.get_post_detail(post_id)
                post = post_data['post']
        except Exception as _auto_e:
            logger.debug(f"自动刷新用户信息失败: {_auto_e}")

        # 严格以数据库为唯一信息源，不做任何FSM兜底补齐。
        
        # 单独获取地区列表用于筛选表单（列表页使用）
        from ..services.region_mgmt_service import RegionMgmtService
        regions_data = await RegionMgmtService.get_regions_list()
        regions = regions_data.get('regions', [])

        # 城市/区县双下拉所需数据（编辑页使用）
        selected_city_id = post.get('city_id')
        if not selected_city_id and post.get('district_id'):
            try:
                d = await region_manager.get_district_by_id(post['district_id'])
                selected_city_id = d.get('city_id') if d else None
            except Exception:
                selected_city_id = None
        # 优先使用服务层提供的聚合数据，避免因数据库返回类型差异导致空列表
        cities = regions_data.get('active_cities') or regions_data.get('cities', [])
        if selected_city_id:
            try:
                all_districts = regions_data.get('districts', [])
                city_districts = [d for d in all_districts if d.get('city_id') == selected_city_id]
            except Exception:
                city_districts = []
        else:
            city_districts = []
        
        # 视图/编辑模式切换（默认预览）
        mode = request.query_params.get('mode', 'view')

        if mode != 'edit':
            # 预览模式：只读信息 + 编辑/返回按钮
            status_badge = Span(
                POST_STATUS_DISPLAY_MAP.get(post.get('status'), post.get('status')),
                cls=f"badge {get_posts_status_color(post.get('status'))}"
            )

            # 计算频道用户名与链接
            ch_username = post.get('channel_chat_id') if isinstance(post.get('channel_chat_id'), str) else '-'
            ch_link = post.get('channel_link') if isinstance(post.get('channel_link'), str) and post.get('channel_link') else None

            # 解析 Telegram 用户名
            tg_username = '-'
            try:
                import json as _json
                ui = post.get('user_info')
                if isinstance(ui, str) and ui:
                    ui = _json.loads(ui)
                if isinstance(ui, dict):
                    u = ui.get('username')
                    if not u and isinstance(ui.get('raw_info'), dict):
                        u = ui['raw_info'].get('username')
                    if u:
                        tg_username = f"@{u}"
            except Exception:
                pass

            # 不做任何基于联系方式的推断，完全以DB的 user_info 字段为准。

            # 左：关键信息；右：补充信息
            left_block = Div(
                H3("基本信息", cls="text-lg font-semibold mb-4"),
                Ul(
                    Li(Strong("名称："), Span(post.get('name', '未设置'))),
                    Li(Strong("商户类型："), Span(post.get('merchant_type', '-') or '-')),
                    Li(Strong("地区："), Span(f"{post.get('city_name','')} - {post.get('district_name','')}")),
                    Li(Strong("价格："), Span(f"P {post.get('p_price','-')} | PP {post.get('pp_price','-')}")),
                    Li(Strong("状态："), status_badge),
                    cls="space-y-2"
                ),
                cls="card bg-base-100 shadow p-6"
            )

            # 生成商家deeplink（统一规范：start=merchant_{id}）
            deeplink = f"https://t.me/{DEEPLINK_BOT_USERNAME}?start=merchant_{post_id}"
            dl_input_id = f"deeplink_{post_id}"
            dl_btn_id = f"btn_copy_dl_{post_id}"

            right_block = Div(
                H3("发布与联系", cls="text-lg font-semibold mb-4"),
                Ul(
                    Li(Strong("频道用户名："), Span(ch_username or '-')),
                    Li(Strong("频道链接："), A(ch_link or '-', href=ch_link or '#', cls="link", **({} if ch_link else {"onclick": "return false;"}))),
                    Li(Strong("Telegram 用户名："), Span(tg_username)),
                    Li(Strong("联系方式："), Span(post.get('contact_info', '-') or '-')),
                    Li(Strong("优势一句话："), Span(post.get('adv_sentence', '-') or '-')),
                    Li(
                        Strong("深度链接："),
                        Input(value=f"https://t.me/{DEEPLINK_BOT_USERNAME}?start=m_{post_id}", readonly=True, id=dl_input_id, cls="input input-bordered w-full mt-2"),
                        Button("复制", type="button", id=dl_btn_id, cls="btn btn-ghost btn-xs mt-2"),
                    ),
                    Li(Strong("发布时间："), Span(_fmt_dt_display(post.get('publish_time')))),
                    Li(Strong("到期时间："), Span(_fmt_dt_display(post.get('expiration_time')))),
                    cls="space-y-2"
                ),
                cls="card bg-base-100 shadow p-6"
            )

            # 统一以频道贴文 HTML 片段作为预览（iframe），长度从 MD 渲染获取；若长度计算失败也不中断预览
            preview_iframe = Iframe(src=f"/posts/{post_id}/caption-preview", cls="w-full h-48 bg-base-200 rounded")
            try:
                from utils.caption_renderer import render_channel_caption_md as _rcm
                bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
                caption_preview_md = await _rcm(post, bot_u)
                caption_len = len((caption_preview_md or '').strip())
            except Exception:
                caption_len = None
            preview_block = Div(
                H3("发布文本预览 (caption)", cls="text-lg font-semibold mb-4"),
                preview_iframe,
                P(f"长度: {caption_len if caption_len is not None else '—'} / 1024", cls="text-xs text-gray-500 mt-1"),
                cls="card bg-base-100 shadow p-6 mb-6"
            )

            # 服务描述块
            desc_block = Div(
                H3("服务描述", cls="text-lg font-semibold mb-4"),
                Pre(post.get('custom_description', '-') or '-', cls="whitespace-pre-wrap"),
                cls="card bg-base-100 shadow p-6 mb-6"
            )

            # 媒体预览区（最多展示6个）并支持拖拽排序
            media_section = None
            try:
                if media_files:
                    tiles = []
                    for m in media_files[:6]:
                        mid = m.get('id')
                        mtype = m.get('media_type')
                        thumb = Img(src=f"/media-proxy/{mid}", cls="w-full h-40 object-cover rounded") if mtype=='photo' else Div(A("预览视频", href=f"/media-proxy/{mid}", cls="link"))
                        tiles.append(
                            Div(
                                Div(thumb, cls=""),
                                P(f"#{mid} · {mtype}", cls="text-xs text-gray-500 mt-1"),
                                cls="draggable shadow rounded p-1 bg-base-200",
                                id=f"m_{mid}",
                                draggable="true",
                                **{"data-id": str(mid)}
                            )
                        )
                    media_section = Div(
                        H3("媒体预览与排序", cls="text-lg font-semibold mb-4"),
                        Div(*tiles, id="media-grid", cls="grid grid-cols-2 md:grid-cols-3 gap-3"),
                        Div(
                            Button("保存顺序", id="save-order", cls="btn btn-primary btn-sm mt-3"),
                            P("拖动卡片改变顺序，发布时按此顺序发送（行优先：1-2-3 / 4-5-6）", cls="text-xs text-gray-400 mt-2"),
                            cls=""
                        ),
                        Script(f'''
                        (function(){{
                          var grid=document.getElementById('media-grid');
                          var dragEl=null;
                          grid.addEventListener('dragstart',function(e){{
                            dragEl=e.target.closest('.draggable');
                            e.dataTransfer.effectAllowed='move';
                          }});
                          grid.addEventListener('dragover',function(e){{
                            e.preventDefault();
                            var target=e.target.closest('.draggable');
                            if(!dragEl||!target||dragEl===target) return;
                            var rect=target.getBoundingClientRect();
                            var before=(e.clientY-rect.top)/(rect.bottom-rect.top)<0.5;
                            grid.insertBefore(dragEl, before?target:target.nextSibling);
                          }});
                          document.getElementById('save-order').addEventListener('click', function(){{
                            var ids=[].map.call(grid.querySelectorAll('.draggable'),function(el){{return el.dataset.id;}}).join(',');
                            fetch('/posts/{post_id}/media-order',{{method:'POST', headers:{{'Content-Type':'application/x-www-form-urlencoded'}}, body:'order='+encodeURIComponent(ids)}})
                              .then(r=>r.ok?alert('已保存顺序'):alert('保存失败'));
                          }});
                        }})();
                        '''),
                        cls="card bg-base-100 shadow p-6"
                    )
            except Exception:
                media_section = None

            preview = Div(
                Div(
                    left_block,
                    right_block,
                    cls="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6"
                ),
                preview_block,
                desc_block,
                media_section or Div(),
                cls=""
            )

            # 复制脚本
            copy_script = Script(
                f'''
                (function(){{
                  var input = document.getElementById('{dl_input_id}');
                  var btn = document.getElementById('{dl_btn_id}');
                  if(btn && input){{
                    btn.addEventListener('click', function(){{
                      try{{
                        navigator.clipboard.writeText(input.value).then(function(){{
                          btn.textContent = '已复制';
                          setTimeout(function(){{ btn.textContent = '复制'; }}, 1200);
                        }});
                      }}catch(e){{
                        input.select(); document.execCommand('copy');
                        btn.textContent = '已复制';
                        setTimeout(function(){{ btn.textContent = '复制'; }}, 1200);
                      }}
                    }});
                  }}
                }})();
                '''
            )

            actions = Div(
                A("编辑", href=f"/posts/{post_id}?mode=edit", cls="btn btn-primary"),
                A("返回列表", href="/posts", cls="btn btn-ghost ml-2"),
                cls="flex justify-end gap-2"
            )

            content = Div(
                Div(
                    H1(f"帖子详情 - {post.get('name', '未知')}", cls="page-title"),
                    P(f"ID: {post_id} | 创建时间: {post.get('created_at', '')}", cls="page-subtitle"),
                    cls="page-header"
                ),
                preview,
                copy_script,
                actions,
                cls="page-content"
            )
            return create_layout("帖子详情", content)

        # 生成“caption 预览”和“媒体数量”
        media_files = await media_db.get_media_by_merchant_id(post_id)
        media_count = len(media_files or [])
        from html import escape as _escape
        # deeplink生成参数
        bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
        link_merchant = f"https://t.me/{bot_u}?start=m_{post_id}" if bot_u else ''
        link_district = f"https://t.me/{bot_u}?start=d_{post.get('district_id')}" if bot_u and post.get('district_id') else ''
        link_price_p = f"https://t.me/{bot_u}?start=price_p_{post.get('p_price') or ''}" if bot_u and post.get('p_price') else ''
        link_price_pp = f"https://t.me/{bot_u}?start=price_pp_{post.get('pp_price') or ''}" if bot_u and post.get('pp_price') else ''
        link_report = f"https://t.me/{bot_u}?start=report_{post_id}" if bot_u else ''
        # 标签最多3个（直接查表）
        tags_html = ''
        try:
            rows = await db_manager.fetch_all(
                "SELECT k.id, k.name FROM keywords k JOIN merchant_keywords mk ON mk.keyword_id = k.id WHERE mk.merchant_id = ? ORDER BY k.display_order ASC, k.id ASC LIMIT 3",
                (post_id,)
            )
            parts = []
            for r in rows or []:
                kid = r['id']; nm = r['name']
                if bot_u and kid:
                    parts.append(f"<a href=\"https://t.me/{bot_u}?start=kw_{kid}\">#{_escape(nm)}</a>")
                else:
                    parts.append(_escape(f"#{nm}"))
            tags_html = ' '.join(parts)
        except Exception:
            tags_html = ''
        # 生成文本（唯一模板）
        args_v2 = {
            'nickname_html': f"<a href=\"{_escape(link_merchant)}\">{_escape(post.get('name') or '-')}</a>" if link_merchant else _escape(post.get('name') or '-'),
            'district_html': f"<a href=\"{_escape(link_district)}\">{_escape(post.get('district_name') or '-')}</a>" if link_district else _escape(post.get('district_name') or '-'),
            'p_price': _escape(str(post.get('p_price') or '')),
            'pp_price': _escape(str(post.get('pp_price') or '')),
            'price_p_html': (f"<a href=\"{_escape(link_price_p)}\">{_escape(str(post.get('p_price') or ''))}/p</a>" if link_price_p else f"{_escape(str(post.get('p_price') or ''))}/p"),
            'price_pp_html': (f"<a href=\"{_escape(link_price_pp)}\">{_escape(str(post.get('pp_price') or ''))}/pp</a>" if link_price_pp else f"{_escape(str(post.get('pp_price') or ''))}/pp"),
            'tags_html': tags_html,
            'report_html': f"<a href=\"{_escape(link_report)}\">报告</a>" if link_report else '报告',
            'offer_html': '-',
            'adv_html': _escape((post.get('adv_sentence') or '').strip())
        }
        # 兼容旧模板字段：price_links_html
        try:
            args_v2['price_links_html'] = (
                (f"<a href=\"{_escape(link_price_p)}\">P</a>" if link_price_p else "P") + ' / ' +
                (f"<a href=\"{_escape(link_price_pp)}\">PP</a>" if link_price_pp else "PP")
            )
        except Exception:
            pass
        # 使用统一MarkdownV2渲染器
        bot_u = (DEEPLINK_BOT_USERNAME or '').lstrip('@')
        caption_preview = await render_channel_caption_md(post, bot_u)
        caption_len = len(caption_preview or '')

        # 构建编辑表单（字段与 merchants 表保持一致）
        edit_form = Form(
            Div(
                # 预览信息
                Div(
                    H3("媒体与文本预览", cls="text-lg font-semibold mb-4"),
                    Div(
                        P(f"媒体数量：{media_count}/6（最多6张，发布取前6张）", cls="mb-2"),
                        P(f"caption 长度：{caption_len}/1024", cls="text-sm text-gray-500 mb-2"),
                        Pre(caption_preview or '-', cls="whitespace-pre-wrap bg-base-200 p-3 rounded"),
                        cls="form-control"
                    ),
                    cls="mb-6"
                ),
                # 基本信息
                Div(
                    H3("基本信息", cls="text-lg font-semibold mb-4"),
                    Div(
                        Div(
                            Label("商户名称", cls="label"),
                            Input(name="name", value=post.get('name', ''), 
                                 cls="input input-bordered w-full"),
                            cls="form-control"
                        ),
                        Div(
                            Label("联系方式", cls="label"),
                            Input(name="contact_info", value=post.get('contact_info', ''), 
                                 cls="input input-bordered w-full"),
                            cls="form-control"
                        ),
                        Div(
                            Label("发布频道 chat_id/用户名", cls="label"),
                            Input(name="channel_chat_id", value=post.get('channel_chat_id', '') or '', 
                                 cls="input input-bordered w-full", placeholder="例如 -100xxx 或 @channel"),
                            cls="form-control"
                        ),
                        Div(
                            Label("频道链接 (https://t.me/…)", cls="label"),
                            Input(name="channel_link", value=post.get('channel_link', '') or '', 
                                 cls="input input-bordered w-full", placeholder="例如 https://t.me/yourchannel"),
                            cls="form-control"
                        ),
                        Div(
                            Label("商家deeplink", cls="label"),
                            Div(
                                Input(value=f"https://t.me/{DEEPLINK_BOT_USERNAME}?start=m_{post_id}", readonly=True, id=f"edit_dl_{post_id}", cls="input input-bordered w-full"),
                                Button("复制", type="button", id=f"btn_edit_dl_{post_id}", cls="btn btn-ghost btn-xs ml-2"),
                                cls="flex items-center"
                            ),
                            cls="form-control"
                        ),
                        cls="grid grid-cols-1 md:grid-cols-2 gap-4"
                    ),
                    cls="mb-6"
                ),
                
                # 服务信息
                Div(
                    H3("服务信息", cls="text-lg font-semibold mb-4"),
                    Div(
                        Label("服务描述", cls="label"),
                        Textarea(
                            post.get('custom_description', ''),
                            name="custom_description",
                            placeholder="请输入服务描述",
                            cls="textarea textarea-bordered w-full h-32"
                        ),
                        cls="form-control mb-4"
                    ),
                    Div(
                        Label("优势（≤30字，必填）", cls="label"),
                        Input(name="adv_sentence", value=post.get('adv_sentence','') or '', maxlength="30", cls="input input-bordered w-full", required=True),
                        cls="form-control mb-4"
                    ),
                    Div(
                        Div(
                            Label("价格1 (P)", cls="label"),
                            Input(name="p_price", value=str(post.get('p_price', '') or ''), 
                                 type="number", cls="input input-bordered w-full"),
                            cls="form-control"
                        ),
                        Div(
                            Label("价格2 (PP)", cls="label"),
                            Input(name="pp_price", value=str(post.get('pp_price', '') or ''), 
                                 type="number", cls="input input-bordered w-full"),
                            cls="form-control"
                        ),
                        cls="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4"
                    ),
                    Div(
                        Div(
                            Label("城市", cls="label"),
                            Select(
                                Option("请选择城市", value="", selected=(not selected_city_id), disabled=(len(cities)>0)),
                                *[Option(c.get('name',''), value=str(c['id']), selected=(selected_city_id==c['id'])) for c in cities],
                                name="city_id", id="city_select", cls="select select-bordered w-full"
                            ),
                            cls="form-control"
                        ),
                        Div(
                            Label("地区", cls="label"),
                            Select(
                                Option("请选择地区", value="", selected=(not post.get('district_id')), disabled=(len(city_districts)>0)),
                                *[Option(d.get('name',''), value=str(d['id']), selected=(post.get('district_id')==d['id'])) for d in city_districts],
                                name="district_id", id="district_select", cls="select select-bordered w-full"
                            ),
                            cls="form-control"
                        ),
                        cls="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4"
                    ),
                    cls="mb-6"
                ),
                
                # 状态管理
                Div(
                    H3("状态管理", cls="text-lg font-semibold mb-4"),
                    Div(
                        Div(
                            Label("当前状态", cls="label"),
                            Span(
                                POST_STATUS_DISPLAY_MAP.get(post['status'], post['status']),
                                cls=f"badge {get_posts_status_color(post['status'])} badge-lg"
                            ),
                            cls="form-control"
                        ),
                        Div(
                            Label("发布时间", cls="label"),
                            Input(
                                name="publish_time",
                                value=_fmt_dt_input(post.get('publish_time')),
                                type="datetime-local", cls="input input-bordered w-full"
                            ),
                            cls="form-control"
                        ),
                        Div(
                            Label("到期时间", cls="label"),
                            Input(
                                name="expiration_time",
                                value=_fmt_dt_input(post.get('expiration_time')),
                                type="datetime-local", cls="input input-bordered w-full"
                            ),
                            cls="form-control"
                        ),
                        cls="grid grid-cols-1 md:grid-cols-3 gap-4"
                    ),
                    cls="mb-6"
                ),
                
                cls="space-y-6"
            ),
            
            # 操作按钮
            Div(
                Button("保存修改", type="submit", cls="btn btn-primary"),
                Form(
                    Button("删除帖子", type="submit", cls="btn btn-error ml-2",
                           onclick="return confirm('确定删除该帖子？此操作不可恢复');"),
                    method="post", action=f"/posts/{post_id}/delete"
                ),
                A("返回列表", href="/posts", cls="btn btn-ghost ml-2"),
                cls="flex justify-end gap-2 mt-6"
            ),
            
            method="post", action=f"/posts/{post_id}/update"
        )
        
        # 编辑页复制deeplink脚本
        edit_copy_script = Script(
            f'''
            (function(){{
              var input = document.getElementById('edit_dl_{post_id}');
              var btn = document.getElementById('btn_edit_dl_{post_id}');
              if(btn && input){{
                btn.addEventListener('click', function(){{
                  try{{
                    navigator.clipboard.writeText(input.value).then(function(){{
                      btn.textContent = '已复制';
                      setTimeout(function(){{ btn.textContent = '复制'; }}, 1200);
                    }});
                  }}catch(e){{
                    input.select(); document.execCommand('copy');
                    btn.textContent = '已复制';
                    setTimeout(function(){{ btn.textContent = '复制'; }}, 1200);
                  }}
                }});
              }}
            }})();
            '''
        )

        content = Div(
            Div(
                H1(f"帖子详情 - {post.get('name', '未知')}", cls="page-title"),
                P(f"ID: {post_id} | 创建时间: {post.get('created_at', '')}", cls="page-subtitle"),
                cls="page-header"
            ),
            
            Div(edit_form, cls="card bg-base-100 shadow-xl p-6"),
            edit_copy_script,
            
            # 动态联动脚本：城市变更后刷新地区列表
            Script(
                f"""
                (function(){{
                  try{{
                    var districts = {__import__('json').dumps(regions_data.get('districts', []), ensure_ascii=False)};
                    var citySel = document.getElementById('city_select');
                    var distSel = document.getElementById('district_select');
                    function refreshDistricts(cityId){{
                      if(!distSel) return;
                      distSel.innerHTML = '';
                      var opt0 = document.createElement('option');
                      opt0.value=''; opt0.text='请选择地区';
                      distSel.appendChild(opt0);
                      if(!cityId) return;
                      var list = districts.filter(function(d){{return String(d.city_id)===String(cityId);}});
                      list.forEach(function(d){{
                        var o = document.createElement('option');
                        o.value = String(d.id); o.text = d.name || String(d.id);
                        distSel.appendChild(o);
                      }});
                    }}
                    if(citySel){{
                      citySel.addEventListener('change', function(){{
                        refreshDistricts(this.value);
                      }});
                    }}
                  }}catch(e){{}}
                }})();
                """
            ),
            
            cls="page-content"
        )
        
        return create_layout("帖子详情", content)
        
    except Exception as e:
        logger.error(f"获取帖子详情失败: {e}")
        error_content = Div(
            H1("获取失败", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"获取帖子详情时发生错误: {str(e)}"),
            A("返回列表", href="/posts", cls="btn btn-primary mt-4")
        )
        return create_layout("获取失败", error_content)


@require_auth
async def post_new(request: Request):
    """新建帖子页面"""
    try:
        from ..services.region_mgmt_service import RegionMgmtService
        regions_data = await RegionMgmtService.get_regions_list()
        regions = regions_data.get('regions', [])

        form = Form(
            Div(
                H3("基础信息", cls="text-lg font-semibold mb-4"),
                Div(
                    Label("Telegram 用户ID (chat_id)", cls="label"),
                    Input(name="telegram_chat_id", type="number", cls="input input-bordered w-full", required=True,
                          placeholder="请输入用户的Telegram数字ID"),
                    cls="form-control mb-4"
                ),
                Div(
                    Label("商户名称", cls="label"),
                    Input(name="name", cls="input input-bordered w-full", placeholder="可选，不填为‘待完善’"),
                    cls="form-control mb-4"
                ),
                Div(
                    Div(
                        Label("发布频道 chat_id/用户名", cls="label"),
                        Input(name="channel_chat_id", cls="input input-bordered w-full", placeholder="例如 -100xxx 或 @channel"),
                        cls="form-control"
                    ),
                    Div(
                        Label("频道链接 (https://t.me/…)", cls="label"),
                        Input(name="channel_link", cls="input input-bordered w-full", placeholder="例如 https://t.me/yourchannel"),
                        cls="form-control"
                    ),
                    cls="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4"
                ),
                Div(
                    Label("服务区域", cls="label"),
                    Select(
                        *[Option(f"{r.get('city_name','')} - {r.get('name','')}", value=str(r['id'])) for r in regions],
                        name="district_id", cls="select select-bordered w-full", required=True
                    ),
                    cls="form-control mb-4"
                ),
                Div(
                    Div(
                        Label("价格1", cls="label"),
                        Input(name="p_price", type="number", cls="input input-bordered w-full"),
                        cls="form-control"
                    ),
                    Div(
                        Label("价格2", cls="label"),
                        Input(name="pp_price", type="number", cls="input input-bordered w-full"),
                        cls="form-control"
                    ),
                    cls="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4"
                ),
                Div(
                    Label("联系方式", cls="label"),
                    Input(name="contact_info", cls="input input-bordered w-full"),
                    cls="form-control mb-4"
                ),
                Div(
                    Label("描述", cls="label"),
                    Textarea(name="custom_description", cls="textarea textarea-bordered w-full h-32"),
                    cls="form-control mb-4"
                ),
                Div(
                    Label("优势（≤30字，必填）", cls="label"),
                    Input(name="adv_sentence", maxlength="30", cls="input input-bordered w-full", required=True),
                    cls="form-control mb-4"
                ),
                cls="card bg-base-100 shadow p-6 max-w-3xl mx-auto"
            ),
            Div(
                Button("创建帖子", type="submit", cls="btn btn-primary"),
                A("返回列表", href="/posts", cls="btn btn-ghost ml-2"),
                cls="flex justify-end gap-2 mt-6"
            ),
            method="post", action="/posts/create"
        )

        content = Div(
            Div(H1("新建帖子", cls="page-title"), cls="page-header"),
            form,
            cls="page-content"
        )
        return create_layout("新建帖子", content)
    except Exception as e:
        logger.error(f"新建帖子页面错误: {e}")
        return create_layout("错误", Div(P("加载新建页面失败")))


@require_auth
async def post_create(request: Request):
    """处理新建帖子提交"""
    try:
        form = await request.form()
        telegram_chat_id = int(form.get('telegram_chat_id'))
        name = form.get('name') or '待完善'
        district_id = int(form.get('district_id'))
        p_price = form.get('p_price')
        pp_price = form.get('pp_price')
        contact_info = form.get('contact_info')
        custom_description = form.get('custom_description')
        adv_sentence = (form.get('adv_sentence') or '').strip() or None
        if not adv_sentence:
            return create_layout("创建失败", Div(P("优势不能为空"), A("返回", href="/posts/new", cls="btn btn-primary mt-4")))
        if adv_sentence and len(adv_sentence) > 30:
            return create_layout("创建失败", Div(P("优势不能超过30字"), A("返回", href="/posts/new", cls="btn btn-primary mt-4")))
        channel_chat_id = (form.get('channel_chat_id') or '').strip() or None
        channel_link = (form.get('channel_link') or '').strip() or None

        # 频道字段最小规范化（与Bot一致）：互补生成
        try:
            from urllib.parse import urlparse
            if channel_chat_id and channel_chat_id.startswith('@') and not channel_link:
                channel_link = f"https://t.me/{channel_chat_id.lstrip('@')}"
            if (not channel_chat_id) and channel_link and (channel_link.startswith('http://') or channel_link.startswith('https://')):
                p = urlparse(channel_link)
                if p.netloc.endswith('t.me') and p.path:
                    username = p.path.strip('/').split('/')[0]
                    if username:
                        channel_chat_id = f"@{username}"
        except Exception:
            pass

        # 通过区县ID反查城市ID
        district = await region_manager.get_district_by_id(district_id)
        city_id = district['city_id'] if district else None

        merchant_data = {
            'telegram_chat_id': telegram_chat_id,
            'name': name,
            'city_id': city_id,
            'district_id': district_id,
            'p_price': int(p_price) if p_price else None,
            'pp_price': int(pp_price) if pp_price else None,
            'contact_info': contact_info,
            'adv_sentence': adv_sentence,
            'custom_description': custom_description,
            'channel_chat_id': channel_chat_id,
            'channel_link': channel_link,
            'status': 'pending_approval'
        }

        merchant_id = await merchant_manager.create_merchant(merchant_data)
        if merchant_id:
            try:
                # 自动检测并落库Telegram用户信息（非交互式创建场景也保持一致）
                await MerchantMgmtService.refresh_telegram_user_info(merchant_id)
            except Exception:
                pass
            return RedirectResponse(url=f"/posts/{merchant_id}", status_code=302)
        else:
            raise ValueError("创建失败，请检查Telegram用户ID是否已存在")
    except Exception as e:
        logger.error(f"创建帖子失败: {e}")
        return create_layout("创建失败", Div(P(f"创建失败: {str(e)}"), A("返回", href="/posts", cls="btn btn-primary mt-4")))


@require_auth
async def post_update(request: Request, post_id: int):
    """更新帖子信息"""
    try:
        # 获取表单数据
        form_data = await request.form()
        
        def to_int(val):
            try:
                return int(val) if val not in (None, "") else None
            except ValueError:
                return None

        # 频道字段最小规范化（互补）：
        ch_id = (form_data.get('channel_chat_id') or '').strip() or None
        ch_link = (form_data.get('channel_link') or '').strip() or None
        try:
            from urllib.parse import urlparse
            if ch_id and ch_id.startswith('@') and not ch_link:
                ch_link = f"https://t.me/{ch_id.lstrip('@')}"
            if (not ch_id) and ch_link and (ch_link.startswith('http://') or ch_link.startswith('https://')):
                p = urlparse(ch_link)
                if p.netloc.endswith('t.me') and p.path:
                    username = p.path.strip('/').split('/')[0]
                    if username:
                        ch_id = f"@{username}"
        except Exception:
            pass

        # 过期时间规范化：管理员输入任何时间，统一归一为“所选日期的次日 00:00”
        exp_raw = (form_data.get('expiration_time') or '').strip()
        exp_norm = None
        if exp_raw:
            try:
                s = exp_raw.replace('T', ' ')
                dt = None
                try:
                    dt = datetime.fromisoformat(s)
                except Exception:
                    try:
                        dt = datetime.strptime(s[:10], '%Y-%m-%d')
                    except Exception:
                        dt = None
                if dt:
                    base_midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    exp_dt = base_midnight + timedelta(days=1)
                    exp_norm = exp_dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                exp_norm = None

        # 构建更新数据（与 merchants 表字段一致）
        update_data = {
            'name': form_data.get('name') or None,
            'contact_info': form_data.get('contact_info') or None,
            'channel_chat_id': ch_id,
            'channel_link': ch_link,
            'custom_description': form_data.get('custom_description') or None,
            'adv_sentence': (form_data.get('adv_sentence') or '').strip() or None,
            'p_price': to_int(form_data.get('p_price')),
            'pp_price': to_int(form_data.get('pp_price')),
            'city_id': to_int(form_data.get('city_id')),
            'district_id': to_int(form_data.get('district_id')),
            'publish_time': form_data.get('publish_time') or None,
            'expiration_time': exp_norm
        }
        # 校验优势必填与长度
        if not update_data['adv_sentence']:
            return create_layout("更新失败", Div(P("优势不能为空"), A("返回详情", href=f"/posts/{post_id}", cls="btn btn-primary mt-4")))
        if update_data['adv_sentence'] and len(update_data['adv_sentence']) > 30:
            return create_layout("更新失败", Div(P("优势不能超过30字"), A("返回详情", href=f"/posts/{post_id}", cls="btn btn-primary mt-4")))

        # 一致性保证：若选择了district，则以district反推city，避免城市/地区不一致
        try:
            if update_data.get('district_id'):
                d = await region_manager.get_district_by_id(int(update_data['district_id']))
                if d and (not update_data.get('city_id') or int(update_data['city_id']) != int(d.get('city_id'))):
                    update_data['city_id'] = int(d.get('city_id'))
        except Exception:
            pass

        # 通过 MerchantManager 更新（信息更新）
        from database.db_merchants import merchant_manager as mm
        result = await mm.update_merchant(post_id, update_data)
        
        if result:
            try:
                # 若变更了 chat_id 或首次为空字段，自动刷新用户信息
                await MerchantMgmtService.refresh_telegram_user_info(post_id)
            except Exception:
                pass
            return RedirectResponse(url=f"/posts/{post_id}", status_code=302)
        else:
            raise ValueError('更新失败')
            
    except Exception as e:
        logger.error(f"更新帖子失败: {e}")
        error_content = Div(
            H1("更新失败", cls="text-2xl font-bold text-red-600 mb-4"),
            P(f"更新帖子时发生错误: {str(e)}"),
            A("返回详情", href=f"/posts/{post_id}", cls="btn btn-primary mt-4")
        )
        return create_layout("更新失败", error_content)


@require_auth
async def post_approve(request: Request, post_id: int):
    """批准帖子"""
    try:
        result = await PostMgmtService.update_post_status(
            merchant_id=post_id,
            status='approved'
        )
        
        if result.get('success'):
            return RedirectResponse(url="/posts", status_code=302)
        else:
            raise ValueError(result.get('error', '批准失败'))
            
    except Exception as e:
        logger.error(f"批准帖子失败: {e}")
        return RedirectResponse(url="/posts", status_code=302)


@require_auth  
async def post_reject(request: Request, post_id: int):
    """驳回帖子"""
    try:
        result = await PostMgmtService.update_post_status(
            merchant_id=post_id,
            status='pending_submission'
        )
        
        if result.get('success'):
            return RedirectResponse(url="/posts", status_code=302)
        else:
            raise ValueError(result.get('error', '驳回失败'))
            
    except Exception as e:
        logger.error(f"驳回帖子失败: {e}")
        return RedirectResponse(url="/posts", status_code=302)


@require_auth
async def post_publish(request: Request, post_id: int):
    """立即发布帖子"""
    try:
        result = await PostMgmtService.update_post_status(
            merchant_id=post_id,
            status='published'
        )
        
        if result.get('success'):
            return RedirectResponse(url="/posts", status_code=302)
        else:
            raise ValueError(result.get('error', '发布失败'))
            
    except Exception as e:
        logger.error(f"发布帖子失败: {e}")
        return RedirectResponse(url="/posts", status_code=302)


@require_auth
async def post_expire(request: Request, post_id: int):
    """设置帖子过期"""
    try:
        result = await PostMgmtService.update_post_status(
            merchant_id=post_id,
            status='expired'
        )
        
        if result.get('success'):
            return RedirectResponse(url="/posts", status_code=302)
        else:
            raise ValueError(result.get('error', '设置过期失败'))
            
    except Exception as e:
        logger.error(f"设置帖子过期失败: {e}")
        return RedirectResponse(url="/posts", status_code=302)


@require_auth
async def post_extend(request: Request, post_id: int):
    """延长帖子时间"""
    try:
        # 获取表单数据
        form_data = await request.form()
        days = int(form_data.get('days', 1))
        
        result = await PostMgmtService.extend_post_expiry(
            merchant_id=post_id,
            extend_days=days
        )
        
        if result.get('success'):
            return RedirectResponse(url="/posts", status_code=302)
        else:
            raise ValueError(result.get('error', '延长时间失败'))
            
    except Exception as e:
        logger.error(f"延长帖子时间失败: {e}")
        return RedirectResponse(url="/posts", status_code=302)


@require_auth
async def post_delete(request: Request, post_id: int):
    """删除帖子"""
    try:
        result = await PostMgmtService.delete_post(post_id)
        if result.get('success'):
            return RedirectResponse(url="/posts", status_code=302)
        else:
            raise ValueError(result.get('error', '删除失败'))
    except Exception as e:
        logger.error(f"删除帖子失败: {e}")
        return RedirectResponse(url=f"/posts/{post_id}", status_code=302)


## 移除：待提交的快捷“设为待审核”入口，改由Bot侧“提交审核”按钮触发
@require_auth
async def post_media_order_save(request: Request, post_id: int):
    try:
        form = await request.form()
        order = (form.get('order') or '').strip()
        if not order:
            return RedirectResponse(url=f"/posts/{post_id}", status_code=302)
        ids = [int(x) for x in order.split(',') if x.isdigit()]
        # 只取前6个并重排 sort_order 从0开始
        ids = ids[:6]
        for idx, mid in enumerate(ids):
            try:
                await db_manager.execute_query("UPDATE media SET sort_order = ? WHERE id = ?", (idx, mid))
            except Exception:
                pass
        return RedirectResponse(url=f"/posts/{post_id}", status_code=302)
    except Exception as e:
        logger.error(f"保存媒体顺序失败: {e}")
        return RedirectResponse(url=f"/posts/{post_id}", status_code=302)
