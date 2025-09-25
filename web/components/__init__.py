# -*- coding: utf-8 -*-
"""
Web Components Package - Modular UI Component Library

UI components extracted from web/app.py.old, implementing modular architecture refactoring.
Provides backward compatible component export mechanism.

Component Modules:
- forms: OKX theme form components (okx_*)
- tables: Data table and pagination components  
- charts: Statistical charts and card components
- indicators: Status indicator components
- layouts: Page layout components

Usage:
    from web.components import okx_button, okx_input
    from web.components.forms import OKXComponents
    from web.components.layouts import create_layout
"""

# Backward compatible component exports
try:
    from .forms import (
        okx_button,
        okx_input, 
        okx_textarea,
        okx_select,
        okx_form_group,
        OKXComponents
    )
except ImportError:
    # Fallback if forms module is not available
    okx_button = None
    okx_input = None
    okx_textarea = None
    okx_select = None
    okx_form_group = None
    OKXComponents = None

try:
    from .layouts import (
        create_layout,
        create_page_container,
        create_grid_layout
    )
except ImportError:
    create_layout = None
    create_page_container = None
    create_grid_layout = None

try:
    from .tables import (
        data_table,
        pagination,
        table_actions
    )
except ImportError:
    data_table = None
    pagination = None
    table_actions = None

try:
    from .charts import (
        stats_card,
        progress_bar,
        chart_container
    )
except ImportError:
    stats_card = None
    progress_bar = None
    chart_container = None

try:
    from .indicators import (
        status_badge,
        loading_spinner,
        alert_message
    )
except ImportError:
    status_badge = None
    loading_spinner = None
    alert_message = None

__all__ = [
    # Form components - backward compatible
    'okx_button',
    'okx_input', 
    'okx_textarea',
    'okx_select',
    'okx_form_group',
    'OKXComponents',
    
    # Layout components
    'create_layout',
    'create_page_container', 
    'create_grid_layout',
    
    # Table components
    'data_table',
    'pagination',
    'table_actions',
    
    # Chart components
    'stats_card',
    'progress_bar',
    'chart_container',
    
    # Indicator components
    'status_badge',
    'loading_spinner',
    'alert_message'
]

# Remove None values from exports
__all__ = [name for name in __all__ if globals().get(name) is not None]