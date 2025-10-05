# -*- coding: utf-8 -*-
"""
订阅验证管理服务
从subscription_v2.py.old中提取的订阅验证管理业务逻辑
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# 导入数据库管理器
from database.db_system_config import system_config_manager
from database.db_users import user_manager

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class SubscriptionMgmtService:
    """订阅验证管理服务类"""
    
    CACHE_NAMESPACE = "subscription_mgmt"
    DEFAULT_CONFIG = {"enabled": False, "required_subscriptions": []}

    # --- 统一字段约定 ---
    # 为避免“新旧字段并存”导致的运行时不一致，服务层统一使用并写入如下结构：
    #   required_subscriptions: [
    #       {"chat_id": str, "display_name": str, "join_link": str}
    #   ]
    # 历史可能存在的字段（channel_id/channel_name/channel_url）在入库前一律转换为上述标准键。

    @staticmethod
    def _normalize_subscription_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """将单个频道配置规范化为统一键名结构。

        返回的字典固定包含：chat_id, display_name, join_link。
        """
        return {
            'chat_id': item.get('chat_id') or item.get('channel_id') or item.get('id') or '',
            'display_name': item.get('display_name') or item.get('channel_name') or item.get('name') or '',
            'join_link': item.get('join_link') or item.get('channel_url') or item.get('url') or '',
        }

    @staticmethod
    def _normalize_required_list(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量规范化并去除明显空项。"""
        normalized = []
        for it in items or []:
            n = SubscriptionMgmtService._normalize_subscription_item(it)
            if n.get('chat_id'):
                normalized.append(n)
        return normalized
    
    @staticmethod
    async def get_subscription_dashboard() -> Dict[str, Any]:
        """
        获取订阅验证管理仪表板数据
        
        Returns:
            dict: 订阅验证仪表板数据
        """
        try:
            # 获取当前配置
            config = await system_config_manager.get_config(
                'subscription_verification_config',
                SubscriptionMgmtService.DEFAULT_CONFIG
            )
            # 规范化 required_subscriptions（避免历史数据中的旧字段影响展示层）
            if isinstance(config, dict):
                config['required_subscriptions'] = SubscriptionMgmtService._normalize_required_list(
                    config.get('required_subscriptions', [])
                )
            
            # 获取统计数据
            stats = await SubscriptionMgmtService._get_subscription_statistics()
            
            # 获取验证历史
            verification_history = await SubscriptionMgmtService._get_verification_history()
            
            return {
                'config': config,
                'statistics': stats,
                'verification_history': verification_history,
                'status': {
                    'enabled': config.get('enabled', False),
                    'required_channels': len(config.get('required_subscriptions', [])),
                    'total_subscribed_users': stats.get('total_subscribed', 0)
                },
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取订阅验证仪表板数据失败: {e}")
            return {
                'config': SubscriptionMgmtService.DEFAULT_CONFIG,
                'statistics': {},
                'verification_history': [],
                'status': {'enabled': False, 'required_channels': 0, 'total_subscribed_users': 0},
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_subscription_config() -> Dict[str, Any]:
        """
        获取订阅验证配置
        
        Returns:
            dict: 订阅验证配置
        """
        try:
            config = await system_config_manager.get_config(
                'subscription_verification_config',
                SubscriptionMgmtService.DEFAULT_CONFIG
            )
            if isinstance(config, dict):
                config['required_subscriptions'] = SubscriptionMgmtService._normalize_required_list(
                    config.get('required_subscriptions', [])
                )
            
            return {
                'config': config,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取订阅验证配置失败: {e}")
            return {
                'config': SubscriptionMgmtService.DEFAULT_CONFIG,
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def update_subscription_config(
        enabled: bool,
        required_subscriptions: List[Dict[str, str]],
        verification_message: Optional[str] = None,
        bypass_for_premium: bool = False
    ) -> Dict[str, Any]:
        """
        更新订阅验证配置
        
        Args:
            enabled: 是否启用订阅验证
            required_subscriptions: 必需的订阅列表
            verification_message: 验证消息
            bypass_for_premium: 高级用户是否跳过验证
            
        Returns:
            dict: 更新结果
        """
        try:
            new_config = {
                'enabled': enabled,
                # 入库前统一规范化字段，确保中间件直接可用
                'required_subscriptions': SubscriptionMgmtService._normalize_required_list(required_subscriptions),
                'verification_message': verification_message or '请先订阅必需的频道',
                'bypass_for_premium': bypass_for_premium,
                'updated_at': datetime.now().isoformat()
            }
            
            result = await system_config_manager.set_config(
                'subscription_verification_config',
                new_config
            )
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(SubscriptionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"订阅验证配置更新成功: enabled={enabled}, channels={len(required_subscriptions)}")
                return {'success': True, 'message': '订阅验证配置更新成功'}
            else:
                return {'success': False, 'error': '配置更新失败'}
                
        except Exception as e:
            logger.error(f"更新订阅验证配置失败: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def add_required_subscription(channel_id: str, channel_name: str, channel_url: str) -> Dict[str, Any]:
        """
        添加必需的订阅频道
        
        Args:
            channel_id: 频道ID
            channel_name: 频道名称
            channel_url: 频道URL
            
        Returns:
            dict: 添加结果
        """
        try:
            # 获取当前配置
            config = await system_config_manager.get_config(
                'subscription_verification_config',
                SubscriptionMgmtService.DEFAULT_CONFIG
            )
            
            # 统一字段（兼容旧参数名，但入库一律使用标准字段）
            required_subscriptions = SubscriptionMgmtService._normalize_required_list(
                config.get('required_subscriptions', [])
            )
            
            # 检查频道是否已存在
            # 以 chat_id 为唯一键进行去重
            if any(str(sub.get('chat_id')) == str(channel_id) for sub in required_subscriptions):
                return {'success': False, 'error': '该频道已在必需订阅列表中'}
            
            # 添加新频道
            required_subscriptions.append({
                'chat_id': channel_id,
                'display_name': channel_name,
                'join_link': channel_url,
                'added_at': datetime.now().isoformat()
            })
            
            config['required_subscriptions'] = required_subscriptions
            config['updated_at'] = datetime.now().isoformat()
            
            # 回写前保持整体结构规范
            config['required_subscriptions'] = SubscriptionMgmtService._normalize_required_list(required_subscriptions)
            result = await system_config_manager.set_config(
                'subscription_verification_config',
                config
            )
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(SubscriptionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"添加必需订阅频道成功: chat_id={channel_id}, name={channel_name}")
                return {'success': True, 'message': '必需订阅频道添加成功'}
            else:
                return {'success': False, 'error': '添加失败'}
                
        except Exception as e:
            logger.error(f"添加必需订阅频道失败: channel_id={channel_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def remove_required_subscription(channel_id: str) -> Dict[str, Any]:
        """
        移除必需的订阅频道
        
        Args:
            channel_id: 频道ID
            
        Returns:
            dict: 移除结果
        """
        try:
            # 获取当前配置
            config = await system_config_manager.get_config(
                'subscription_verification_config',
                SubscriptionMgmtService.DEFAULT_CONFIG
            )
            
            required_subscriptions = SubscriptionMgmtService._normalize_required_list(
                config.get('required_subscriptions', [])
            )
            
            # 查找并移除频道
            # 以 chat_id 匹配删除（兼容历史入库差异）
            updated_subscriptions = [sub for sub in required_subscriptions if str(sub.get('chat_id')) != str(channel_id)]
            
            if len(updated_subscriptions) == len(required_subscriptions):
                return {'success': False, 'error': '未找到指定的频道'}
            
            config['required_subscriptions'] = SubscriptionMgmtService._normalize_required_list(updated_subscriptions)
            config['updated_at'] = datetime.now().isoformat()
            
            result = await system_config_manager.set_config(
                'subscription_verification_config',
                config
            )
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(SubscriptionMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"移除必需订阅频道成功: chat_id={channel_id}")
                return {'success': True, 'message': '必需订阅频道移除成功'}
            else:
                return {'success': False, 'error': '移除失败'}
                
        except Exception as e:
            logger.error(f"移除必需订阅频道失败: channel_id={channel_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def verify_user_subscriptions(user_id: int) -> Dict[str, Any]:
        """
        验证用户订阅状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 验证结果
        """
        try:
            # 获取配置
            config = await system_config_manager.get_config(
                'subscription_verification_config',
                SubscriptionMgmtService.DEFAULT_CONFIG
            )
            
            if not config.get('enabled', False):
                return {
                    'verified': True,
                    'message': '订阅验证未启用',
                    'required_subscriptions': [],
                    'missing_subscriptions': []
                }
            
            # 获取用户信息
            user = await user_manager.get_user_profile(user_id)
            if not user:
                return {
                    'verified': False,
                    'message': '用户不存在',
                    'required_subscriptions': [],
                    'missing_subscriptions': []
                }
            
            # 检查是否为高级用户且可以跳过验证
            if config.get('bypass_for_premium', False) and user.get('is_premium', False):
                return {
                    'verified': True,
                    'message': '高级用户跳过订阅验证',
                    'required_subscriptions': [],
                    'missing_subscriptions': []
                }
            
            # 获取必需的订阅
            required_subscriptions = SubscriptionMgmtService._normalize_required_list(
                config.get('required_subscriptions', [])
            )
            if not required_subscriptions:
                return {
                    'verified': True,
                    'message': '无必需订阅要求',
                    'required_subscriptions': [],
                    'missing_subscriptions': []
                }
            
            # TODO: 实现实际的订阅状态检查逻辑
            # 这里需要调用Telegram API检查用户是否订阅了指定频道
            missing_subscriptions = []
            
            # 模拟订阅检查（实际实现需要Telegram Bot API）
            user_subscribed = user.get('is_subscribed', False)
            if not user_subscribed:
                missing_subscriptions = required_subscriptions
            
            is_verified = len(missing_subscriptions) == 0
            
            # 最小化修改：不落库用户订阅状态（数据库与方法未定义）。
            # 若后续需要持久化，请在 db_users.py 实现相应字段与方法后再恢复写入。
            
            return {
                'verified': is_verified,
                'message': '订阅验证通过' if is_verified else f'需要订阅 {len(missing_subscriptions)} 个频道',
                'required_subscriptions': required_subscriptions,
                'missing_subscriptions': missing_subscriptions
            }
            
        except Exception as e:
            logger.error(f"验证用户订阅状态失败: user_id={user_id}, error={e}")
            return {
                'verified': False,
                'message': '验证过程中出现错误',
                'required_subscriptions': [],
                'missing_subscriptions': [],
                'error': str(e)
            }
    
    @staticmethod
    async def get_subscription_analytics() -> Dict[str, Any]:
        """
        获取订阅验证分析数据
        
        Returns:
            dict: 订阅验证分析数据
        """
        try:
            cache_key = "subscription_analytics"
            cached_data = CacheService.get(SubscriptionMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取订阅分析数据
            analytics_data = {
                'total_users': await user_manager.count_users(),
                'subscribed_users': await SubscriptionMgmtService._count_subscribed_users(),
                'verification_rate': await SubscriptionMgmtService._calculate_verification_rate(),
                'subscription_trends': await SubscriptionMgmtService._get_subscription_trends(),
                'channel_performance': await SubscriptionMgmtService._get_channel_performance(),
                'verification_history': await SubscriptionMgmtService._get_verification_history()
            }
            
            # 缓存15分钟
            CacheService.set(SubscriptionMgmtService.CACHE_NAMESPACE, cache_key, analytics_data, 900)
            return analytics_data
            
        except Exception as e:
            logger.error(f"获取订阅验证分析数据失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def _get_subscription_statistics() -> Dict[str, Any]:
        """获取订阅统计"""
        try:
            cache_key = "subscription_stats"
            cached_stats = CacheService.get(SubscriptionMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_stats is not None:
                return cached_stats
            
            total_users = await user_manager.count_users()
            subscribed_users = await SubscriptionMgmtService._count_subscribed_users()
            
            stats = {
                'total_users': total_users,
                'total_subscribed': subscribed_users,
                'total_unsubscribed': total_users - subscribed_users,
                'subscription_rate': (subscribed_users / total_users * 100) if total_users > 0 else 0.0
            }
            
            # 缓存10分钟
            CacheService.set(SubscriptionMgmtService.CACHE_NAMESPACE, cache_key, stats, 600)
            return stats
            
        except Exception as e:
            logger.error(f"获取订阅统计失败: {e}")
            return {}
    
    @staticmethod
    async def _count_subscribed_users() -> int:
        """计算已订阅用户数"""
        try:
            return await user_manager.count_subscribed_users()
        except Exception as e:
            logger.error(f"计算已订阅用户数失败: {e}")
            return 0
    
    @staticmethod
    async def _calculate_verification_rate() -> float:
        """计算验证率"""
        try:
            total_users = await user_manager.count_users()
            subscribed_users = await SubscriptionMgmtService._count_subscribed_users()
            return (subscribed_users / total_users * 100) if total_users > 0 else 0.0
        except Exception as e:
            logger.error(f"计算验证率失败: {e}")
            return 0.0
    
    @staticmethod
    async def _get_subscription_trends() -> Dict[str, Any]:
        """获取订阅趋势"""
        try:
            # 获取最近30天的订阅数据
            now = datetime.now()
            trends = {}
            
            for days in [1, 7, 30]:
                date_threshold = now - timedelta(days=days)
                count = await user_manager.count_users_subscribed_since(date_threshold)
                trends[f'last_{days}_days'] = count
            
            return trends
        except Exception as e:
            logger.error(f"获取订阅趋势失败: {e}")
            return {}
    
    @staticmethod
    async def _get_channel_performance() -> List[Dict[str, Any]]:
        """获取频道表现"""
        try:
            # 获取配置中的频道
            config = await system_config_manager.get_config(
                'subscription_verification_config',
                SubscriptionMgmtService.DEFAULT_CONFIG
            )
            
            channels = SubscriptionMgmtService._normalize_required_list(
                config.get('required_subscriptions', [])
            )
            performance = []
            
            for channel in channels:
                # TODO: 实现频道订阅数统计逻辑
                performance.append({
                    'channel_id': channel.get('chat_id'),
                    'channel_name': channel.get('display_name'),
                    'subscriber_count': 0,  # 需要实际实现
                    'growth_rate': 0.0,  # 需要实际实现
                    'added_at': channel.get('added_at', '')
                })
            
            return performance
        except Exception as e:
            logger.error(f"获取频道表现失败: {e}")
            return []
    
    @staticmethod
    async def _get_verification_history(limit: int = 100) -> List[Dict[str, Any]]:
        """获取验证历史"""
        try:
            # TODO: 实现验证历史获取逻辑
            # 这里应该从日志或者专门的验证历史表中获取数据
            return []
        except Exception as e:
            logger.error(f"获取验证历史失败: {e}")
            return []
