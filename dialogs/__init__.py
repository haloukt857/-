"""
对话管理模块初始化文件
导出所有对话相关的类和函数
"""

from .states import (
    UserStates,
    MerchantStates, 
    AdminStates,
    StateData,
    StateValidator,
    StateManager,
    get_user_type_from_state,
    is_merchant_registration_state,
    is_admin_configuration_state
)

from .dialog_manager import (
    register_all_dialogs
)

from .binding_flow_new import router as binding_flow_router

__all__ = [
    # 状态相关
    'UserStates',
    'MerchantStates',
    'AdminStates', 
    'StateData',
    'StateValidator',
    'StateManager',
    'get_user_type_from_state',
    'is_merchant_registration_state',
    'is_admin_configuration_state',
    
    # 对话管理
    'register_all_dialogs',
    
    # 绑定流程
    'binding_flow_router'
]