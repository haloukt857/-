"""
自动回复变量函数处理系统
提供消息中变量替换功能，支持用户信息、时间、自定义变量等
"""

import re
import logging
from typing import Dict, Any, Optional, Callable, Union, List
from datetime import datetime, time
from aiogram.types import User

# 配置日志
logger = logging.getLogger(__name__)

class VariableProcessor:
    """变量处理器类，负责消息中变量函数的替换"""
    
    def __init__(self):
        """初始化变量处理器"""
        self._variable_functions: Dict[str, Callable] = {}
        self._register_default_variables()
    
    def _register_default_variables(self):
        """注册默认的变量函数"""
        # 用户相关变量
        self._variable_functions['username'] = self._get_username
        self._variable_functions['user_id'] = self._get_user_id
        self._variable_functions['full_name'] = self._get_full_name
        self._variable_functions['first_name'] = self._get_first_name
        self._variable_functions['last_name'] = self._get_last_name
        
        # 时间相关变量
        self._variable_functions['current_time'] = self._get_current_time
        self._variable_functions['current_datetime'] = self._get_current_datetime
        self._variable_functions['date'] = self._get_current_date
        self._variable_functions['year'] = self._get_current_year
        self._variable_functions['month'] = self._get_current_month
        self._variable_functions['day'] = self._get_current_day
        self._variable_functions['weekday'] = self._get_weekday
        
        # 问候语变量
        self._variable_functions['greeting'] = self._get_greeting
        self._variable_functions['time_greeting'] = self._get_time_based_greeting
        
        # 特殊格式变量
        self._variable_functions['mention'] = self._get_user_mention
        self._variable_functions['user_link'] = self._get_user_link
    
    def process_message(self, message_content: str, user: User, context: Optional[Dict[str, Any]] = None) -> str:
        """
        处理消息中的变量替换
        
        Args:
            message_content: 原始消息内容
            user: Telegram用户对象
            context: 额外的上下文信息
            
        Returns:
            处理后的消息内容
        """
        try:
            if not message_content:
                return ""
            
            # 准备变量上下文
            variable_context = {
                'user': user,
                'context': context or {},
                'datetime': datetime.now()
            }
            
            # 查找所有变量标记 {variable_name}
            pattern = r'\{([^}]+)\}'
            
            def replace_variable(match):
                variable_name = match.group(1).strip().lower()
                return self._resolve_variable(variable_name, variable_context)
            
            # 替换所有变量
            processed_message = re.sub(pattern, replace_variable, message_content)
            
            logger.debug(f"消息变量处理完成: {message_content[:50]}...")
            return processed_message
            
        except Exception as e:
            logger.error(f"处理消息变量失败: {e}")
            # 返回原始消息而不是抛出异常，确保系统稳定性
            return message_content
    
    def _resolve_variable(self, variable_name: str, context: Dict[str, Any]) -> str:
        """
        解析单个变量
        
        Args:
            variable_name: 变量名称
            context: 变量上下文
            
        Returns:
            解析后的值
        """
        try:
            # 检查是否为注册的变量函数
            if variable_name in self._variable_functions:
                func = self._variable_functions[variable_name]
                result = func(context)
                return str(result) if result is not None else f"{{{variable_name}}}"
            
            # 检查是否为上下文变量
            if 'context' in context and variable_name in context['context']:
                return str(context['context'][variable_name])
            
            # 未找到变量，返回原始标记
            logger.warning(f"未知变量: {variable_name}")
            return f"{{{variable_name}}}"
            
        except Exception as e:
            logger.error(f"解析变量失败 {variable_name}: {e}")
            return f"{{{variable_name}}}"
    
    # ===== 用户相关变量函数 =====
    
    def _get_username(self, context: Dict[str, Any]) -> str:
        """获取用户名（@username）"""
        user = context.get('user')
        if user and user.username:
            return f"@{user.username}"
        return "用户"
    
    def _get_user_id(self, context: Dict[str, Any]) -> str:
        """获取用户ID"""
        user = context.get('user')
        return str(user.id) if user else "0"
    
    def _get_full_name(self, context: Dict[str, Any]) -> str:
        """获取用户全名"""
        user = context.get('user')
        if not user:
            return "用户"
        
        full_name = user.full_name or ""
        if not full_name.strip():
            # 如果没有全名，尝试组合名和姓
            parts = []
            if user.first_name:
                parts.append(user.first_name)
            if user.last_name:
                parts.append(user.last_name)
            full_name = " ".join(parts) if parts else "用户"
        
        return full_name
    
    def _get_first_name(self, context: Dict[str, Any]) -> str:
        """获取用户名"""
        user = context.get('user')
        return user.first_name if user and user.first_name else "用户"
    
    def _get_last_name(self, context: Dict[str, Any]) -> str:
        """获取用户姓"""
        user = context.get('user')
        return user.last_name if user and user.last_name else ""
    
    def _get_user_mention(self, context: Dict[str, Any]) -> str:
        """获取用户提及格式"""
        user = context.get('user')
        if not user:
            return "用户"
        
        if user.username:
            return f"@{user.username}"
        else:
            # 使用Telegram提及格式
            display_name = user.first_name or "用户"
            return f"[{display_name}](tg://user?id={user.id})"
    
    def _get_user_link(self, context: Dict[str, Any]) -> str:
        """获取用户链接"""
        user = context.get('user')
        if not user:
            return ""
        
        return f"tg://user?id={user.id}"
    
    # ===== 时间相关变量函数 =====
    
    def _get_current_time(self, context: Dict[str, Any]) -> str:
        """获取当前时间（HH:MM）"""
        dt = context.get('datetime', datetime.now())
        return dt.strftime("%H:%M")
    
    def _get_current_datetime(self, context: Dict[str, Any]) -> str:
        """获取当前日期时间"""
        dt = context.get('datetime', datetime.now())
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    def _get_current_date(self, context: Dict[str, Any]) -> str:
        """获取当前日期"""
        dt = context.get('datetime', datetime.now())
        return dt.strftime("%Y-%m-%d")
    
    def _get_current_year(self, context: Dict[str, Any]) -> str:
        """获取当前年份"""
        dt = context.get('datetime', datetime.now())
        return dt.strftime("%Y")
    
    def _get_current_month(self, context: Dict[str, Any]) -> str:
        """获取当前月份"""
        dt = context.get('datetime', datetime.now())
        return dt.strftime("%m")
    
    def _get_current_day(self, context: Dict[str, Any]) -> str:
        """获取当前日期"""
        dt = context.get('datetime', datetime.now())
        return dt.strftime("%d")
    
    def _get_weekday(self, context: Dict[str, Any]) -> str:
        """获取星期几（中文）"""
        dt = context.get('datetime', datetime.now())
        weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        return weekdays[dt.weekday()]
    
    # ===== 问候语相关变量函数 =====
    
    def _get_greeting(self, context: Dict[str, Any]) -> str:
        """获取通用问候语"""
        return "您好"
    
    def _get_time_based_greeting(self, context: Dict[str, Any]) -> str:
        """获取基于时间的问候语"""
        dt = context.get('datetime', datetime.now())
        hour = dt.hour
        
        if 5 <= hour < 9:
            return "早上好"
        elif 9 <= hour < 12:
            return "上午好"
        elif 12 <= hour < 14:
            return "中午好"
        elif 14 <= hour < 18:
            return "下午好"
        elif 18 <= hour < 22:
            return "晚上好"
        else:
            return "夜深了"
    
    # ===== 自定义变量管理 =====
    
    def register_variable(self, name: str, func: Callable[[Dict[str, Any]], str]):
        """
        注册自定义变量函数
        
        Args:
            name: 变量名称
            func: 变量处理函数，接收context参数，返回字符串
        """
        try:
            if not name or not isinstance(name, str):
                raise ValueError("变量名称必须是非空字符串")
            
            if not callable(func):
                raise ValueError("变量函数必须是可调用对象")
            
            name = name.lower().strip()
            
            # 检查是否与内置变量冲突
            if name in self._variable_functions:
                logger.warning(f"覆盖已存在的变量: {name}")
            
            self._variable_functions[name] = func
            logger.info(f"注册自定义变量成功: {name}")
            
        except Exception as e:
            logger.error(f"注册自定义变量失败: {e}")
            raise
    
    def unregister_variable(self, name: str) -> bool:
        """
        移除自定义变量
        
        Args:
            name: 变量名称
            
        Returns:
            是否成功移除
        """
        try:
            name = name.lower().strip()
            
            if name in self._variable_functions:
                del self._variable_functions[name]
                logger.info(f"移除自定义变量成功: {name}")
                return True
            else:
                logger.warning(f"变量不存在: {name}")
                return False
                
        except Exception as e:
            logger.error(f"移除自定义变量失败: {e}")
            return False
    
    def get_available_variables(self) -> Dict[str, str]:
        """
        获取所有可用变量及其描述
        
        Returns:
            变量名称和描述的字典
        """
        descriptions = {
            # 用户相关
            'username': '用户名（@username）',
            'user_id': '用户ID',
            'full_name': '用户全名',
            'first_name': '用户名',
            'last_name': '用户姓',
            'mention': '用户提及格式',
            'user_link': '用户链接',
            
            # 时间相关
            'current_time': '当前时间（HH:MM）',
            'current_datetime': '当前日期时间',
            'date': '当前日期',
            'year': '当前年份',
            'month': '当前月份',
            'day': '当前日期',
            'weekday': '星期几',
            
            # 问候语
            'greeting': '通用问候语',
            'time_greeting': '时间问候语',
        }
        
        return descriptions
    
    def validate_message_template(self, message_content: str) -> Dict[str, Any]:
        """
        验证消息模板中的变量
        
        Args:
            message_content: 消息内容
            
        Returns:
            验证结果字典，包含有效变量、无效变量等信息
        """
        try:
            if not message_content:
                return {
                    'is_valid': True,
                    'valid_variables': [],
                    'invalid_variables': [],
                    'total_variables': 0
                }
            
            # 查找所有变量
            pattern = r'\{([^}]+)\}'
            variables = re.findall(pattern, message_content)
            
            valid_variables = []
            invalid_variables = []
            
            for var in variables:
                var_name = var.strip().lower()
                if var_name in self._variable_functions:
                    valid_variables.append(var_name)
                else:
                    invalid_variables.append(var_name)
            
            return {
                'is_valid': len(invalid_variables) == 0,
                'valid_variables': valid_variables,
                'invalid_variables': invalid_variables,
                'total_variables': len(variables)
            }
            
        except Exception as e:
            logger.error(f"验证消息模板失败: {e}")
            return {
                'is_valid': False,
                'valid_variables': [],
                'invalid_variables': [],
                'total_variables': 0,
                'error': str(e)
            }
    
    def get_variable_buttons(self) -> List[Dict[str, str]]:
        """
        获取所有可用的变量按钮配置
        
        Returns:
            变量按钮配置列表
        """
        buttons = []
        
        # 从注册的变量函数中生成按钮
        for var_name in self._variable_functions.keys():
            buttons.append({
                'name': var_name,
                'description': f'插入变量 {{{var_name}}}'
            })
        
        return buttons

# ===== 管理界面快捷按钮配置 =====

class VariableButtonConfig:
    """变量函数快捷按钮配置"""
    
    @staticmethod
    def get_common_variable_buttons() -> List[Dict[str, str]]:
        """
        获取常用变量函数按钮配置
        
        Returns:
            按钮配置列表
        """
        return [
            {'name': '用户名', 'variable': '{username}', 'description': '插入用户@用户名'},
            {'name': '完整姓名', 'variable': '{full_name}', 'description': '插入用户完整姓名'},
            {'name': '用户ID', 'variable': '{user_id}', 'description': '插入用户ID'},
            {'name': '当前时间', 'variable': '{current_time}', 'description': '插入当前时间'},
            {'name': '当前日期', 'variable': '{date}', 'description': '插入当前日期'},
            {'name': '问候语', 'variable': '{time_greeting}', 'description': '插入时间问候语'},
            {'name': '提及用户', 'variable': '{mention}', 'description': '插入用户提及格式'},
            {'name': '星期几', 'variable': '{weekday}', 'description': '插入星期几'},
        ]
    
    @staticmethod
    def get_advanced_variable_buttons() -> List[Dict[str, str]]:
        """
        获取高级变量函数按钮配置
        
        Returns:
            高级按钮配置列表
        """
        return [
            {'name': '完整日期时间', 'variable': '{current_datetime}', 'description': '插入完整日期时间'},
            {'name': '用户链接', 'variable': '{user_link}', 'description': '插入用户链接'},
            {'name': '年份', 'variable': '{year}', 'description': '插入当前年份'},
            {'name': '月份', 'variable': '{month}', 'description': '插入当前月份'},
            {'name': '日期', 'variable': '{day}', 'description': '插入当前日期'},
            {'name': '名', 'variable': '{first_name}', 'description': '插入用户名'},
            {'name': '姓', 'variable': '{last_name}', 'description': '插入用户姓'},
            {'name': '通用问候', 'variable': '{greeting}', 'description': '插入通用问候语'},
        ]

# 创建全局实例
variable_processor = VariableProcessor()
variable_buttons = VariableButtonConfig()