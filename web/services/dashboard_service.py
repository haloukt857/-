# -*- coding: utf-8 -*-
"""
仪表板服务
从app.py.old中提取的仪表板业务逻辑，提供统计数据聚合和缓存管理
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

# 导入数据库管理器
from database.db_merchants import merchant_manager
from database.db_regions import region_manager
from database.db_users import user_manager
from database.db_incentives import incentive_manager
from database.db_reviews import review_manager
from database.db_binding_codes import binding_codes_manager
from database.db_media import media_db
from database.db_orders import OrderManager

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)

# 实例化管理器
order_manager = OrderManager()


class DashboardService:
    """仪表板服务类"""
    
    # 缓存命名空间
    CACHE_NAMESPACE = "dashboard"
    CACHE_KEY_STATS = "main_stats"
    
    @staticmethod
    async def get_dashboard_data(force_refresh: bool = False) -> Dict[str, Any]:
        """
        获取仪表板统计数据
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            dict: 仪表板数据
        """
        try:
            if force_refresh:
                CacheService.delete(DashboardService.CACHE_NAMESPACE, DashboardService.CACHE_KEY_STATS)
            
            # 尝试从缓存获取
            cached_data = CacheService.get(DashboardService.CACHE_NAMESPACE, DashboardService.CACHE_KEY_STATS)
            if cached_data is not None:
                logger.debug("仪表板数据缓存命中")
                return cached_data
            
            # 缓存未命中，重新获取数据
            dashboard_data = await DashboardService._fetch_dashboard_data()
            
            # 设置缓存
            CacheService.set(
                DashboardService.CACHE_NAMESPACE,
                DashboardService.CACHE_KEY_STATS,
                dashboard_data,
                CacheService.DASHBOARD_CACHE_TTL
            )
            
            logger.info("仪表板数据已更新并缓存")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"获取仪表板数据失败: {e}")
            return DashboardService._get_default_dashboard_data()
    
    @staticmethod
    async def _fetch_dashboard_data() -> Dict[str, Any]:
        """获取实际的仪表板数据"""
        try:
            # 商户统计数据
            merchant_stats = await DashboardService._get_merchant_statistics()
            
            # 评价统计数据
            review_stats = await DashboardService._get_review_statistics()
            
            # 绑定码统计数据
            binding_stats = await DashboardService._get_binding_statistics()
            
            # 地区统计数据
            region_stats = await DashboardService._get_region_statistics()
            
            # 用户统计数据
            user_stats = await DashboardService._get_user_statistics()
            
            # 订单统计数据
            order_stats = await DashboardService._get_order_statistics()
            
            # 系统统计数据
            system_stats = await DashboardService._get_system_statistics()
            
            return {
                'merchants': merchant_stats,
                'reviews': review_stats,
                'binding_codes': binding_stats,
                'regions': region_stats,
                'users': user_stats,
                'orders': order_stats,
                'system': system_stats,
                'last_updated': datetime.now().isoformat(),
                'cache_info': {
                    'cached_at': time.time(),
                    'ttl': CacheService.DASHBOARD_CACHE_TTL
                }
            }
            
        except Exception as e:
            logger.error(f"获取仪表板详细数据失败: {e}")
            raise
    
    @staticmethod
    async def _get_merchant_statistics() -> Dict[str, Any]:
        """获取商户统计数据"""
        try:
            merchant_stats = await merchant_manager.get_merchant_statistics()
            return {
                'total': merchant_stats.get('total', 0),
                'approved': merchant_stats.get('approved', 0),
                'pending': merchant_stats.get('pending', 0),
                'published': merchant_stats.get('published', 0),
                'expired': merchant_stats.get('expired', 0),
                'approval_rate': merchant_stats.get('approval_rate', 0.0)
            }
        except Exception as e:
            logger.error(f"获取商户统计数据失败: {e}")
            return {
                'total': 0, 'approved': 0, 'pending': 0, 
                'published': 0, 'expired': 0, 'approval_rate': 0.0
            }
    
    @staticmethod
    async def _get_review_statistics() -> Dict[str, Any]:
        """获取评价统计数据"""
        try:
            # 统一口径：以 is_confirmed_by_admin=1 AND is_active=1 AND is_deleted=0 为准
            review_total = await review_manager.count_reviews()
            review_avg = await review_manager.get_average_rating()
            confirmed_count = await review_manager.count_confirmed_reviews()
            
            return {
                'total': review_total,
                'average_rating': review_avg,
                'confirmed_count': confirmed_count,
                'pending_count': max(0, (review_total or 0) - (confirmed_count or 0))
            }
        except Exception as e:
            logger.error(f"获取评价统计数据失败: {e}")
            return {
                'total': 0, 'average_rating': 0.0,
                'confirmed_count': 0, 'pending_count': 0
            }
    
    @staticmethod
    async def _get_binding_statistics() -> Dict[str, Any]:
        """获取绑定码统计数据"""
        try:
            binding_stats = await binding_codes_manager.get_binding_code_statistics()
            return {
                'total_codes': binding_stats.get('total_codes', 0),
                'used_codes': binding_stats.get('used_codes', 0),
                'unused_codes': binding_stats.get('unused_codes', 0),
                'usage_rate': binding_stats.get('usage_rate', 0.0)
            }
        except Exception as e:
            logger.error(f"获取绑定码统计数据失败: {e}")
            return {
                'total_codes': 0, 'used_codes': 0, 
                'unused_codes': 0, 'usage_rate': 0.0
            }
    
    @staticmethod
    async def _get_region_statistics() -> Dict[str, Any]:
        """获取地区统计数据"""
        try:
            cities = await region_manager.get_all_cities()
            districts = await region_manager.get_all_districts()
            
            return {
                'total_cities': len(cities),
                'total_districts': len(districts),
                'cities': cities[:10],  # 只返回前10个城市用于显示
                'districts': districts[:20]  # 只返回前20个区县用于显示
            }
        except Exception as e:
            logger.error(f"获取地区统计数据失败: {e}")
            return {
                'total_cities': 0, 'total_districts': 0,
                'cities': [], 'districts': []
            }
    
    @staticmethod
    async def _get_user_statistics() -> Dict[str, Any]:
        """获取用户统计数据"""
        try:
            user_stats = await user_manager.get_user_statistics()
            return {
                'total': user_stats.get('total', 0),
                'active': user_stats.get('active', 0),
                'by_level': user_stats.get('by_level', {}),
                'top_users': user_stats.get('top_users', [])[:5]  # 前5名用户
            }
        except Exception as e:
            logger.error(f"获取用户统计数据失败: {e}")
            return {
                'total': 0, 'active': 0,
                'by_level': {}, 'top_users': []
            }
    
    @staticmethod
    async def _get_order_statistics() -> Dict[str, Any]:
        """获取订单统计数据"""
        try:
            order_stats = await order_manager.get_order_statistics()
            return {
                'total': order_stats.get('total', 0),
                'completed': order_stats.get('completed', 0),
                'pending': order_stats.get('pending', 0),
                'reviewed': order_stats.get('reviewed', 0),
                'completion_rate': order_stats.get('completion_rate', 0.0)
            }
        except Exception as e:
            logger.error(f"获取订单统计数据失败: {e}")
            return {
                'total': 0, 'completed': 0, 'pending': 0,
                'reviewed': 0, 'completion_rate': 0.0
            }
    
    @staticmethod
    async def _get_system_statistics() -> Dict[str, Any]:
        """获取系统统计数据"""
        try:
            # 模板数量
            template_count = 0
            try:
                from database.db_templates import template_manager
                templates = await template_manager.get_all_templates()
                template_count = len(templates)
            except:
                pass
            
            # 缓存统计
            cache_stats = CacheService.get_cache_stats()
            
            return {
                'template_count': template_count,
                'cache_stats': cache_stats,
                'uptime': time.time(),  # 简单的运行时间标记
                'version': '2.0.0'
            }
        except Exception as e:
            logger.error(f"获取系统统计数据失败: {e}")
            return {
                'template_count': 0,
                'cache_stats': {},
                'uptime': time.time(),
                'version': '2.0.0'
            }
    
    @staticmethod
    def _get_default_dashboard_data() -> Dict[str, Any]:
        """获取默认的仪表板数据（错误时使用）"""
        return {
            'merchants': {'total': 0, 'approved': 0, 'pending': 0, 'published': 0, 'expired': 0, 'approval_rate': 0.0},
            'reviews': {'total': 0, 'average_rating': 0.0, 'confirmed_count': 0, 'pending_count': 0},
            'binding_codes': {'total_codes': 0, 'used_codes': 0, 'unused_codes': 0, 'usage_rate': 0.0},
            'regions': {'total_cities': 0, 'total_districts': 0, 'cities': [], 'districts': []},
            'users': {'total': 0, 'active': 0, 'by_level': {}, 'top_users': []},
            'orders': {'total': 0, 'completed': 0, 'pending': 0, 'reviewed': 0, 'completion_rate': 0.0},
            'system': {'template_count': 0, 'cache_stats': {}, 'uptime': time.time(), 'version': '2.0.0'},
            'last_updated': datetime.now().isoformat(),
            'error': True,
            'cache_info': {'cached_at': 0, 'ttl': 0}
        }
    
    @staticmethod
    async def get_performance_metrics() -> Dict[str, Any]:
        """获取性能指标"""
        try:
            cache_stats = CacheService.get_cache_stats()
            
            # 清理过期缓存
            cleaned_count = CacheService.cleanup_expired()
            
            return {
                'cache_performance': cache_stats,
                'cleaned_expired_items': cleaned_count,
                'memory_usage': {
                    'cache_size_mb': cache_stats.get('cache_size_mb', 0),
                    'active_entries': cache_stats.get('active_entries', 0)
                },
                'dashboard_cache': {
                    'exists': CacheService.exists(DashboardService.CACHE_NAMESPACE, DashboardService.CACHE_KEY_STATS),
                    'ttl': CacheService.DASHBOARD_CACHE_TTL
                }
            }
            
        except Exception as e:
            logger.error(f"获取性能指标失败: {e}")
            return {
                'cache_performance': {},
                'cleaned_expired_items': 0,
                'memory_usage': {'cache_size_mb': 0, 'active_entries': 0},
                'dashboard_cache': {'exists': False, 'ttl': 0},
                'error': str(e)
            }
    
    @staticmethod
    async def refresh_cache() -> Dict[str, Any]:
        """刷新缓存"""
        try:
            # 清除仪表板缓存
            deleted_count = CacheService.clear_namespace(DashboardService.CACHE_NAMESPACE)
            
            # 重新获取数据
            new_data = await DashboardService.get_dashboard_data(force_refresh=True)
            
            return {
                'success': True,
                'deleted_entries': deleted_count,
                'cache_refreshed': True,
                'data_updated': 'last_updated' in new_data
            }
            
        except Exception as e:
            logger.error(f"刷新缓存失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'deleted_entries': 0,
                'cache_refreshed': False,
                'data_updated': False
            }
