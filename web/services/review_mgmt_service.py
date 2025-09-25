# -*- coding: utf-8 -*-
"""
评价管理服务
从reviews_v2.py.old中提取的评价管理业务逻辑
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# 导入数据库管理器
from database.db_reviews import review_manager
from database.db_merchants import merchant_manager
from database.db_users import user_manager

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class ReviewMgmtService:
    """评价管理服务类"""
    
    CACHE_NAMESPACE = "review_mgmt"
    
    # 评价状态映射
    STATUS_COLORS = {
        'pending_user_review': 'warning',
        'pending_merchant_review': 'info', 
        'completed': 'success'
    }
    
    STATUS_ICONS = {
        'pending_user_review': '⏳',
        'pending_merchant_review': '🔍',
        'completed': '✅'
    }
    
    @staticmethod
    async def get_reviews_list(
        status_filter: Optional[str] = None,
        merchant_filter: Optional[str] = None,
        confirmed_filter: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search_query: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        获取评价列表
        
        Args:
            status_filter: 状态筛选
            merchant_filter: 商户筛选
            confirmed_filter: 确认状态筛选
            date_from: 开始日期
            date_to: 结束日期
            search_query: 搜索关键词
            page: 页码
            per_page: 每页数量
            
        Returns:
            dict: 评价列表数据
        """
        try:
            # 构建筛选参数
            filters = {}
            if status_filter:
                filters['status'] = status_filter
            if merchant_filter:
                filters['merchant_id'] = int(merchant_filter)
            if confirmed_filter:
                filters['confirmed'] = confirmed_filter == 'true'
            if date_from:
                filters['date_from'] = datetime.fromisoformat(date_from)
            if date_to:
                filters['date_to'] = datetime.fromisoformat(date_to)
            if search_query:
                filters['search'] = search_query
            
            # 获取评价数据
            reviews = await review_manager.get_reviews_with_details(
                status=status_filter,
                merchant_id=int(merchant_filter) if merchant_filter else None,
                is_confirmed=(confirmed_filter == 'true') if confirmed_filter else None,
                date_from=date_from,
                date_to=date_to,
                limit=per_page,
                offset=(page - 1) * per_page
            )
            
            # 获取总数
            total_reviews = await review_manager.count_reviews(
                status=status_filter,
                merchant_id=int(merchant_filter) if merchant_filter else None,
                is_confirmed=(confirmed_filter == 'true') if confirmed_filter else None,
                date_from=date_from,
                date_to=date_to
            )
            
            # 获取评价统计
            review_stats = await ReviewMgmtService._get_review_statistics()
            
            # 获取商户列表用于筛选
            merchants = await merchant_manager.get_merchants()
            
            return {
                'reviews': reviews,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_reviews,
                    'pages': (total_reviews + per_page - 1) // per_page
                },
                'filters': {
                    'status_filter': status_filter,
                    'merchant_filter': merchant_filter,
                    'confirmed_filter': confirmed_filter,
                    'date_from': date_from,
                    'date_to': date_to,
                    'search_query': search_query
                },
                'merchants': merchants[:100],  # 限制数量以提升性能
                'statistics': review_stats,
                'status_options': {
                    'pending_user_review': '待用户评价',
                    'pending_merchant_review': '待商户确认',
                    'completed': '已完成'
                },
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取评价列表失败: {e}")
            return {
                'reviews': [],
                'pagination': {'page': page, 'per_page': per_page, 'total': 0, 'pages': 0},
                'filters': {},
                'merchants': [],
                'statistics': {},
                'status_options': {},
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    async def get_review_detail(review_id: int) -> Dict[str, Any]:
        """
        获取评价详情
        
        Args:
            review_id: 评价ID
            
        Returns:
            dict: 评价详情数据
        """
        try:
            review = await review_manager.get_review_detail(review_id)
            if not review:
                return {'success': False, 'error': '评价不存在'}
            
            # 获取相关订单信息
            order = None
            if review.get('order_id'):
                from database.db_orders import OrderManager
                order_manager = OrderManager()
                order = await order_manager.get_order_by_id(review['order_id'])
            
            # 获取商户信息
            merchant = await merchant_manager.get_merchant_by_id(review.get('merchant_id'))
            
            # 获取用户信息
            user = await user_manager.get_user_profile(review.get('customer_user_id'))
            
            return {
                'review': review,
                'order': order,
                'merchant': merchant,
                'user': user,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"获取评价详情失败: review_id={review_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def confirm_review(review_id: int, confirmed: bool, admin_notes: Optional[str] = None) -> Dict[str, Any]:
        """
        确认评价
        
        Args:
            review_id: 评价ID
            confirmed: 是否确认
            admin_notes: 管理员备注
            
        Returns:
            dict: 确认结果
        """
        try:
            result = await review_manager.confirm_review(review_id, confirmed, admin_notes)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(ReviewMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                
                action = "确认" if confirmed else "取消确认"
                logger.info(f"评价{action}成功: review_id={review_id}")
                return {'success': True, 'message': f'评价{action}成功'}
            else:
                return {'success': False, 'error': '评价确认失败'}
                
        except Exception as e:
            logger.error(f"确认评价失败: review_id={review_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def update_review_info(review_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新评价信息
        
        Args:
            review_id: 评价ID
            data: 更新数据
            
        Returns:
            dict: 更新结果
        """
        try:
            result = await review_manager.update_review(review_id, data)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(ReviewMgmtService.CACHE_NAMESPACE)
                
                logger.info(f"评价信息更新成功: review_id={review_id}")
                return {'success': True, 'message': '评价信息更新成功'}
            else:
                return {'success': False, 'error': '评价信息更新失败'}
                
        except Exception as e:
            logger.error(f"更新评价信息失败: review_id={review_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def delete_review(review_id: int) -> Dict[str, Any]:
        """
        删除评价
        
        Args:
            review_id: 评价ID
            
        Returns:
            dict: 删除结果
        """
        try:
            result = await review_manager.delete_review(review_id)
            
            if result:
                # 清除相关缓存
                CacheService.clear_namespace(ReviewMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
                
                logger.info(f"评价删除成功: review_id={review_id}")
                return {'success': True, 'message': '评价删除成功'}
            else:
                return {'success': False, 'error': '评价删除失败'}
                
        except Exception as e:
            logger.error(f"删除评价失败: review_id={review_id}, error={e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def batch_confirm_reviews(review_ids: List[int], confirmed: bool) -> Dict[str, Any]:
        """
        批量确认评价
        
        Args:
            review_ids: 评价ID列表
            confirmed: 是否确认
            
        Returns:
            dict: 批量确认结果
        """
        try:
            if not review_ids:
                return {'success': False, 'error': '未选择评价'}
            
            success_count = 0
            failed_count = 0
            errors = []
            
            for review_id in review_ids:
                try:
                    result = await review_manager.confirm_review(review_id, confirmed)
                    if result:
                        success_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"评价 {review_id} 确认失败")
                except Exception as e:
                    failed_count += 1
                    errors.append(f"评价 {review_id} 确认异常: {str(e)}")
            
            # 清除相关缓存
            if success_count > 0:
                CacheService.clear_namespace(ReviewMgmtService.CACHE_NAMESPACE)
                CacheService.clear_namespace("dashboard")
            
            action = "确认" if confirmed else "取消确认"
            return {
                'success': success_count > 0,
                'success_count': success_count,
                'failed_count': failed_count,
                'errors': errors,
                'message': f'成功{action} {success_count} 条评价，失败 {failed_count} 条'
            }
            
        except Exception as e:
            logger.error(f"批量确认评价失败: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    async def get_review_analytics() -> Dict[str, Any]:
        """
        获取评价分析数据
        
        Returns:
            dict: 评价分析数据
        """
        try:
            cache_key = "review_analytics"
            cached_data = CacheService.get(ReviewMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取评价分析数据
            analytics_data = {
                'total_reviews': await review_manager.count_reviews(),
                'confirmed_reviews': await review_manager.count_confirmed_reviews(),
                'pending_reviews': await ReviewMgmtService._count_pending_reviews(),
                'average_rating': await review_manager.get_average_rating(),
                'rating_distribution': await ReviewMgmtService._get_rating_distribution(),
                'reviews_by_time': await ReviewMgmtService._get_reviews_by_time_period(),
                'top_rated_merchants': await ReviewMgmtService._get_top_rated_merchants(),
                'review_trends': await ReviewMgmtService._get_review_trends()
            }
            
            # 缓存10分钟
            CacheService.set(ReviewMgmtService.CACHE_NAMESPACE, cache_key, analytics_data, 600)
            return analytics_data
            
        except Exception as e:
            logger.error(f"获取评价分析数据失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def _get_review_statistics() -> Dict[str, Any]:
        """获取评价统计"""
        try:
            cache_key = "review_stats"
            cached_stats = CacheService.get(ReviewMgmtService.CACHE_NAMESPACE, cache_key)
            if cached_stats is not None:
                return cached_stats
            
            total_reviews = await review_manager.count_reviews()
            confirmed_reviews = await review_manager.count_confirmed_reviews()
            
            stats = {
                'total_reviews': total_reviews,
                'confirmed_reviews': confirmed_reviews,
                'pending_reviews': total_reviews - confirmed_reviews,
                'confirmation_rate': (confirmed_reviews / total_reviews * 100) if total_reviews > 0 else 0.0,
                'average_rating': await review_manager.get_average_rating()
            }
            
            # 缓存5分钟
            CacheService.set(ReviewMgmtService.CACHE_NAMESPACE, cache_key, stats, 300)
            return stats
            
        except Exception as e:
            logger.error(f"获取评价统计失败: {e}")
            return {}
    
    @staticmethod
    async def _count_pending_reviews() -> int:
        """计算待确认评价数"""
        try:
            total = await review_manager.count_reviews()
            confirmed = await review_manager.count_confirmed_reviews()
            return total - confirmed
        except Exception as e:
            logger.error(f"计算待确认评价数失败: {e}")
            return 0
    
    @staticmethod
    async def _get_rating_distribution() -> Dict[str, int]:
        """获取评分分布"""
        try:
            return await review_manager.get_rating_distribution()
        except Exception as e:
            logger.error(f"获取评分分布失败: {e}")
            return {}
    
    @staticmethod
    async def _get_reviews_by_time_period() -> Dict[str, int]:
        """按时间段统计评价"""
        try:
            now = datetime.now()
            return {
                'today': await review_manager.count_reviews_since(now.replace(hour=0, minute=0, second=0)),
                'this_week': await review_manager.count_reviews_since(now - timedelta(days=7)),
                'this_month': await review_manager.count_reviews_since(now - timedelta(days=30)),
                'this_year': await review_manager.count_reviews_since(now.replace(month=1, day=1))
            }
        except Exception as e:
            logger.error(f"按时间段统计评价失败: {e}")
            return {}
    
    @staticmethod
    async def _get_top_rated_merchants(limit: int = 10) -> List[Dict[str, Any]]:
        """获取评分最高的商户"""
        try:
            return await review_manager.get_top_rated_merchants(limit)
        except Exception as e:
            logger.error(f"获取评分最高的商户失败: {e}")
            return []
    
    @staticmethod
    async def _get_review_trends() -> Dict[str, Any]:
        """获取评价趋势"""
        try:
            # 获取最近30天的每日评价数据
            daily_reviews = await review_manager.get_daily_review_counts(30)
            
            return {
                'daily_reviews': daily_reviews,
                'growth_rate': await ReviewMgmtService._calculate_growth_rate()
            }
        except Exception as e:
            logger.error(f"获取评价趋势失败: {e}")
            return {}
    
    @staticmethod
    async def _calculate_growth_rate() -> float:
        """计算增长率"""
        try:
            now = datetime.now()
            this_month = await review_manager.count_reviews_since(now.replace(day=1))
            last_month = await review_manager.count_reviews_in_range(
                now.replace(month=now.month-1, day=1) if now.month > 1 else now.replace(year=now.year-1, month=12, day=1),
                now.replace(day=1)
            )
            return ((this_month - last_month) / last_month * 100) if last_month > 0 else 0.0
        except Exception as e:
            logger.error(f"计算增长率失败: {e}")
            return 0.0

    
    @staticmethod
    def get_status_display(status: str) -> str:
        """获取状态显示文本"""
        status_map = {
            'pending_user_review': '待用户评价',
            'pending_merchant_review': '待商户确认',
            'completed': '已完成'
        }
        return status_map.get(status, status or '未知状态')
    
    @staticmethod
    def get_status_color(status: str) -> str:
        """获取状态颜色"""
        return ReviewMgmtService.STATUS_COLORS.get(status, 'secondary')
    
    @staticmethod
    def get_status_icon(status: str) -> str:
        """获取状态图标"""
        return ReviewMgmtService.STATUS_ICONS.get(status, '❓')
