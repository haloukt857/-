"""
Telegram商户机器人FSM状态定义
定义所有用户类型的状态类，支持状态持久化和转换验证
"""

from aiogram.fsm.state import State, StatesGroup
from typing import Dict, Any, Optional, List
import json
import logging
from datetime import datetime, timedelta

# 设置日志记录器
logger = logging.getLogger(__name__)


class UserStates(StatesGroup):
    """
    普通用户状态组
    处理用户与商户的交互流程
    """
    # 等待商户选择状态
    waiting_for_merchant_selection = State()
    
    # 正在对话状态
    in_conversation = State()
    
    # 选择服务状态
    selecting_service = State()
    
    # 选择价格类型状态 (P/PP选择)
    selecting_price = State()
    
    # 填写预约信息状态
    filling_appointment_info = State()
    
    # 确认订单状态
    confirming_order = State()


class MerchantStates(StatesGroup):
    """
    商户状态组
    处理商户注册和信息管理流程
    """
    # 绑定码输入状态
    entering_binding_code = State()
    
    # 选择地区状态
    selecting_region = State()
    
    # 选择类别状态
    selecting_category = State()
    
    # 输入名称状态
    entering_name = State()
    
    # 输入联系信息状态
    entering_contact_info = State()
    
    # 确认档案状态
    confirming_profile = State()
    
    # 编辑档案状态
    editing_profile = State()

    # 新版7步注册流程中的文本输入状态
    # 步骤4：输入 P 价格
    entering_p_price = State()
    # 步骤5：输入 PP 价格
    entering_pp_price = State()
    # 步骤6：输入自定义服务描述
    entering_custom_description = State()
    # 步骤7：输入频道用户名（@username）
    entering_channel_username = State()

    # 新增：优势一句话（≤30字）
    entering_adv_sentence = State()

    # 新增：输入优势一句话（≤30字）
    entering_adv_sentence = State()

    # 步骤9：选择发布时间（日期+时间槽）
    selecting_publish_time = State()

    # 管理媒体（等待用户发送图片/视频）
    uploading_media = State()


class MerchantOnboardingStates(StatesGroup):
    """商户信息提交流程状态（详细分步）"""
    AwaitingName = State()
    AwaitingCity = State()
    AwaitingDistrict = State()
    AwaitingPrice1 = State()
    AwaitingPrice2 = State()
    AwaitingAdvantages = State()
    AwaitingDisadvantages = State()
    AwaitingBasicSkills = State()
    AwaitingMedia = State()
    AwaitingConfirmation = State()

class UserSearchStates(StatesGroup):
    """用户搜索流程状态"""
    AwaitingCity = State()
    AwaitingDistrict = State()
    ViewingMerchants = State()
    ViewingMerchantDetails = State()

class UserOrderStates(StatesGroup):
    """用户下单流程状态"""
    ConfirmingOrder = State()
    SelectingPrice = State()

class ReviewStates(StatesGroup):
    """评价流程状态"""
    AwaitingRating = State()
    AwaitingTextReview = State()



class AdminStates(StatesGroup):
    """
    管理员状态组
    处理管理员配置和管理功能
    """
    # 设置消息状态
    setting_message = State()
    
    # 配置按钮状态
    configuring_buttons = State()
    
    # 添加按钮状态
    adding_button = State()
    
    # 编辑按钮状态
    editing_button = State()
    
    # 查看统计筛选状态
    viewing_stats_filter = State()
    
    # 生成绑定码状态
    generating_binding_code = State()


class StateData:
    """
    状态数据管理类
    处理状态相关数据的序列化和反序列化
    """
    
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        """
        初始化状态数据
        
        Args:
            data: 状态数据字典
        """
        self.data = data or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def set(self, key: str, value: Any) -> None:
        """
        设置状态数据
        
        Args:
            key: 数据键
            value: 数据值
        """
        self.data[key] = value
        self.updated_at = datetime.now()
        logger.debug(f"状态数据已设置: {key} = {value}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取状态数据
        
        Args:
            key: 数据键
            default: 默认值
            
        Returns:
            数据值或默认值
        """
        return self.data.get(key, default)
    
    def remove(self, key: str) -> Any:
        """
        移除状态数据
        
        Args:
            key: 数据键
            
        Returns:
            被移除的值
        """
        value = self.data.pop(key, None)
        if value is not None:
            self.updated_at = datetime.now()
            logger.debug(f"状态数据已移除: {key}")
        return value
    
    def clear(self) -> None:
        """清空所有状态数据"""
        self.data.clear()
        self.updated_at = datetime.now()
        logger.debug("状态数据已清空")
    
    def to_json(self) -> str:
        """
        将状态数据序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        serializable_data = {
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
        return json.dumps(serializable_data, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'StateData':
        """
        从JSON字符串反序列化状态数据
        
        Args:
            json_str: JSON字符串
            
        Returns:
            StateData实例
        """
        try:
            data_dict = json.loads(json_str)
            instance = cls(data_dict.get("data", {}))
            
            # 恢复时间戳
            if "created_at" in data_dict:
                instance.created_at = datetime.fromisoformat(data_dict["created_at"])
            if "updated_at" in data_dict:
                instance.updated_at = datetime.fromisoformat(data_dict["updated_at"])
                
            return instance
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"状态数据反序列化失败: {e}")
            return cls()


class StateValidator:
    """
    状态转换验证器
    验证状态转换的合法性和错误恢复
    """
    
    # 定义允许的状态转换映射
    ALLOWED_TRANSITIONS = {
        # 用户状态转换
        UserStates.waiting_for_merchant_selection: [
            UserStates.in_conversation,
            UserStates.selecting_service
        ],
        UserStates.in_conversation: [
            UserStates.selecting_service,
            UserStates.waiting_for_merchant_selection
        ],
        UserStates.selecting_service: [
            UserStates.filling_appointment_info,
            UserStates.in_conversation,
            UserStates.waiting_for_merchant_selection
        ],
        UserStates.filling_appointment_info: [
            UserStates.confirming_order,
            UserStates.selecting_service
        ],
        UserStates.confirming_order: [
            UserStates.waiting_for_merchant_selection,
            UserStates.selecting_service
        ],
        
        # 商户状态转换
        MerchantStates.entering_binding_code: [
            MerchantStates.selecting_region
        ],
        MerchantStates.selecting_region: [
            MerchantStates.selecting_category,
            MerchantStates.entering_binding_code
        ],
        MerchantStates.selecting_category: [
            MerchantStates.entering_name,
            MerchantStates.selecting_region
        ],
        MerchantStates.entering_name: [
            MerchantStates.entering_contact_info,
            MerchantStates.selecting_category
        ],
        MerchantStates.entering_contact_info: [
            MerchantStates.confirming_profile,
            MerchantStates.entering_name
        ],
        MerchantStates.confirming_profile: [
            MerchantStates.editing_profile,
            MerchantStates.entering_binding_code  # 重新开始
        ],
        MerchantStates.editing_profile: [
            MerchantStates.confirming_profile,
            MerchantStates.selecting_region,
            MerchantStates.selecting_category,
            MerchantStates.entering_name,
            MerchantStates.entering_contact_info
        ],
        
        # 管理员状态转换
        AdminStates.setting_message: [
            AdminStates.configuring_buttons
        ],
        AdminStates.configuring_buttons: [
            AdminStates.adding_button,
            AdminStates.editing_button,
            AdminStates.setting_message
        ],
        AdminStates.adding_button: [
            AdminStates.configuring_buttons
        ],
        AdminStates.editing_button: [
            AdminStates.configuring_buttons
        ],
        AdminStates.viewing_stats_filter: [],
        AdminStates.generating_binding_code: []
    }
    
    @classmethod
    def is_valid_transition(cls, from_state: State, to_state: State) -> bool:
        """
        验证状态转换是否合法
        
        Args:
            from_state: 源状态
            to_state: 目标状态
            
        Returns:
            是否为合法转换
        """
        if from_state is None:
            return True  # 从空状态可以转换到任何状态
        
        allowed_states = cls.ALLOWED_TRANSITIONS.get(from_state, [])
        is_valid = to_state in allowed_states
        
        if not is_valid:
            logger.warning(f"无效的状态转换: {from_state} -> {to_state}")
        else:
            logger.debug(f"有效的状态转换: {from_state} -> {to_state}")
            
        return is_valid
    
    @classmethod
    def get_recovery_state(cls, user_type: str, current_state: Optional[State] = None) -> State:
        """
        获取错误恢复状态
        
        Args:
            user_type: 用户类型 ('user', 'merchant', 'admin')
            current_state: 当前状态
            
        Returns:
            恢复状态
        """
        recovery_states = {
            'user': UserStates.waiting_for_merchant_selection,
            'merchant': MerchantStates.entering_binding_code,
            'admin': None  # 管理员没有默认恢复状态
        }
        
        recovery_state = recovery_states.get(user_type)
        logger.info(f"为用户类型 {user_type} 获取恢复状态: {recovery_state}")
        
        return recovery_state


class StateManager:
    """
    状态管理器
    提供状态持久化和管理功能
    """
    
    def __init__(self, db_manager):
        """
        初始化状态管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
        self.state_timeout = timedelta(hours=1)  # 状态超时时间
    
    async def save_state(self, user_id: int, state: State, data: StateData) -> bool:
        """
        保存用户状态到数据库
        
        Args:
            user_id: 用户ID
            state: 状态对象
            data: 状态数据
            
        Returns:
            是否保存成功
        """
        try:
            state_name = f"{state.group.__name__}:{state.state}" if state else None
            data_json = data.to_json()
            
            query = """
                INSERT OR REPLACE INTO fsm_states (user_id, state, data, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            await self.db_manager.execute_query(query, (user_id, state_name, data_json))
            logger.debug(f"用户 {user_id} 状态已保存: {state_name}")
            return True
            
        except Exception as e:
            logger.error(f"保存用户 {user_id} 状态失败: {e}")
            return False
    
    async def load_state(self, user_id: int) -> tuple[Optional[State], StateData]:
        """
        从数据库加载用户状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            状态对象和状态数据的元组
        """
        try:
            query = """
                SELECT state, data, updated_at FROM fsm_states 
                WHERE user_id = ?
            """
            
            result = await self.db_manager.fetch_one(query, (user_id,))
            
            if not result:
                logger.debug(f"用户 {user_id} 没有保存的状态")
                return None, StateData()
            
            state_name, data_json, updated_at = result
            
            # 检查状态是否过期
            if self._is_state_expired(updated_at):
                logger.info(f"用户 {user_id} 的状态已过期，清除状态")
                await self.clear_state(user_id)
                return None, StateData()
            
            # 解析状态
            state = self._parse_state_name(state_name)
            data = StateData.from_json(data_json) if data_json else StateData()
            
            logger.debug(f"用户 {user_id} 状态已加载: {state_name}")
            return state, data
            
        except Exception as e:
            logger.error(f"加载用户 {user_id} 状态失败: {e}")
            return None, StateData()
    
    async def clear_state(self, user_id: int) -> bool:
        """
        清除用户状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否清除成功
        """
        try:
            query = "DELETE FROM fsm_states WHERE user_id = ?"
            await self.db_manager.execute_query(query, (user_id,))
            logger.debug(f"用户 {user_id} 状态已清除")
            return True
            
        except Exception as e:
            logger.error(f"清除用户 {user_id} 状态失败: {e}")
            return False
    
    async def cleanup_expired_states(self) -> int:
        """
        清理过期的状态
        
        Returns:
            清理的状态数量
        """
        try:
            cutoff_time = datetime.now() - self.state_timeout
            query = """
                DELETE FROM fsm_states 
                WHERE updated_at < ?
            """
            
            result = await self.db_manager.execute_query(
                query, 
                (cutoff_time.isoformat(),)
            )
            
            # 获取删除的行数（这需要数据库管理器支持）
            cleaned_count = result if isinstance(result, int) else 0
            logger.info(f"已清理 {cleaned_count} 个过期状态")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理过期状态失败: {e}")
            return 0
    
    def _is_state_expired(self, updated_at_str: str) -> bool:
        """
        检查状态是否过期
        
        Args:
            updated_at_str: 更新时间字符串
            
        Returns:
            是否过期
        """
        try:
            updated_at = datetime.fromisoformat(updated_at_str)
            return datetime.now() - updated_at > self.state_timeout
        except ValueError:
            return True  # 如果时间格式错误，认为已过期
    
    def _parse_state_name(self, state_name: str) -> Optional[State]:
        """
        解析状态名称为状态对象
        
        Args:
            state_name: 状态名称字符串
            
        Returns:
            状态对象或None
        """
        if not state_name:
            return None
        
        try:
            group_name, state_name_part = state_name.split(':', 1)
            
            # 根据组名获取对应的状态组
            state_groups = {
                'UserStates': UserStates,
                'MerchantStates': MerchantStates,
                'AdminStates': AdminStates
            }
            
            state_group = state_groups.get(group_name)
            if not state_group:
                logger.warning(f"未知的状态组: {group_name}")
                return None
            
            # 获取状态对象
            return getattr(state_group, state_name_part, None)
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"解析状态名称失败: {state_name}, 错误: {e}")
            return None


# 状态相关的工具函数
def get_user_type_from_state(state: State) -> Optional[str]:
    """
    从状态对象获取用户类型
    
    Args:
        state: 状态对象
        
    Returns:
        用户类型字符串或None
    """
    if not state:
        return None
    
    group_name = state.group.__name__
    type_mapping = {
        'UserStates': 'user',
        'MerchantStates': 'merchant',
        'AdminStates': 'admin'
    }
    
    return type_mapping.get(group_name)


def is_merchant_registration_state(state: State) -> bool:
    """
    检查是否为商户注册相关状态
    
    Args:
        state: 状态对象
        
    Returns:
        是否为商户注册状态
    """
    if not state or not isinstance(state.group, type(MerchantStates)):
        return False
    
    registration_states = [
        MerchantStates.entering_binding_code,
        MerchantStates.selecting_region,
        MerchantStates.selecting_category,
        MerchantStates.entering_name,
        MerchantStates.entering_contact_info,
        MerchantStates.confirming_profile
    ]
    
    return state in registration_states


def is_admin_configuration_state(state: State) -> bool:
    """
    检查是否为管理员配置相关状态
    
    Args:
        state: 状态对象
        
    Returns:
        是否为管理员配置状态
    """
    if not state or not isinstance(state.group, type(AdminStates)):
        return False
    
    config_states = [
        AdminStates.setting_message,
        AdminStates.configuring_buttons,
        AdminStates.adding_button,
        AdminStates.editing_button
    ]
    
    return state in config_states
