# -*- coding: utf-8 -*-
"""
数据分析服务
整合各种analytics相关的业务逻辑，提供统一的数据分析接口
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# 导入其他服务
from .user_mgmt_service import UserMgmtService
from .order_mgmt_service import OrderMgmtService
from .review_mgmt_service import ReviewMgmtService
from .post_mgmt_service import PostMgmtService
from .subscription_mgmt_service import SubscriptionMgmtService
from .incentive_mgmt_service import IncentiveMgmtService
# from .binding_mgmt_service import BindingMgmtService  # V2.0: 已迁移到DB Manager
from database.db_binding_codes import binding_codes_manager
from .dashboard_service import DashboardService

# 导入缓存服务
from .cache_service import CacheService

logger = logging.getLogger(__name__)


class AnalyticsService:
    """数据分析服务类"""
    
    CACHE_NAMESPACE = "analytics"
    
    @staticmethod
    async def get_comprehensive_analytics() -> Dict[str, Any]:
        """
        获取综合分析数据
        
        Returns:
            dict: 综合分析数据
        """
        try:
            cache_key = "comprehensive_analytics"
            cached_data = CacheService.get(AnalyticsService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取各模块的分析数据
            analytics_data = {
                'overview': await AnalyticsService._get_overview_metrics(),
                'user_analytics': await UserMgmtService.get_user_analytics(),
                'order_analytics': await OrderMgmtService.get_order_analytics(),
                'review_analytics': await ReviewMgmtService.get_review_analytics(),
                'post_analytics': await PostMgmtService.get_post_analytics(),
                'subscription_analytics': await SubscriptionMgmtService.get_subscription_analytics(),
                'incentive_analytics': await IncentiveMgmtService.get_incentive_analytics(),
                'binding_analytics': await AnalyticsService._get_binding_analytics_v2(),
                'trends': await AnalyticsService._get_comprehensive_trends(),
                'generated_at': datetime.now().isoformat()
            }
            
            # 缓存20分钟
            CacheService.set(AnalyticsService.CACHE_NAMESPACE, cache_key, analytics_data, 1200)
            return analytics_data
            
        except Exception as e:
            logger.error(f"获取综合分析数据失败: {e}")
            return {
                'overview': {},
                'user_analytics': {},
                'order_analytics': {},
                'review_analytics': {},
                'post_analytics': {},
                'subscription_analytics': {},
                'incentive_analytics': {},
                'binding_analytics': {},
                'trends': {},
                'generated_at': datetime.now().isoformat(),
                'error': str(e)
            }
    
    @staticmethod
    async def get_business_metrics() -> Dict[str, Any]:
        """
        获取业务核心指标
        
        Returns:
            dict: 业务核心指标
        """
        try:
            cache_key = "business_metrics"
            cached_data = CacheService.get(AnalyticsService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 获取业务核心指标
            business_metrics = {
                'user_metrics': await AnalyticsService._get_user_business_metrics(),
                'merchant_metrics': await AnalyticsService._get_merchant_business_metrics(),
                'order_metrics': await AnalyticsService._get_order_business_metrics(),
                'engagement_metrics': await AnalyticsService._get_engagement_metrics(),
                'growth_metrics': await AnalyticsService._get_growth_metrics(),
                'quality_metrics': await AnalyticsService._get_quality_metrics()
            }
            
            # 缓存15分钟
            CacheService.set(AnalyticsService.CACHE_NAMESPACE, cache_key, business_metrics, 900)
            return business_metrics
            
        except Exception as e:
            logger.error(f"获取业务核心指标失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def get_performance_dashboard() -> Dict[str, Any]:
        """
        获取性能仪表板数据
        
        Returns:
            dict: 性能仪表板数据
        """
        try:
            # 获取系统性能指标
            performance_data = {
                'system_metrics': await DashboardService.get_performance_metrics(),
                'cache_metrics': CacheService.get_cache_stats(),
                'response_time_metrics': await AnalyticsService._get_response_time_metrics(),
                'error_rate_metrics': await AnalyticsService._get_error_rate_metrics(),
                'throughput_metrics': await AnalyticsService._get_throughput_metrics(),
                'resource_usage': await AnalyticsService._get_resource_usage_metrics()
            }
            
            return performance_data
            
        except Exception as e:
            logger.error(f"获取性能仪表板数据失败: {e}")
            return {'error': str(e)}
    
    @staticmethod
    async def get_time_series_analytics(
        metric: str,
        time_range: str = '30d',
        granularity: str = 'day'
    ) -> Dict[str, Any]:
        """
        获取时间序列分析数据
        
        Args:
            metric: 指标名称 (users, orders, reviews, posts等)
            time_range: 时间范围 (7d, 30d, 90d, 1y)
            granularity: 粒度 (hour, day, week, month)
            
        Returns:
            dict: 时间序列分析数据
        """
        try:
            cache_key = f"time_series_{metric}_{time_range}_{granularity}"
            cached_data = CacheService.get(AnalyticsService.CACHE_NAMESPACE, cache_key)
            if cached_data is not None:
                return cached_data
            
            # 解析时间范围
            days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
            days = days_map.get(time_range, 30)
            
            # 根据指标类型获取时间序列数据
            time_series_data = await AnalyticsService._get_metric_time_series(
                metric, days, granularity
            )
            
            # 计算趋势指标
            trend_analysis = AnalyticsService._analyze_trend(time_series_data)
            
            result = {
                'metric': metric,
                'time_range': time_range,
                'granularity': granularity,
                'data': time_series_data,
                'trend_analysis': trend_analysis,
                'generated_at': datetime.now().isoformat()
            }
            
            # 缓存30分钟
            CacheService.set(AnalyticsService.CACHE_NAMESPACE, cache_key, result, 1800)
            return result
            
        except Exception as e:
            logger.error(f"获取时间序列分析数据失败: metric={metric}, error={e}")
            return {'error': str(e)}
    
    @staticmethod
    async def get_custom_report(
        report_type: str,
        filters: Dict[str, Any],
        date_range: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        获取自定义报告
        
        Args:
            report_type: 报告类型
            filters: 筛选条件
            date_range: 日期范围
            
        Returns:
            dict: 自定义报告数据
        """
        try:
            report_data = {
                'report_info': {
                    'type': report_type,
                    'filters': filters,
                    'date_range': date_range,
                    'generated_at': datetime.now().isoformat()
                }
            }
            
            # 根据报告类型生成数据
            if report_type == 'user_behavior':
                report_data['data'] = await AnalyticsService._generate_user_behavior_report(filters, date_range)
            elif report_type == 'merchant_performance':
                report_data['data'] = await AnalyticsService._generate_merchant_performance_report(filters, date_range)
            elif report_type == 'order_analysis':
                report_data['data'] = await AnalyticsService._generate_order_analysis_report(filters, date_range)
            elif report_type == 'review_sentiment':
                report_data['data'] = await AnalyticsService._generate_review_sentiment_report(filters, date_range)
            else:
                report_data['error'] = f'不支持的报告类型: {report_type}'
            
            return report_data
            
        except Exception as e:
            logger.error(f"获取自定义报告失败: report_type={report_type}, error={e}")
            return {'error': str(e)}
    
    @staticmethod
    async def _get_overview_metrics() -> Dict[str, Any]:
        """获取概览指标"""
        try:
            # 获取仪表板数据作为概览指标的基础
            dashboard_data = await DashboardService.get_dashboard_data()
            
            return {
                'total_users': dashboard_data['users'].get('total', 0),
                'total_merchants': dashboard_data['merchants'].get('total', 0),
                'total_orders': dashboard_data['orders'].get('total', 0),
                'total_reviews': dashboard_data['reviews'].get('total', 0),
                'system_health': 'healthy',  # 简单的系统健康状态
                'last_updated': dashboard_data.get('last_updated')
            }
        except Exception as e:
            logger.error(f"获取概览指标失败: {e}")
            return {}
    
    @staticmethod
    async def _get_user_business_metrics() -> Dict[str, Any]:
        """获取用户业务指标"""
        try:
            user_analytics = await UserMgmtService.get_user_analytics()
            return {
                'total_users': user_analytics.get('total_users', 0),
                'active_users': user_analytics.get('active_users', 0),
                'retention_rate': await AnalyticsService._calculate_user_retention_rate(),
                'churn_rate': await AnalyticsService._calculate_user_churn_rate(),
                'average_session_duration': await AnalyticsService._calculate_avg_session_duration()
            }
        except Exception as e:
            logger.error(f"获取用户业务指标失败: {e}")
            return {}
    
    @staticmethod
    async def _get_merchant_business_metrics() -> Dict[str, Any]:
        """获取商户业务指标"""
        try:
            post_analytics = await PostMgmtService.get_post_analytics()
            return {
                'total_merchants': post_analytics.get('total_posts', 0),
                'active_merchants': post_analytics.get('published', 0),
                'approval_rate': post_analytics.get('approval_rate', 0.0),
                'average_response_time': await AnalyticsService._calculate_merchant_response_time()
            }
        except Exception as e:
            logger.error(f"获取商户业务指标失败: {e}")
            return {}
    
    @staticmethod
    async def _get_order_business_metrics() -> Dict[str, Any]:
        """获取订单业务指标"""
        try:
            order_analytics = await OrderMgmtService.get_order_analytics()
            return {
                'total_orders': order_analytics.get('total_orders', 0),
                'completion_rate': order_analytics.get('completion_rate', 0.0),
                'average_order_value': order_analytics.get('average_order_value', 0.0),
                'order_growth_rate': await AnalyticsService._calculate_order_growth_rate()
            }
        except Exception as e:
            logger.error(f"获取订单业务指标失败: {e}")
            return {}
    
    @staticmethod
    async def _get_engagement_metrics() -> Dict[str, Any]:
        """获取用户参与度指标"""
        try:
            return {
                'daily_active_users': await AnalyticsService._calculate_daily_active_users(),
                'user_interaction_rate': await AnalyticsService._calculate_user_interaction_rate(),
                'content_engagement_rate': await AnalyticsService._calculate_content_engagement_rate(),
                'feature_adoption_rate': await AnalyticsService._calculate_feature_adoption_rate()
            }
        except Exception as e:
            logger.error(f"获取用户参与度指标失败: {e}")
            return {}
    
    @staticmethod
    async def _get_growth_metrics() -> Dict[str, Any]:
        """获取增长指标"""
        try:
            return {
                'user_growth_rate': await AnalyticsService._calculate_user_growth_rate(),
                'merchant_growth_rate': await AnalyticsService._calculate_merchant_growth_rate(),
                'revenue_growth_rate': await AnalyticsService._calculate_revenue_growth_rate(),
                'market_penetration': await AnalyticsService._calculate_market_penetration()
            }
        except Exception as e:
            logger.error(f"获取增长指标失败: {e}")
            return {}
    
    @staticmethod
    async def _get_quality_metrics() -> Dict[str, Any]:
        """获取质量指标"""
        try:
            review_analytics = await ReviewMgmtService.get_review_analytics()
            return {
                'average_rating': review_analytics.get('average_rating', 0.0),
                'review_completion_rate': await AnalyticsService._calculate_review_completion_rate(),
                'customer_satisfaction': await AnalyticsService._calculate_customer_satisfaction(),
                'service_quality_index': await AnalyticsService._calculate_service_quality_index()
            }
        except Exception as e:
            logger.error(f"获取质量指标失败: {e}")
            return {}
    
    @staticmethod
    async def _get_comprehensive_trends() -> Dict[str, Any]:
        """获取综合趋势数据"""
        try:
            return {
                'user_trends': await AnalyticsService._get_user_trends(),
                'order_trends': await AnalyticsService._get_order_trends(),
                'review_trends': await AnalyticsService._get_review_trends(),
                'growth_trends': await AnalyticsService._get_growth_trends()
            }
        except Exception as e:
            logger.error(f"获取综合趋势数据失败: {e}")
            return {}
    
    @staticmethod
    async def _get_metric_time_series(metric: str, days: int, granularity: str) -> List[Dict[str, Any]]:
        """获取指标的时间序列数据"""
        try:
            # TODO: 实现具体的时间序列数据获取逻辑
            # 这里应该根据metric类型从相应的数据库表中获取时间序列数据
            return []
        except Exception as e:
            logger.error(f"获取指标时间序列数据失败: metric={metric}, error={e}")
            return []
    
    @staticmethod
    def _analyze_trend(time_series_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析时间序列数据的趋势"""
        try:
            if not time_series_data or len(time_series_data) < 2:
                return {'trend': 'insufficient_data'}
            
            # 简单的趋势分析
            first_value = time_series_data[0].get('value', 0)
            last_value = time_series_data[-1].get('value', 0)
            
            if last_value > first_value:
                trend = 'upward'
            elif last_value < first_value:
                trend = 'downward'
            else:
                trend = 'stable'
            
            growth_rate = ((last_value - first_value) / first_value * 100) if first_value > 0 else 0
            
            return {
                'trend': trend,
                'growth_rate': growth_rate,
                'start_value': first_value,
                'end_value': last_value,
                'data_points': len(time_series_data)
            }
        except Exception as e:
            logger.error(f"分析趋势失败: {e}")
            return {'trend': 'error'}
    
    # 以下是各种计算方法的占位符实现，实际使用时需要根据具体业务逻辑实现
    
    @staticmethod
    async def _calculate_user_retention_rate() -> float:
        """计算用户留存率"""
        # TODO: 实现用户留存率计算逻辑
        return 0.0
    
    @staticmethod
    async def _calculate_user_churn_rate() -> float:
        """计算用户流失率"""
        # TODO: 实现用户流失率计算逻辑
        return 0.0
    
    @staticmethod
    async def _calculate_avg_session_duration() -> float:
        """计算平均会话时长"""
        # TODO: 实现平均会话时长计算逻辑
        return 0.0
    
    @staticmethod
    async def _calculate_merchant_response_time() -> float:
        """计算商户平均响应时间"""
        # TODO: 实现商户响应时间计算逻辑
        return 0.0
    
    @staticmethod
    async def _calculate_order_growth_rate() -> float:
        """计算订单增长率"""
        # TODO: 实现订单增长率计算逻辑
        return 0.0
    
    # 继续添加其他计算方法的占位符实现...
    
    @staticmethod
    async def _get_response_time_metrics() -> Dict[str, Any]:
        """获取响应时间指标"""
        return {'average_response_time': 0.0}
    
    @staticmethod
    async def _get_error_rate_metrics() -> Dict[str, Any]:
        """获取错误率指标"""
        return {'error_rate': 0.0}
    
    @staticmethod
    async def _get_throughput_metrics() -> Dict[str, Any]:
        """获取吞吐量指标"""
        return {'requests_per_second': 0.0}
    
    @staticmethod
    async def _get_resource_usage_metrics() -> Dict[str, Any]:
        """获取资源使用指标"""
        return {'cpu_usage': 0.0, 'memory_usage': 0.0}
    
    # 其他占位符方法...
    @staticmethod
    async def _calculate_daily_active_users() -> int:
        return 0
    
    @staticmethod
    async def _calculate_user_interaction_rate() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_content_engagement_rate() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_feature_adoption_rate() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_user_growth_rate() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_merchant_growth_rate() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_revenue_growth_rate() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_market_penetration() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_review_completion_rate() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_customer_satisfaction() -> float:
        return 0.0
    
    @staticmethod
    async def _calculate_service_quality_index() -> float:
        return 0.0
    
    @staticmethod
    async def _get_user_trends() -> Dict[str, Any]:
        return {}
    
    @staticmethod
    async def _get_order_trends() -> Dict[str, Any]:
        return {}
    
    @staticmethod
    async def _get_review_trends() -> Dict[str, Any]:
        return {}
    
    @staticmethod
    async def _get_growth_trends() -> Dict[str, Any]:
        return {}
    
    @staticmethod
    async def _generate_user_behavior_report(filters: Dict[str, Any], date_range: Dict[str, str]) -> Dict[str, Any]:
        return {}
    
    @staticmethod
    async def _generate_merchant_performance_report(filters: Dict[str, Any], date_range: Dict[str, str]) -> Dict[str, Any]:
        return {}
    
    @staticmethod
    async def _generate_order_analysis_report(filters: Dict[str, Any], date_range: Dict[str, str]) -> Dict[str, Any]:
        return {}
    
    @staticmethod
    async def _generate_review_sentiment_report(filters: Dict[str, Any], date_range: Dict[str, str]) -> Dict[str, Any]:
        return {}
    
    @staticmethod
    async def _get_binding_analytics_v2() -> Dict[str, Any]:
        """
        V2.0 绑定码分析数据 - 直接使用DB Manager
        
        Returns:
            dict: 绑定码分析数据
        """
        try:
            # 获取所有绑定码数据
            result = await binding_codes_manager.get_all_binding_codes(
                include_used=True, 
                include_expired=True
            )
            all_codes = (result or {}).get('codes', [])
            
            if not all_codes:
                return {
                    'total_codes': 0,
                    'used_codes': 0,
                    'unused_codes': 0,
                    'usage_rate': 0.0,
                    'recent_usage': [],
                    'trends': {}
                }
            
            # 统计数据
            total_codes = len(all_codes)
            used_codes = sum(1 for code in all_codes if code.get('is_used', False))
            unused_codes = total_codes - used_codes
            usage_rate = (used_codes / total_codes * 100) if total_codes > 0 else 0.0
            
            # 最近使用的绑定码 (最多10个)
            recent_usage = [
                {
                    'code': code.get('code', ''),
                    'merchant_name': code.get('merchant_name', '未知'),
                    'used_at': code.get('used_at', ''),
                    'merchant_id': code.get('merchant_id', 0)
                }
                for code in all_codes 
                if code.get('is_used') and code.get('used_at')
            ]
            recent_usage = sorted(recent_usage, key=lambda x: x['used_at'], reverse=True)[:10]
            
            return {
                'total_codes': total_codes,
                'used_codes': used_codes,
                'unused_codes': unused_codes,
                'usage_rate': round(usage_rate, 2),
                'recent_usage': recent_usage,
                'trends': {
                    'usage_trend': 'stable',  # 简化的趋势分析
                    'growth_rate': 0.0
                }
            }
            
        except Exception as e:
            logger.error(f"获取绑定码分析数据失败: {e}")
            return {
                'total_codes': 0,
                'used_codes': 0,
                'unused_codes': 0,
                'usage_rate': 0.0,
                'recent_usage': [],
                'trends': {},
                'error': str(e)
            }
