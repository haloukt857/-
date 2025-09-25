"""
Table Components - 数据表格组件

提供通用的数据表格、分页、表格操作等组件。
支持响应式设计、排序、筛选、行操作等功能。

Usage:
    from web.components.tables import data_table, pagination
    
    table = data_table(
        columns=['ID', '名称', '状态', '操作'],
        data=data_list,
        actions=['edit', 'delete']
    )
"""

from typing import List, Dict, Any, Optional, Union, Tuple, Callable
from fasthtml.common import *


def data_table(
    columns: List[str], 
    data: List[Dict[str, Any]], 
    actions: Optional[List[Union[str, Dict[str, Any]]]] = None,
    table_id: str = "data-table",
    **kwargs
) -> Div:
    """
    创建数据表格组件
    
    Args:
        columns (List[str]): 表格列标题
        data (List[Dict]): 表格数据
        actions (List, optional): 行操作按钮配置
        table_id (str): 表格ID
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 表格容器
        
    Example:
        table = data_table(
            columns=['ID', '用户名', '状态', '操作'],
            data=[
                {'id': 1, 'username': 'admin', 'status': '正常'},
                {'id': 2, 'username': 'user1', 'status': '禁用'}
            ],
            actions=[
                {'text': '编辑', 'action': 'edit', 'class': 'btn-primary'},
                {'text': '删除', 'action': 'delete', 'class': 'btn-error'}
            ]
        )
    """
    # 表格头部
    thead_cells = [Th(col) for col in columns]
    thead = Thead(Tr(*thead_cells))
    
    # 表格数据行
    tbody_rows = []
    
    for row_data in data:
        cells = []
        
        # 数据列
        for i, col in enumerate(columns):
            # 跳过操作列
            col_name = col if isinstance(col, str) else str(col)
            if col_name.lower() in ['操作', 'actions', 'action']:
                continue
                
            # 获取列数据，支持嵌套字段
            col_key = col_name.lower().replace(' ', '_')
            if col_key in row_data:
                cell_value = row_data[col_key]
            elif col_name in row_data:
                cell_value = row_data[col_name]
            else:
                # 尝试根据索引匹配
                data_keys = list(row_data.keys())
                if i < len(data_keys):
                    cell_value = row_data[data_keys[i]]
                else:
                    cell_value = ""
            
            # 处理特殊数据类型
            if isinstance(cell_value, bool):
                cell_content = "是" if cell_value else "否"
            elif cell_value is None:
                cell_content = "-"
            else:
                cell_content = str(cell_value)
            
            cells.append(Td(cell_content))
        
        # 操作列
        if actions and any(col.lower() in ['操作', 'actions', 'action'] for col in columns):
            action_buttons = []
            row_id = row_data.get('id', row_data.get('ID', ''))
            
            for action in actions:
                if isinstance(action, str):
                    # 简单字符串配置
                    action_config = {'text': action, 'action': action}
                elif isinstance(action, dict):
                    action_config = action
                else:
                    continue
                
                btn_text = action_config.get('text', action_config.get('action', '操作'))
                btn_class = action_config.get('class', 'btn btn-sm btn-outline')
                btn_onclick = action_config.get('onclick', f"handleAction('{action_config.get('action', '')}', '{row_id}')")
                
                action_buttons.append(
                    Button(
                        btn_text,
                        cls=btn_class,
                        onclick=btn_onclick
                    )
                )
            
            if action_buttons:
                cells.append(Td(Div(*action_buttons, cls="flex gap-1")))
        
        tbody_rows.append(Tr(*cells))
    
    tbody = Tbody(*tbody_rows)
    
    # 组装表格
    table_cls = kwargs.pop('cls', 'table table-zebra w-full')
    
    return Div(
        Table(
            thead,
            tbody,
            cls=table_cls,
            id=table_id
        ),
        cls="overflow-x-auto",
        **kwargs
    )


def pagination(
    current_page: int = 1,
    total_pages: int = 1,
    total_items: int = 0,
    per_page: int = 20,
    base_url: str = "",
    **kwargs
) -> Div:
    """
    创建分页组件
    
    Args:
        current_page (int): 当前页码
        total_pages (int): 总页数
        total_items (int): 总条目数
        per_page (int): 每页条目数
        base_url (str): 基础URL
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 分页容器
        
    Example:
        pagination_html = pagination(
            current_page=2,
            total_pages=10,
            total_items=200,
            per_page=20,
            base_url="/merchants"
        )
    """
    if total_pages <= 1:
        return Div()  # 不显示分页
    
    pagination_items = []
    
    # 上一页
    if current_page > 1:
        prev_url = f"{base_url}?page={current_page - 1}"
        pagination_items.append(
            A("«", href=prev_url, cls="join-item btn")
        )
    else:
        pagination_items.append(
            Button("«", disabled=True, cls="join-item btn btn-disabled")
        )
    
    # 页码按钮
    start_page = max(1, current_page - 2)
    end_page = min(total_pages, current_page + 2)
    
    # 添加第一页和省略号
    if start_page > 1:
        pagination_items.append(
            A("1", href=f"{base_url}?page=1", cls="join-item btn")
        )
        if start_page > 2:
            pagination_items.append(
                Button("...", disabled=True, cls="join-item btn btn-disabled")
            )
    
    # 中间页码
    for page in range(start_page, end_page + 1):
        if page == current_page:
            pagination_items.append(
                Button(str(page), cls="join-item btn btn-active")
            )
        else:
            page_url = f"{base_url}?page={page}"
            pagination_items.append(
                A(str(page), href=page_url, cls="join-item btn")
            )
    
    # 添加最后一页和省略号
    if end_page < total_pages:
        if end_page < total_pages - 1:
            pagination_items.append(
                Button("...", disabled=True, cls="join-item btn btn-disabled")
            )
        pagination_items.append(
            A(str(total_pages), href=f"{base_url}?page={total_pages}", cls="join-item btn")
        )
    
    # 下一页
    if current_page < total_pages:
        next_url = f"{base_url}?page={current_page + 1}"
        pagination_items.append(
            A("»", href=next_url, cls="join-item btn")
        )
    else:
        pagination_items.append(
            Button("»", disabled=True, cls="join-item btn btn-disabled")
        )
    
    # 分页信息
    start_item = (current_page - 1) * per_page + 1
    end_item = min(current_page * per_page, total_items)
    
    info_text = f"显示 {start_item}-{end_item} 条，共 {total_items} 条"
    
    container_cls = kwargs.pop('cls', 'flex justify-between items-center mt-4')
    
    return Div(
        Div(info_text, cls="text-sm text-gray-600"),
        Div(*pagination_items, cls="join"),
        cls=container_cls,
        **kwargs
    )


def table_actions(*actions, **kwargs) -> Div:
    """
    创建表格操作栏
    
    Args:
        *actions: 操作按钮
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 操作栏容器
        
    Example:
        actions_bar = table_actions(
            Button("新增", cls="btn btn-primary", onclick="addNew()"),
            Button("批量删除", cls="btn btn-error", onclick="batchDelete()"),
            cls="mb-4"
        )
    """
    container_cls = kwargs.pop('cls', 'flex gap-2 mb-4')
    
    return Div(*actions, cls=container_cls, **kwargs)


def searchable_table(
    columns: List[str],
    data: List[Dict[str, Any]], 
    search_fields: List[str] = None,
    **kwargs
) -> Div:
    """
    创建可搜索的数据表格
    
    Args:
        columns (List[str]): 表格列标题
        data (List[Dict]): 表格数据
        search_fields (List[str]): 可搜索的字段
        **kwargs: 传递给data_table的参数
        
    Returns:
        Div: 包含搜索框和表格的容器
        
    Example:
        searchable = searchable_table(
            columns=['ID', '用户名', '邮箱'],
            data=users_data,
            search_fields=['username', 'email']
        )
    """
    table_id = kwargs.get('table_id', 'searchable-table')
    search_id = f"{table_id}-search"
    
    # 搜索框
    search_box = Div(
        Input(
            placeholder="搜索...",
            cls="input input-bordered w-full max-w-sm",
            id=search_id,
            oninput=f"filterTable('{search_id}', '{table_id}')"
        ),
        cls="mb-4"
    )
    
    # 数据表格
    table = data_table(columns, data, table_id=table_id, **kwargs)
    
    # 搜索脚本
    search_script = Script(f"""
        function filterTable(searchId, tableId) {{
            const searchTerm = document.getElementById(searchId).value.toLowerCase();
            const table = document.getElementById(tableId);
            const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
            
            for (let i = 0; i < rows.length; i++) {{
                const row = rows[i];
                const cells = row.getElementsByTagName('td');
                let found = false;
                
                for (let j = 0; j < cells.length; j++) {{
                    const cellText = cells[j].textContent.toLowerCase();
                    if (cellText.includes(searchTerm)) {{
                        found = true;
                        break;
                    }}
                }}
                
                row.style.display = found ? '' : 'none';
            }}
        }}
    """)
    
    return Div(
        search_box,
        table,
        search_script
    )


def sortable_table(
    columns: List[str],
    data: List[Dict[str, Any]],
    sortable_columns: List[str] = None,
    **kwargs
) -> Div:
    """
    创建可排序的数据表格
    
    Args:
        columns (List[str]): 表格列标题
        data (List[Dict]): 表格数据
        sortable_columns (List[str]): 可排序的列
        **kwargs: 传递给data_table的参数
        
    Returns:
        Div: 包含排序功能的表格容器
    """
    table_id = kwargs.get('table_id', 'sortable-table')
    
    # 如果没有指定可排序列，默认所有列都可排序
    if sortable_columns is None:
        sortable_columns = [col for col in columns if col.lower() not in ['操作', 'actions', 'action']]
    
    # 修改表头，添加排序图标
    enhanced_columns = []
    for col in columns:
        if col in sortable_columns:
            enhanced_columns.append(f"{col} ↕")
        else:
            enhanced_columns.append(col)
    
    # 创建表格
    table = data_table(enhanced_columns, data, table_id=table_id, **kwargs)
    
    # 排序脚本
    sort_script = Script(f"""
        function sortTable(tableId, columnIndex) {{
            const table = document.getElementById(tableId);
            const tbody = table.getElementsByTagName('tbody')[0];
            const rows = Array.from(tbody.getElementsByTagName('tr'));
            
            // 获取当前排序状态
            const header = table.getElementsByTagName('th')[columnIndex];
            const isAsc = !header.classList.contains('sort-desc');
            
            // 清除所有排序状态
            const headers = table.getElementsByTagName('th');
            for (let h of headers) {{
                h.classList.remove('sort-asc', 'sort-desc');
            }}
            
            // 设置当前列排序状态
            header.classList.add(isAsc ? 'sort-asc' : 'sort-desc');
            
            // 排序行
            rows.sort((a, b) => {{
                const aText = a.getElementsByTagName('td')[columnIndex].textContent;
                const bText = b.getElementsByTagName('td')[columnIndex].textContent;
                
                // 尝试数字排序
                const aNum = parseFloat(aText);
                const bNum = parseFloat(bText);
                
                if (!isNaN(aNum) && !isNaN(bNum)) {{
                    return isAsc ? aNum - bNum : bNum - aNum;
                }}
                
                // 文本排序
                return isAsc ? aText.localeCompare(bText) : bText.localeCompare(aText);
            }});
            
            // 重新插入排序后的行
            rows.forEach(row => tbody.appendChild(row));
        }}
        
        // 为表头添加点击事件
        document.addEventListener('DOMContentLoaded', function() {{
            const table = document.getElementById('{table_id}');
            const headers = table.getElementsByTagName('th');
            
            for (let i = 0; i < headers.length; i++) {{
                const header = headers[i];
                if (header.textContent.includes('↕')) {{
                    header.style.cursor = 'pointer';
                    header.onclick = () => sortTable('{table_id}', i);
                }}
            }}
        }});
    """)
    
    return Div(table, sort_script)


# 向后兼容的导出
__all__ = [
    'data_table',
    'pagination', 
    'table_actions',
    'searchable_table',
    'sortable_table'
]