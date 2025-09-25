# -*- coding: utf-8 -*-
"""
地区管理路由模块
处理城市、区县管理和地区筛选功能
"""

import logging
from fasthtml.common import *
from starlette.requests import Request
from starlette.responses import RedirectResponse

# 导入布局和认证组件
from ..layout import create_layout, require_auth

logger = logging.getLogger(__name__)


# 导入服务层
from ..services.region_mgmt_service import RegionMgmtService

# 导入CSRF功能
from ..layout import validate_csrf, get_or_create_csrf_token, okx_form_group, okx_input, okx_button, okx_select

import logging

async def regions_list(request: Request):
    """地区管理页面 - 显示城市和区县列表，支持增删改查操作"""
    
    try:
        # 获取地区数据（使用服务层的缓存机制）
        regions_data = await RegionMgmtService.get_regions_list()
        cities = regions_data.get('cities', [])
        districts = regions_data.get('districts', [])
        
        # 生成CSRF Token
        csrf_token = get_or_create_csrf_token(request)
        
        content = Div(
            # 页面头部
            Div(
                H1("地区管理", cls="page-title"),
                P("管理城市和区县信息", cls="page-subtitle"),
                cls="page-header"
            ),
            
            # 统计信息卡片
            Div(
                Div(
                    Div("城市总数", cls="text-sm text-gray-600"),
                    Div(str(len(cities)), cls="text-2xl font-bold text-blue-600"),
                    cls="stat-card"
                ),
                Div(
                    Div("区县总数", cls="text-sm text-gray-600"),
                    Div(str(len(districts)), cls="text-2xl font-bold text-green-600"),
                    cls="stat-card"
                ),
                cls="stats-container mb-6"
            ),
            
            # 城市管理区域
            Div(
                # 城市管理头部 - 添加"添加城市"按钮和表单
                Div(
                    H3("城市列表", cls="text-lg font-semibold mb-4"),
                    # 添加城市表单
                    Details(
                        Summary("➕ 添加新城市", cls="btn btn-primary btn-sm mb-4"),
                        Form(
                            okx_form_group(
                                "城市名称",
                                okx_input("city_name", placeholder="请输入城市名称", required=True)
                            ),
                            okx_form_group(
                                "状态",
                                okx_select("is_active", [
                                    ("1", "启用"),
                                    ("0", "禁用")
                                ], selected="1")
                            ),
                            Input(type="hidden", name="csrf_token", value=csrf_token),
                            okx_button("添加城市", type="submit", variant="primary"),
                            method="post",
                            action="/regions/city/add",
                            cls="bg-base-200 p-4 rounded-lg mt-2"
                        ),
                        cls="mb-4"
                    ),
                    cls="flex justify-between items-start mb-4"
                ),
                
                # 城市列表表格
                Div(
                    Table(
                        Thead(
                            Tr(
                                Th("ID"),
                                Th("城市名称"),
                                Th("状态"),
                                Th("操作")
                            )
                        ),
                        Tbody(
                            *[
                                Tr(
                                    Td(str(city.get('id', '-'))),
                                    Td(city.get('name', '-')),
                                    Td(
                                        Span("启用" if city.get('is_active', True) else "禁用",
                                             cls=f"badge {'badge-success' if city.get('is_active', True) else 'badge-error'}")
                                    ),
                                    Td(
                                        Div(
                                            A("✏️ 编辑", href=f"/regions/city/{city.get('id')}/edit", cls="btn btn-xs btn-outline mr-1"),
                                            Form(
                                                Input(type="hidden", name="csrf_token", value=csrf_token),
                                                Button("🔄 切换状态", 
                                                      type="submit", 
                                                      cls="btn btn-xs btn-warning mr-1",
                                                      onclick="return confirm('确定要切换城市状态吗？')"),
                                                method="post",
                                                action=f"/regions/city/{city.get('id')}/toggle",
                                                style="display: inline-block;"
                                            ),
                                            Form(
                                                Input(type="hidden", name="csrf_token", value=csrf_token),
                                                Button("🗑️ 删除", 
                                                      type="submit", 
                                                      cls="btn btn-xs btn-error",
                                                      onclick="return confirm('确定要删除这个城市吗？删除后该城市下的所有区县也会被删除！')"),
                                                method="post",
                                                action=f"/regions/city/{city.get('id')}/delete",
                                                style="display: inline-block;"
                                            ),
                                            cls="flex gap-1"
                                        )
                                    )
                                )
                                for city in cities
                            ] if cities else [
                                Tr(
                                    Td("暂无城市数据", colspan="4", cls="text-center text-gray-500")
                                )
                            ]
                        ),
                        cls="table table-zebra w-full"
                    ),
                    cls="overflow-x-auto"
                ),
                cls="card bg-base-100 shadow-xl p-6 mb-6"
            ),
            
            # 区县管理区域
            Div(
                # 区县管理头部 - 添加"添加区县"按钮和表单
                Div(
                    H3("区县列表", cls="text-lg font-semibold mb-4"),
                    # 添加区县表单
                    Details(
                        Summary("➕ 添加新区县", cls="btn btn-secondary btn-sm mb-4"),
                        Form(
                            okx_form_group(
                                "所属城市",
                                okx_select("city_id", [
                                    (str(city.get('id')), city.get('name'))
                                    for city in cities if city.get('is_active', True)
                                ] + [("", "请选择城市")] if cities else [("", "暂无可用城市")], 
                                selected="")
                            ),
                            okx_form_group(
                                "区县名称",
                                okx_input("district_name", placeholder="请输入区县名称", required=True)
                            ),
                            okx_form_group(
                                "状态",
                                okx_select("is_active", [
                                    ("1", "启用"),
                                    ("0", "禁用")
                                ], selected="1")
                            ),
                            Input(type="hidden", name="csrf_token", value=csrf_token),
                            okx_button("添加区县", type="submit", variant="secondary", disabled=not cities),
                            method="post",
                            action="/regions/district/add",
                            cls="bg-base-200 p-4 rounded-lg mt-2"
                        ),
                        cls="mb-4"
                    ),
                    cls="flex justify-between items-start mb-4"
                ),
                
                # 区县列表表格
                Div(
                    Table(
                        Thead(
                            Tr(
                                Th("ID"),
                                Th("区县名称"),
                                Th("所属城市"),
                                Th("状态"),
                                Th("操作")
                            )
                        ),
                        Tbody(
                            *[
                                Tr(
                                    Td(str(district.get('id', '-'))),
                                    Td(district.get('name', '-')),
                                    Td(district.get('city_name', '-')),
                                    Td(
                                        Span("启用" if district.get('is_active', True) else "禁用",
                                             cls=f"badge {'badge-success' if district.get('is_active', True) else 'badge-error'}")
                                    ),
                                    Td(
                                        Div(
                                            A("✏️ 编辑", href=f"/regions/district/{district.get('id')}/edit", cls="btn btn-xs btn-outline mr-1"),
                                            Form(
                                                Input(type="hidden", name="csrf_token", value=csrf_token),
                                                Button("🔄 切换状态", 
                                                      type="submit", 
                                                      cls="btn btn-xs btn-warning mr-1",
                                                      onclick="return confirm('确定要切换区县状态吗？')"),
                                                method="post",
                                                action=f"/regions/district/{district.get('id')}/toggle",
                                                style="display: inline-block;"
                                            ),
                                            Form(
                                                Input(type="hidden", name="csrf_token", value=csrf_token),
                                                Button("🗑️ 删除", 
                                                      type="submit", 
                                                      cls="btn btn-xs btn-error",
                                                      onclick="return confirm('确定要删除这个区县吗？')"),
                                                method="post",
                                                action=f"/regions/district/{district.get('id')}/delete",
                                                style="display: inline-block;"
                                            ),
                                            cls="flex gap-1"
                                        )
                                    )
                                )
                                for district in districts
                            ] if districts else [
                                Tr(
                                    Td("暂无区县数据", colspan="5", cls="text-center text-gray-500")
                                )
                            ]
                        ),
                        cls="table table-zebra w-full"
                    ),
                    cls="overflow-x-auto"
                ),
                cls="card bg-base-100 shadow-xl p-6"
            ),
            
            cls="page-content"
        )
        
        return create_layout("地区管理", content)
        
    except Exception as e:
        logger.error(f"地区管理页面错误: {e}")
        import traceback
        logger.error(f"完整堆栈: {traceback.format_exc()}")
        error_content = Div(
            H1("地区管理错误", cls="text-2xl font-bold text-red-600 mb-4"),
            Pre(f"{str(e)}\n\n{traceback.format_exc()}", cls="bg-gray-100 p-4 rounded text-sm")
        )
        return create_layout("系统错误", error_content)


# 路由注册在 web/app.py 中进行
# 这里只提供路由函数


@require_auth
async def add_city_route(request: Request):
    """添加城市"""
    form = await request.form()
    
    try:
        # CSRF校验
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/regions?error=csrf", status_code=302)
            
        city_name = form.get('city_name', '').strip()
        display_order = form.get('display_order', '0')
        
        if not city_name:
            return RedirectResponse(url="/regions?error=empty_name", status_code=302)
        
        # 使用表单提交的状态值
        is_active_value = form.get('is_active', '1') == '1'
        
        # 调用服务层创建城市
        # 传递显示顺序（如未提供则为0）
        result = await RegionMgmtService.create_city(city_name, is_active_value, int(display_order or 0))
        
        if result.get('success'):
            return RedirectResponse(url="/regions?city_added=1", status_code=302)
        else:
            error = result.get('error', '创建失败')
            return RedirectResponse(url=f"/regions?error={error}", status_code=302)
            
    except Exception as e:
        logger.error(f"添加城市时出错: {e}")
        return RedirectResponse(url="/regions?error=1", status_code=302)


@require_auth
async def add_district_route(request: Request):
    """添加地区"""
    form = await request.form()
    
    try:
        # CSRF校验
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/regions?error=csrf", status_code=302)
            
        city_id = int(form.get('city_id', 0))
        district_name = form.get('district_name', '').strip()
        display_order = form.get('display_order', '0')
        
        if not district_name:
            return RedirectResponse(url="/regions?error=empty_name", status_code=302)
        
        if city_id <= 0:
            return RedirectResponse(url="/regions?error=invalid_city", status_code=302)
        
        # 使用表单提交的状态值
        is_active_value = form.get('is_active', '1') == '1'
        
        # 调用服务层创建区县
        # 传递显示顺序（如未提供则为0）
        result = await RegionMgmtService.create_district(city_id, district_name, is_active_value, int(display_order or 0))
        
        if result.get('success'):
            return RedirectResponse(url="/regions?district_added=1", status_code=302)
        else:
            error = result.get('error', '创建失败')
            return RedirectResponse(url=f"/regions?error={error}", status_code=302)
            
    except Exception as e:
        logger.error(f"添加地区时出错: {e}")
        return RedirectResponse(url="/regions?error=1", status_code=302)


@require_auth
async def delete_city_route(request: Request):
    """删除城市"""
    city_id = request.path_params.get('city_id')
    form = await request.form()
    
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/regions?error=csrf", status_code=302)
            
        city_id = int(city_id)
        
        # 调用服务层删除城市
        result = await RegionMgmtService.delete_city(city_id)
        
        if result.get('success'):
            return RedirectResponse(url="/regions?city_deleted=1", status_code=302)
        else:
            error = result.get('error', '删除失败')
            return RedirectResponse(url=f"/regions?error={error}", status_code=302)
            
    except Exception as e:
        logger.error(f"删除城市时出错: {e}")
        return RedirectResponse(url="/regions?error=delete_failed", status_code=302)


@require_auth
async def delete_district_route(request: Request):
    """删除地区"""
    district_id = request.path_params.get('district_id')
    form = await request.form()
    
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/regions?error=csrf", status_code=302)
            
        district_id = int(district_id)
        
        # 调用服务层删除区县
        result = await RegionMgmtService.delete_district(district_id)
        
        if result.get('success'):
            return RedirectResponse(url="/regions?district_deleted=1", status_code=302)
        else:
            error = result.get('error', '删除失败')
            return RedirectResponse(url=f"/regions?error={error}", status_code=302)
            
    except Exception as e:
        logger.error(f"删除地区时出错: {e}")
        return RedirectResponse(url="/regions?error=delete_failed", status_code=302)


@require_auth
async def edit_city_get_route(request: Request):
    """城市编辑页面"""
    city_id = request.path_params.get('city_id')
    
    try:
        city_id = int(city_id)
        
        # 调用服务层获取城市详情
        city_data = await RegionMgmtService.get_city_detail(city_id)
        
        if not city_data.get('success'):
            return RedirectResponse(url="/regions?error=city_not_found", status_code=302)
        
        city = city_data.get('city')
        
        # 生成CSRF Token
        csrf_token = get_or_create_csrf_token(request)
        
        content = Div(
            H2("编辑城市", cls="text-2xl font-bold mb-6"),
            Form(
                Input(type="hidden", name="csrf_token", value=csrf_token),
                okx_form_group("城市名称", okx_input("city_name", value=city['name'], required=True)),
                okx_form_group("状态", okx_select("is_active", [("1", "启用"), ("0", "禁用")], selected="1" if city.get('is_active', True) else "0")),
                okx_form_group("显示顺序", okx_input("display_order", type="number", value=str(city.get('display_order', 0)))),
                Div(
                    okx_button("保存", type="submit", cls="btn btn-primary mr-2"),
                    A("取消", href="/regions", cls="btn btn-secondary"),
                    cls="flex gap-2"
                ),
                method="POST",
                action=f"/regions/city/{city_id}/edit",
                cls="card bg-base-100 shadow-xl p-6"
            )
        )
        return create_layout("编辑城市", content)
                
    except Exception as e:
        logger.error(f"编辑城市页面错误: {e}")
        return RedirectResponse(url="/regions?error=1", status_code=302)


@require_auth
async def edit_city_post_route(request: Request):
    """处理城市编辑"""
    city_id = request.path_params.get('city_id')
    
    try:
        city_id = int(city_id)
        form = await request.form()
        
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url=f"/regions/city/{city_id}/edit?error=csrf", status_code=302)
            
        city_name = form.get('city_name', '').strip()
        display_order = int(form.get('display_order', '0'))  # 读取显示顺序
        
        if not city_name:
            return RedirectResponse(url=f"/regions/city/{city_id}/edit?error=empty_name", status_code=302)
        
        # 从表单读取状态值
        is_active_value = form.get('is_active', '1') == '1'

        # 调用服务层更新城市，使用表单提交的状态值
        result = await RegionMgmtService.update_city(city_id, city_name, is_active_value, display_order)
        
        if result.get('success'):
            return RedirectResponse(url="/regions?city_updated=1", status_code=302)
        else:
            error = result.get('error', '更新失败')
            return RedirectResponse(url=f"/regions/city/{city_id}/edit?error={error}", status_code=302)
            
    except Exception as e:
        logger.error(f"编辑城市时出错: {e}")
        return RedirectResponse(url="/regions?error=update_failed", status_code=302)


@require_auth
async def edit_district_get_route(request: Request):
    """地区编辑页面"""
    district_id = request.path_params.get('district_id')
    
    try:
        district_id = int(district_id)
        
        # 获取区县信息和所有城市
        regions_data = await RegionMgmtService.get_regions_list()
        cities = regions_data.get('cities', [])
        districts = regions_data.get('districts', [])
        
        # 找到要编辑的区县
        district = None
        for d in districts:
            if d['id'] == district_id:
                district = d
                break
        
        if not district:
            return RedirectResponse(url="/regions?error=district_not_found", status_code=302)
        
        # 生成CSRF Token
        csrf_token = get_or_create_csrf_token(request)
        
        content = Div(
            H2("编辑地区", cls="text-2xl font-bold mb-6"),
            Form(
                Input(type="hidden", name="csrf_token", value=csrf_token),
                okx_form_group("所属城市", okx_select("city_id", options=[(city['id'], city['name']) for city in cities], selected=district.get('city_id'))),
                okx_form_group("地区名称", okx_input("district_name", value=district['name'], required=True)),
                okx_form_group("状态", okx_select("is_active", [("1", "启用"), ("0", "禁用")], selected="1" if district.get('is_active', True) else "0")),
                okx_form_group("显示顺序", okx_input("display_order", type="number", value=str(district.get('display_order', 0)))),
                Div(
                    okx_button("保存", type="submit", cls="btn btn-primary mr-2"),
                    A("取消", href="/regions", cls="btn btn-secondary"),
                    cls="flex gap-2"
                ),
                method="POST",
                action=f"/regions/district/{district_id}/edit",
                cls="card bg-base-100 shadow-xl p-6"
            )
        )
        return create_layout("编辑地区", content)
                
    except Exception as e:
        logger.error(f"编辑地区页面错误: {e}")
        return RedirectResponse(url="/regions?error=1", status_code=302)


@require_auth
async def edit_district_post_route(request: Request):
    """处理地区编辑"""
    district_id = request.path_params.get('district_id')
    
    try:
        district_id = int(district_id)
        form = await request.form()
        
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url=f"/regions/district/{district_id}/edit?error=csrf", status_code=302)
            
        district_name = form.get('district_name', '').strip()
        city_id = int(form.get('city_id', 0))
        display_order = int(form.get('display_order', '0'))  # 读取显示顺序
        
        if not district_name:
            return RedirectResponse(url=f"/regions/district/{district_id}/edit?error=empty_name", status_code=302)
        
        if city_id <= 0:
            return RedirectResponse(url=f"/regions/district/{district_id}/edit?error=invalid_city", status_code=302)
        
        # 从表单读取状态值
        is_active_value = form.get('is_active', '1') == '1'

        # 调用服务层更新区县，使用表单提交的状态值
        result = await RegionMgmtService.update_district(district_id, city_id, district_name, is_active_value, display_order)
        
        if result.get('success'):
            return RedirectResponse(url="/regions?district_updated=1", status_code=302)
        else:
            error = result.get('error', '更新失败')
            return RedirectResponse(url=f"/regions/district/{district_id}/edit?error={error}", status_code=302)
            
    except Exception as e:
        logger.error(f"编辑地区时出错: {e}")
        return RedirectResponse(url="/regions?error=update_failed", status_code=302)


@require_auth
async def toggle_city_status_route(request: Request):
    """切换城市状态"""
    city_id = int(request.path_params.get('city_id'))
    form = await request.form()
    
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/regions?error=csrf", status_code=302)
        
        # 调用服务层切换城市状态（使用专用的toggle方法）
        result = await RegionMgmtService.toggle_city_status(city_id)
        
        return RedirectResponse(url="/regions", status_code=302)
        
    except Exception as e:
        logger.error(f"切换城市状态失败: {e}")
        return RedirectResponse(url="/regions?error=1", status_code=302)


@require_auth
async def toggle_district_status_route(request: Request):
    """切换地区状态"""
    district_id = int(request.path_params.get('district_id'))
    form = await request.form()
    
    try:
        if not validate_csrf(request, form.get('csrf_token', '')):
            return RedirectResponse(url="/regions?error=csrf", status_code=302)
        
        # 调用服务层切换区县状态（使用专用的toggle方法）
        result = await RegionMgmtService.toggle_district_status(district_id)
        
        return RedirectResponse(url="/regions", status_code=302)
        
    except Exception as e:
        logger.error(f"切换地区状态失败: {e}")
        return RedirectResponse(url="/regions?error=1", status_code=302)
