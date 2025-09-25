"""
Forms Components - OKX主题表单组件

从web/app.py.old中提取的okx_*表单组件，实现统一的OKX主题样式。
支持Button、Input、Textarea、Select、FormGroup等组件。

Usage:
    from web.components.forms import okx_button, okx_input, OKXComponents
    
    button = okx_button("提交", onclick="submit()")
    input_field = okx_input("username", placeholder="请输入用户名")
    components = OKXComponents()
"""

from typing import List, Union, Tuple, Optional, Any
from fasthtml.common import *


def okx_button(text: str, **kwargs) -> Button:
    """
    OKX主题按钮组件
    
    Args:
        text (str): 按钮文本
        **kwargs: 其他HTML属性
        
    Returns:
        Button: FastHTML Button元素
        
    Example:
        okx_button("提交", onclick="submit()", cls="btn btn-success")
    """
    cls = kwargs.pop('cls', 'btn btn-primary')
    return Button(text, cls=cls, **kwargs)


def okx_input(name: str = None, **kwargs) -> Input:
    """
    OKX主题输入框组件
    
    Args:
        name (str, optional): 输入框name属性
        **kwargs: 其他HTML属性
        
    Returns:
        Input: FastHTML Input元素
        
    Example:
        okx_input("username", placeholder="请输入用户名", value="default")
    """
    cls = kwargs.pop('cls', 'input input-bordered w-full')
    if name:
        kwargs['name'] = name
    return Input(cls=cls, **kwargs)


def okx_textarea(name: str = None, **kwargs) -> Textarea:
    """
    OKX主题文本域组件
    
    Args:
        name (str, optional): 文本域name属性
        **kwargs: 其他HTML属性，包括content
        
    Returns:
        Textarea: FastHTML Textarea元素
        
    Example:
        okx_textarea("description", content="默认内容", rows=4)
    """
    cls = kwargs.pop('cls', 'textarea textarea-bordered w-full')
    content = kwargs.pop('content', '')
    if name:
        kwargs['name'] = name
    return Textarea(content, cls=cls, **kwargs)


def okx_select(name: str = None, options: List[Union[str, Tuple[str, str]]] = None, **kwargs) -> Select:
    """
    OKX主题选择框组件
    
    Args:
        name (str, optional): 选择框name属性
        options (List[Union[str, Tuple[str, str]]], optional): 选项列表
        **kwargs: 其他HTML属性，包括selected
        
    Returns:
        Select: FastHTML Select元素
        
    Example:
        okx_select("city", [("bj", "北京"), ("sh", "上海")], selected="bj")
    """
    cls = kwargs.pop('cls', 'select select-bordered w-full')
    selected = kwargs.pop('selected', None)
    if name:
        kwargs['name'] = name
    
    select_options = []
    if options:
        for option in options:
            if isinstance(option, tuple):
                value, label = option
                is_selected = (str(value) == str(selected)) if selected is not None else False
                select_options.append(Option(label, value=value, selected=is_selected))
            else:
                is_selected = (str(option) == str(selected)) if selected is not None else False
                select_options.append(Option(option, value=option, selected=is_selected))
    
    return Select(*select_options, cls=cls, **kwargs)


def okx_form_group(label: str, input_element, help_text: str = None, **kwargs) -> Div:
    """
    OKX主题表单组组件
    
    Args:
        label (str): 表单标签文本
        input_element: 输入元素（Input/Textarea/Select等）
        help_text (str, optional): 帮助文本
        **kwargs: 其他HTML属性
        
    Returns:
        Div: 包装后的表单组
        
    Example:
        form_group = okx_form_group(
            "用户名", 
            okx_input("username", placeholder="请输入用户名"),
            help_text="用户名长度为3-20个字符"
        )
    """
    elements = [
        Label(label, cls="label label-text"),
        input_element
    ]
    if help_text:
        elements.append(P(help_text, cls="text-sm text-gray-500 mt-1"))
    
    return Div(
        *elements,
        cls="form-control w-full mb-4",
        **kwargs
    )


class OKXComponents:
    """
    OKX组件统一管理类
    
    提供面向对象的组件调用方式，方便批量创建和管理表单组件。
    
    Usage:
        okx = OKXComponents()
        form = okx.create_form([
            ("username", "用户名", "input"),
            ("description", "描述", "textarea"),
            ("city", "城市", "select", [("bj", "北京"), ("sh", "上海")])
        ])
    """
    
    def button(self, text: str, **kwargs) -> Button:
        """创建按钮组件"""
        return okx_button(text, **kwargs)
    
    def input(self, name: str = None, **kwargs) -> Input:
        """创建输入框组件"""
        return okx_input(name, **kwargs)
    
    def textarea(self, name: str = None, **kwargs) -> Textarea:
        """创建文本域组件"""
        return okx_textarea(name, **kwargs)
    
    def select(self, name: str = None, options: List[Union[str, Tuple[str, str]]] = None, **kwargs) -> Select:
        """创建选择框组件"""
        return okx_select(name, options, **kwargs)
    
    def form_group(self, label: str, input_element, help_text: str = None, **kwargs) -> Div:
        """创建表单组组件"""
        return okx_form_group(label, input_element, help_text, **kwargs)
    
    def create_form(self, fields: List[Tuple], form_attrs: dict = None) -> Form:
        """
        批量创建表单
        
        Args:
            fields: 字段配置列表，每个元素为 (name, label, type, extra_config)
            form_attrs: 表单属性
            
        Returns:
            Form: 完整的表单元素
            
        Example:
            fields = [
                ("username", "用户名", "input", {"placeholder": "请输入用户名"}),
                ("city", "城市", "select", {"options": [("bj", "北京"), ("sh", "上海")]})
            ]
        """
        if form_attrs is None:
            form_attrs = {}
        
        form_elements = []
        
        for field_config in fields:
            if len(field_config) < 3:
                continue
                
            name = field_config[0]
            label = field_config[1]
            field_type = field_config[2]
            extra_config = field_config[3] if len(field_config) > 3 else {}
            
            # 创建输入元素
            if field_type == "input":
                input_element = self.input(name, **extra_config)
            elif field_type == "textarea":
                input_element = self.textarea(name, **extra_config)
            elif field_type == "select":
                options = extra_config.pop("options", [])
                input_element = self.select(name, options, **extra_config)
            else:
                continue
            
            # 创建表单组
            help_text = extra_config.get("help_text")
            form_group = self.form_group(label, input_element, help_text)
            form_elements.append(form_group)
        
        return Form(*form_elements, **form_attrs)
    
    def create_action_buttons(self, actions: List[Tuple[str, str]], **kwargs) -> Div:
        """
        创建操作按钮组
        
        Args:
            actions: 按钮配置列表 [(text, action_attrs), ...]
            **kwargs: 容器属性
            
        Returns:
            Div: 包装后的按钮组
        """
        buttons = []
        for text, attrs in actions:
            if isinstance(attrs, str):
                # 如果attrs是字符串，假设是onclick事件
                attrs = {"onclick": attrs}
            buttons.append(self.button(text, **attrs))
        
        container_cls = kwargs.pop('cls', 'flex gap-2 mt-4')
        return Div(*buttons, cls=container_cls, **kwargs)


# 向后兼容的导出
__all__ = [
    'okx_button',
    'okx_input',
    'okx_textarea', 
    'okx_select',
    'okx_form_group',
    'OKXComponents'
]