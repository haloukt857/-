"""
自动回复消息处理器
处理用户消息的自动回复功能，包括触发词匹配、变量替换和回复发送
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

# 导入项目模块
from config import ADMIN_IDS
from database.db_auto_reply import AutoReplyManager, auto_reply_manager
from database.db_logs import ActivityLogsDatabase, ActionType
from utils.auto_reply_variables import VariableProcessor, variable_processor

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
auto_reply_router = Router()

class AutoReplyHandler:
    """自动回复处理器类"""
    
    def __init__(self, bot: Bot):
        """
        初始化自动回复处理器
        
        Args:
            bot: Telegram Bot实例
        """
        self.bot = bot
        self.variable_processor = variable_processor
        self.auto_reply_manager = auto_reply_manager
        
        # 缓存机制
        self._triggers_cache: List[Dict[str, Any]] = []
        self._cache_last_updated: Optional[datetime] = None
        self._cache_expiry_hours = 1  # 缓存1小时过期
        
        # 性能监控
        self._processing_stats = {
            'total_processed': 0,
            'matches_found': 0,
            'replies_sent': 0,
            'errors': 0
        }
    
    async def handle_text_message(self, message: Message, state: FSMContext):
        """
        处理文本消息的自动回复
        
        Args:
            message: 用户消息
            state: FSM状态上下文
        """
        try:
            # 性能计数
            self._processing_stats['total_processed'] += 1
            
            # 安全检查：只处理私聊消息
            if message.chat.type != 'private':
                return
            
            # 检查用户和消息有效性
            if not message.from_user or not message.text:
                return
            
            user = message.from_user
            user_message = message.text.strip()
            
            # 空消息检查
            if not user_message:
                return
            
            # 检查是否为系统命令或特殊触发词（优先级检查）
            if await self._is_system_command(user_message):
                logger.debug(f"跳过系统命令: {user_message[:20]}...")
                return
            
            # 检查FSM状态（如果用户在特定状态下，优先处理状态逻辑）
            current_state = await state.get_state()
            if current_state and await self._is_state_active(current_state):
                logger.debug(f"跳过FSM状态消息: {current_state}")
                return
            
            # 查找匹配的触发词
            matching_triggers = await self._find_matching_triggers(user_message)
            
            if not matching_triggers:
                return
            
            # 处理匹配的触发词（按优先级顺序）
            for trigger in matching_triggers:
                try:
                    await self._process_trigger(trigger, message, user)
                    self._processing_stats['matches_found'] += 1
                    
                    # 记录触发词使用
                    await auto_reply_manager.record_trigger_usage(trigger['id'], user.id)
                    
                    # 记录活动日志
                    await ActivityLogsDatabase.log_user_interaction(
                        user_id=user.id,
                        action=ActionType.AUTO_REPLY_TRIGGERED.value,
                        details={
                            'trigger_id': trigger['id'],
                            'trigger_text': trigger['trigger_text'],
                            'match_type': trigger['match_type'],
                            'user_message': user_message[:100]  # 限制长度
                        }
                    )
                    
                    # 只处理第一个匹配的触发词（按优先级）
                    break
                    
                except Exception as e:
                    logger.error(f"处理触发词失败，ID: {trigger['id']}, 错误: {e}")
                    self._processing_stats['errors'] += 1
                    continue
            
        except Exception as e:
            logger.error(f"处理自动回复消息失败: {e}")
            self._processing_stats['errors'] += 1
    
    async def _is_system_command(self, message_text: str) -> bool:
        """
        检查是否为系统命令或特殊触发词
        
        Args:
            message_text: 消息文本
            
        Returns:
            是否为系统命令
        """
        system_patterns = [
            '/start', '/help', '/cancel', '/stop',
            '上榜流程',  # 商户注册触发词
            '/set_button', '/view_stats', '/generate_code'  # 管理员命令
        ]
        
        message_lower = message_text.lower().strip()
        
        # 检查是否以系统命令开始
        for pattern in system_patterns:
            if message_lower.startswith(pattern.lower()):
                return True
        
        return False
    
    async def _is_state_active(self, state_name: str) -> bool:
        """
        检查FSM状态是否为需要特殊处理的状态
        
        Args:
            state_name: 状态名称
            
        Returns:
            是否为活跃状态
        """
        # 需要特殊处理的状态列表
        active_states = [
            'MerchantStates:entering_binding_code',
            'MerchantStates:selecting_region',
            'MerchantStates:selecting_category',
            'MerchantStates:entering_name',
            'MerchantStates:entering_contact_info',
            'MerchantStates:confirming_profile'
        ]
        
        return state_name in active_states
    
    async def _find_matching_triggers(self, message_text: str) -> List[Dict[str, Any]]:
        """
        查找匹配的触发词
        
        Args:
            message_text: 消息文本
            
        Returns:
            匹配的触发词列表
        """
        try:
            # 更新缓存（如果需要）
            await self._update_triggers_cache()
            
            # 使用数据库查找（更准确）
            matching_triggers = await auto_reply_manager.find_matching_triggers(message_text)
            
            return matching_triggers
            
        except Exception as e:
            logger.error(f"查找匹配触发词失败: {e}")
            return []
    
    async def _update_triggers_cache(self):
        """更新触发词缓存"""
        try:
            now = datetime.now()
            
            # 检查缓存是否需要更新
            if (self._cache_last_updated and 
                now - self._cache_last_updated < timedelta(hours=self._cache_expiry_hours)):
                return
            
            # 获取最新的触发词
            self._triggers_cache = await auto_reply_manager.get_all_active_triggers()
            self._cache_last_updated = now
            
            logger.debug(f"触发词缓存已更新，数量: {len(self._triggers_cache)}")
            
        except Exception as e:
            logger.error(f"更新触发词缓存失败: {e}")
    
    async def _process_trigger(self, trigger: Dict[str, Any], message: Message, user):
        """
        处理匹配的触发词
        
        Args:
            trigger: 触发词信息
            message: 原始消息
            user: 用户对象
        """
        try:
            # 获取触发词的回复消息
            reply_messages = await auto_reply_manager.get_messages_by_trigger(
                trigger['id'], 
                active_only=True
            )
            
            if not reply_messages:
                logger.warning(f"触发词无回复消息，ID: {trigger['id']}")
                return
            
            # 发送所有回复消息
            for reply_msg in reply_messages:
                try:
                    # 处理变量替换
                    processed_content = self.variable_processor.process_message(
                        reply_msg['message_content'], 
                        user
                    )
                    
                    # 发送回复
                    await message.answer(processed_content)
                    self._processing_stats['replies_sent'] += 1
                    
                    # 记录消息发送
                    await auto_reply_manager.record_message_sent(reply_msg['id'])
                    
                    logger.info(f"自动回复已发送，触发词: '{trigger['trigger_text']}', 用户: {user.id}")
                    
                    # 添加小延迟，避免消息发送过快
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"发送回复消息失败，消息ID: {reply_msg['id']}, 错误: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"处理触发词失败: {e}")
            raise
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """
        获取处理统计信息
        
        Returns:
            处理统计字典
        """
        return {
            'stats': self._processing_stats.copy(),
            'cache_info': {
                'cached_triggers': len(self._triggers_cache),
                'last_updated': self._cache_last_updated.isoformat() if self._cache_last_updated else None,
                'cache_age_hours': (
                    (datetime.now() - self._cache_last_updated).total_seconds() / 3600
                    if self._cache_last_updated else None
                )
            }
        }
    
    async def clear_cache(self):
        """清空缓存"""
        self._triggers_cache.clear()
        self._cache_last_updated = None
        logger.info("自动回复缓存已清空")
    
    async def reload_cache(self):
        """重新加载缓存"""
        await self.clear_cache()
        await self._update_triggers_cache()
        logger.info("自动回复缓存已重新加载")

# 创建处理器实例（需要在bot初始化后创建）
auto_reply_handler = None

def init_auto_reply_handler(bot: Bot):
    """
    初始化自动回复处理器
    
    Args:
        bot: Telegram Bot实例
    """
    global auto_reply_handler
    auto_reply_handler = AutoReplyHandler(bot)
    logger.info("自动回复处理器初始化完成")

# ===== 路由注册 =====

@auto_reply_router.message(F.text, F.chat.type == 'private')
async def handle_private_text_message(message: Message, state: FSMContext):
    """
    处理私聊文本消息（自动回复功能）
    
    注意：这个处理器优先级较低，会在其他特定处理器之后执行
    """
    if auto_reply_handler is None:
        logger.warning("自动回复处理器未初始化")
        return
    
    try:
        await auto_reply_handler.handle_text_message(message, state)
    except Exception as e:
        logger.error(f"自动回复处理器异常: {e}")

# ===== 管理员命令 =====

@auto_reply_router.message(F.text.startswith('/auto_reply_stats'), F.from_user.id.in_(ADMIN_IDS))
async def cmd_auto_reply_stats(message: Message):
    """管理员查看自动回复统计"""
    if auto_reply_handler is None:
        await message.answer("自动回复处理器未初始化")
        return
    
    try:
        stats = await auto_reply_handler.get_processing_stats()
        
        stats_text = f"""📊 自动回复统计

🔢 处理统计:
• 总处理消息数: {stats['stats']['total_processed']}
• 匹配次数: {stats['stats']['matches_found']}
• 发送回复数: {stats['stats']['replies_sent']}
• 错误次数: {stats['stats']['errors']}

💾 缓存信息:
• 缓存触发词数: {stats['cache_info']['cached_triggers']}
• 缓存更新时间: {stats['cache_info']['last_updated'] or '未更新'}
• 缓存年龄: {stats['cache_info']['cache_age_hours']:.2f}小时 (如果有)
"""
        
        await message.answer(stats_text)
        
    except Exception as e:
        logger.error(f"获取自动回复统计失败: {e}")
        await message.answer("获取统计信息失败")

@auto_reply_router.message(F.text.startswith('/auto_reply_reload'), F.from_user.id.in_(ADMIN_IDS))
async def cmd_auto_reply_reload(message: Message):
    """管理员重新加载自动回复缓存"""
    if auto_reply_handler is None:
        await message.answer("自动回复处理器未初始化")
        return
    
    try:
        await auto_reply_handler.reload_cache()
        await message.answer("✅ 自动回复缓存已重新加载")
    except Exception as e:
        logger.error(f"重新加载自动回复缓存失败: {e}")
        await message.answer("❌ 重新加载缓存失败")

def get_auto_reply_router() -> Router:
    """获取自动回复路由器"""
    return auto_reply_router