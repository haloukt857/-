# -*- coding: utf-8 -*-
"""
订单管理服务
从orders_v2.py.old和orders_routes_v2.py.old中提取的订单管理业务逻辑
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# 导入数据库管理器
from database.db_orders import OrderManager
from database.db_merchants import merchant_manager
from database.db_users import user_manager
from database.db_reviews import ReviewManager
from utils.enums import ORDER_STATUS

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)

# 实例化管理器
order_manager = OrderManager()
review_manager = ReviewManager()


class OrderMgmtService:
    """订单管理服务类"""
    
    CACHE_NAMESPACE = "order_mgmt"
    
    # 订单状态映射（与旧版orders_routes_v2.py保持一致）
    STATUS_DISPLAY_MAP = {
        "尝试预约": "尝试预约",
        "已完成": "已完成",
        "已评价": "已评价",
        "双方评价": "双方评价",
        "单方评价": "单方评价",
    }
    
    STATUS_COLORS = {
        "尝试预约": "badge-warning",
        "已完成": "badge-success",
        "已评价": "badge-info",
        "双方评价": "badge-primary",
        "单方评价": "badge-secondary",
    }
    
    STATUS_ICONS = {
        "尝试预约": "⏳",
        "已完成": "✅",
        "已评价": "⭐",
        "双方评价": "🤝",
        "单方评价": "📝",
    }
    
    @staticmethod
    async def get_orders_list(
        status_filter: Optional[str] = None,
        merchant_filter: Optional[str] = None,
        user_filter: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        获取订单列表
        
        Args:
            status_filter: 状态筛选
            merchant_filter: 商户筛选
            user_filter: 用户筛选
            date_from: 开始日期
            date_to: 结束日期
            search_query: 搜索关键词
            page: 页码
            per_page: 每页数量
            
        Returns:
            dict: 订单列表数据
        """
        try:
            # 直接使用OrderManager支持的参数格式
            # 获取订单数据 - 使用实际存在的方法
            orders = await order_manager.get_orders(
                status=status_filter,
                merchant_id=int(merchant_filter) if merchant_filter else None,
                user_id=int(user_filter) if user_filter else None,
                date_from=date_from,
                date_to=date_to,
                limit=per_page,
                offset=(page - 1) * per_page
            )
            
            # 获取总数 - 使用实际存在的方法
            total_orders = await order_manager.count_orders(
                status=status_filter,
                merchant_id=int(merchant_filter) if merchant_filter else None,
                user_id=int(user_filter) if user_filter else None,
                date_from=date_from,
                date_to=date_to
            )
            
            # 获取订单统计（添加今日订单统计）
            order_stats = await OrderMgmtService._get_order_statistics()
            today_orders = await OrderMgmtService._get_today_orders_count()
            order_stats['today_orders'] = today_orders
            
            # 获取商户和用户列表用于筛选
            merchants = await merchant_manager.get_all_merchants()
            from database.db_users import user_manager as user_mgr
            users = await user_mgr.get_all_users()
            
            return {
                'orders': orders,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_orders,
                    'pages': (total_orders + per_page - 1) // per_page
                },
                'filters': {
                    'status_filter': status_filter,
                    'merchant_filter': merchant_filter,
                    'user_filter': user_filter,
                    'date_from': date_from,
                    'date_to': date_to,
                    'search_query': search_query
                },
                'merchants': merchants[:100],  # 限制数量以提升性能
                'users': users[:100],  # 限制数量以提升性能
                'statistics': order_stats,
                'status_options': OrderMgmtService.STATUS_DISPLAY_MAP,
                'status_colors': OrderMgmtService.STATUS_COLORS,
                'status_icons': OrderMgmtService.STATUS_ICONS,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取订单列表失败: {e}")
            return {
                'orders': [],
                'pagination': {'page': page, 'per_page': per_page, 'total': 0, 'pages': 0},
                'filters': {},
                'merchants': [],
                'users': [],
                'statistics': {
                    'total_orders': 0,
                    'pending_orders': 0,
                    'completed_orders': 0,
                    'cancelled_orders': 0
                },
                'status_options': {},
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_order_detail(order_id: int) -> Dict[str, Any]:
        """
        获取订单详情
        
        Args:
            order_id: 订单ID
            
        Returns:
            dict: 订单详情数据
        """
        try:
            order = await order_manager.get_order_by_id(order_id)
            if not order:
                return {'success': False, 'error': '订单不存在'}
            
            # 获取商户信息
            merchant = await merchant_manager.get_merchant_by_id(order.get('merchant_id'))
            if not merchant:
                merchant = {}
            
            # 获取用户信息
            user = await user_manager.get_user_profile(order.get('user_id'))
            if not user:
                user = {}
            
            # 获取相关评价
            reviews = await review_manager.get_reviews_by_order_id(order_id)
            
            return {
                'order': order,
                'merchant': merchant,
                'user': user,
                'reviews': reviews,
                'status_info': {
                    'display_name': OrderMgmtService.STATUS_DISPLAY_MAP.get(order.get('status'), '未知'),
                    'color': OrderMgmtService.STATUS_COLORS.get(order.get('status'), 'ghost'),
                    'icon': OrderMgmtService.STATUS_ICONS.get(order.get('status'), '❓')
                },
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取订单详情失败: order_id={order_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_order_status(order_id: int, status: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        更新订单状态
        
        Args:
            order_id: 订单ID
            status: 新状态
            notes: 备注
            
        Returns:
            dict: 更新结果
        """
        try:
            # 验证状态有效性
            if status not in [s.value for s in ORDER_STATUS]:
                return {'success': False, 'error': '无效的状态值'}
            
            result = await order_manager.update_order_status(order_id, status, notes)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(OrderMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                
                logger.info(f"订单状态更新成功: order_id={order_id}, status={status}")
                return {'success': True, 'message': '订单状态更新成功'}
            else:
                return {'success': False, 'error': '订单状态更新失败'}
                
        except Exception as e:
            logger.error(f"更新订单状态失败: order_id={order_id}, status={status}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_order_info(order_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新订单信息
        
        Args:
            order_id: 订单ID
            data: 更新数据
            
        Returns:
            dict: 更新结果
        """
        try:
            result = await order_manager.update_order(order_id, data)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(OrderMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"订单信息更新成功: order_id={order_id}")
                return {'success': True, 'message': '订单信息更新成功'}
            else:
                return {'success': False, 'error': '订单信息更新失败'}
                
        except Exception as e:
            logger.error(f"更新订单信息失败: order_id={order_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def delete_order(order_id: int) -> Dict[str, Any]:
        """
        删除订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            dict: 删除结果
        """
        try:
            result = await order_manager.delete_order(order_id)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(OrderMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                
                logger.info(f"订单删除成功: order_id={order_id}")
                return {'success': True, 'message': '订单删除成功'}
            else:
                return {'success': False, 'error': '订单删除失败'}
                
        except Exception as e:
            logger.error(f"删除订单失败: order_id={order_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def batch_update_status(order_ids: List[int], status: str) -> Dict[str, Any]:
        """
        批量更新订单状态
        
        Args:
            order_ids: 订单ID列表
            status: 新状态
            
        Returns:
            dict: 批量更新结果
        """
        try:
            if not order_ids:
                return {'success': False, 'error': '未选择订单'}
            
            if status not in [s.value for s in ORDER_STATUS]:
                return {'success': False, 'error': '无效的状态值'}
            
            success_count = 0
            failed_count = 0
            errors = []
            
            for order_id in order_ids:
                try:
                    result = await order_manager.update_order_status(order_id, status)
                    if result:
                        success_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"订单 {order_id} 更新失败")
                except Exception as e:
                    failed_count += 1
                    errors.append(f"订单 {order_id} 更新异常: {str(e)}")
            
            # 清除相关缓存
            if success_count > 0:
                CacheService.clear_namespace(OrderMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
            
            return {
                'success': success_count > 0,
                'success_count': success_count,
                'failed_count': failed_count,
                'errors': errors,
                'message': f'成功更新 {success_count} 个订单，失败 {failed_count} 个'
            }
            
        except Exception as e:
            logger.error(f"批量更新订单状态失败: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def get_order_analytics() -> Dict[str, Any]:
        """
        获取订单分析数据
        
        Returns:
            dict: 订单分析数据
        """
        try:
            cache_key = "order_analytics"
            cached_data = CacheService.get(OrderMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取订单分析数据
            analytics_data = {
                'total_orders': await order_manager.count_orders(),
                'orders_by_status': await OrderMgmtService._get_orders_by_status(),
                'orders_by_time': await OrderMgmtService._get_orders_by_time_period(),
                'completion_rate': await OrderMgmtService._calculate_completion_rate(),
                'average_order_value': await OrderMgmtService._calculate_average_order_value(),
                'top_merchants': await OrderMgmtService._get_top_merchants_by_orders(),
                'top_users': await OrderMgmtService._get_top_users_by_orders(),
                'trends': await OrderMgmtService._get_order_trends()
            }
            
            # 缓存10分钟
            CacheService.set(OrderMgmtService.CACHE_NAMESPACE, cache_key, analytics_data, 600)
            return analytics_data
            
        except Exception as e:
            logger.error(f"获取订单分析数据失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def _get_order_statistics() -> Dict[str, Any]:
        """获取订单统计"""
        try:
            cache_key = "order_stats"
            cached_stats = CacheService.get(OrderMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_stats is not None:
                return cached_stats
            
            stats = {
                'total_orders': await order_manager.count_orders(),
                'completed_orders': await order_manager.count_orders_by_status(ORDER_STATUS.COMPLETED.value),
                'pending_orders': await order_manager.count_orders_by_status(ORDER_STATUS.ATTEMPT_BOOKING.value),
                'reviewed_orders': await order_manager.count_orders_by_status(ORDER_STATUS.REVIEWED.value),
                'completion_rate': await OrderMgmtService._calculate_completion_rate()
            }
            
            # 缓存5分钟
            CacheService.set(OrderMgmtService.CACHE_NAMESPACE, cache_key, stats, 300)
            return stats
            
        except Exception as e:
            logger.error(f"获取订单统计失败: {e}")
            return {}
    
    @staticmethod
    async def _get_orders_by_status() -> Dict[str, int]:
        """按状态统计订单"""
        try:
            stats = {}
            for status in ORDER_STATUS:
                count = await order_manager.count_orders_by_status(status.value)
                stats[status.value] = count
            return stats
        except Exception as e:
            logger.error(f"按状态统计订单失败: {e}")
            return {}
    
    @staticmethod
    async def _get_orders_by_time_period() -> Dict[str, int]:
        """按时间段统计订单"""
        try:
            now = datetime.now()
            return {
                'today': await order_manager.count_orders_since(now.replace(hour=0, minute=0, second=0)),
                'this_week': await order_manager.count_orders_since(now - timedelta(days=7)),
                'this_month': await order_manager.count_orders_since(now - timedelta(days=30)),
                'this_year': await order_manager.count_orders_since(now.replace(month=1, day=1))
            }
        except Exception as e:
            logger.error(f"按时间段统计订单失败: {e}")
            return {}
    
    @staticmethod
    async def _calculate_completion_rate() -> float:
        """计算完成率"""
        try:
            total_orders = await order_manager.count_orders()
            completed_orders = await order_manager.count_orders_by_status(ORDER_STATUS.COMPLETED.value)
            return (completed_orders / total_orders * 100) if total_orders > 0 else 0.0
        except Exception as e:
            logger.error(f"计算完成率失败: {e}")
            return 0.0
    
    @staticmethod
    async def _calculate_average_order_value() -> float:
        """计算平均订单价值"""
        try:
            # TODO: 实现平均订单价值计算逻辑（如果订单有价值字段）
            return 0.0
        except Exception as e:
            logger.error(f"计算平均订单价值失败: {e}")
            return 0.0
    
    @staticmethod
    async def _get_top_merchants_by_orders(limit: int = 10) -> List[Dict[str, Any]]:
        """获取订单数最多的商户"""
        try:
            return await order_manager.get_top_merchants_by_order_count(limit)
        except Exception as e:
            logger.error(f"获取订单数最多的商户失败: {e}")
            return []
    
    @staticmethod
    async def _get_top_users_by_orders(limit: int = 10) -> List[Dict[str, Any]]:
        """获取订单数最多的用户"""
        try:
            return await order_manager.get_top_users_by_order_count(limit)
        except Exception as e:
            logger.error(f"获取订单数最多的用户失败: {e}")
            return []
    
    @staticmethod
    async def _get_order_trends() -> Dict[str, Any]:
        """获取订单趋势"""
        try:
            # 获取最近30天的每日订单数据
            daily_orders = await order_manager.get_daily_order_counts(30)
            
            return {
                'daily_orders': daily_orders,
                'growth_rate': await OrderMgmtService._calculate_growth_rate()
            }
        except Exception as e:
            logger.error(f"获取订单趋势失败: {e}")
            return {}
    
    @staticmethod
    async def _calculate_growth_rate() -> float:
        """计算增长率"""
        try:
            now = datetime.now()
            this_month = await order_manager.count_orders_since(now.replace(day=1))
            last_month = await order_manager.count_orders_in_range(
                now.replace(month=now.month-1, day=1) if now.month > 1 else now.replace(year=now.year-1, month=12, day=1),
                now.replace(day=1)
            )
            return ((this_month - last_month) / last_month * 100) if last_month > 0 else 0.0
        except Exception as e:
            logger.error(f"计算增长率失败: {e}")
            return 0.0
    
    @staticmethod
    async def _get_today_orders_count() -> int:
        """获取今日订单数量"""
        try:
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return await order_manager.count_orders_since(today_start)
        except Exception as e:
            logger.error(f"获取今日订单数量失败: {e}")
            return 0
    
    @staticmethod
    def get_status_color(status: str) -> str:
        """获取状态颜色"""
        return OrderMgmtService.STATUS_COLORS.get(status, "badge-ghost")
    
    @staticmethod
    def get_status_icon(status: str) -> str:
        """获取状态图标"""
        return OrderMgmtService.STATUS_ICONS.get(status, "❓")
    
    @staticmethod
    def get_status_display(status: str) -> str:
        """获取状态显示名称"""
        return OrderMgmtService.STATUS_DISPLAY_MAP.get(status, status)
