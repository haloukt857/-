"""
高级分析模块
提供深度数据分析、趋势预测和业务洞察功能
支持多维度数据分析和可视化报告生成
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

from database.db_logs import activity_logs_db
from database.db_binding_codes import binding_codes_db
from database.db_merchants import merchant_manager
from database.db_orders import order_manager
from .statistics import StatisticsEngine, StatsResult, TimeRange, StatsPeriod

# 配置日志
logger = logging.getLogger(__name__)

class AnalyticsType(Enum):
    """高级分析类型枚举"""
    COHORT_ANALYSIS = "cohort_analysis"
    FUNNEL_ANALYSIS = "funnel_analysis"
    RETENTION_ANALYSIS = "retention_analysis"
    CHURN_PREDICTION = "churn_prediction"
    REVENUE_FORECAST = "revenue_forecast"
    USER_SEGMENTATION = "user_segmentation"
    CONVERSION_OPTIMIZATION = "conversion_optimization"
    SEASONAL_TRENDS = "seasonal_trends"

@dataclass
class AnalyticsInsight:
    """分析洞察数据类"""
    insight_type: str
    title: str
    description: str
    impact_level: str  # 'high', 'medium', 'low'
    recommendation: str
    data_points: Dict[str, Any]
    confidence_score: float  # 0-1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'insight_type': self.insight_type,
            'title': self.title,
            'description': self.description,
            'impact_level': self.impact_level,
            'recommendation': self.recommendation,
            'data_points': self.data_points,
            'confidence_score': self.confidence_score
        }

class AdvancedAnalyticsEngine:
    """
    高级分析引擎类
    提供深度数据分析和业务洞察功能
    """
    
    @staticmethod
    async def generate_cohort_analysis(time_range: TimeRange) -> Dict[str, Any]:
        """
        生成用户群组分析
        分析不同时期注册用户的行为模式和留存情况
        
        Args:
            time_range: 分析时间范围
            
        Returns:
            群组分析数据
        """
        try:
            # 获取用户活动数据
            activities = await activity_logs_db.get_recent_activities(limit=10000)
            
            # 按用户分组并按时间排序
            user_activities = {}
            for activity in activities:
                if activity['user_id']:
                    user_id = activity['user_id']
                    if user_id not in user_activities:
                        user_activities[user_id] = []
                    user_activities[user_id].append(activity)
            
            # 按首次活动时间分组用户
            cohorts = {}
            for user_id, user_activity_list in user_activities.items():
                # 按时间排序
                sorted_activities = sorted(user_activity_list, key=lambda x: x['timestamp'])
                first_activity_date = datetime.fromisoformat(sorted_activities[0]['timestamp']).date()
                
                # 按月分组
                cohort_key = first_activity_date.strftime('%Y-%m')
                if cohort_key not in cohorts:
                    cohorts[cohort_key] = []
                cohorts[cohort_key].append({
                    'user_id': user_id,
                    'first_activity': first_activity_date,
                    'total_activities': len(user_activity_list),
                    'last_activity': datetime.fromisoformat(sorted_activities[-1]['timestamp']).date()
                })
            
            # 计算留存率
            cohort_analysis = {}
            for cohort_month, users in cohorts.items():
                cohort_size = len(users)
                retention_data = {
                    'cohort_month': cohort_month,
                    'cohort_size': cohort_size,
                    'retention_rates': {}
                }
                
                # 计算各月留存率
                for period in range(1, 13):  # 12个月的留存率
                    retained_users = 0
                    for user in users:
                        # 检查用户在该期间是否还活跃
                        target_month = user['first_activity'] + timedelta(days=30 * period)
                        if user['last_activity'] >= target_month:
                            retained_users += 1
                    
                    retention_rate = (retained_users / cohort_size) * 100 if cohort_size > 0 else 0
                    retention_data['retention_rates'][f'month_{period}'] = retention_rate
                
                cohort_analysis[cohort_month] = retention_data
            
            logger.info(f"群组分析生成完成，分析了 {len(cohorts)} 个群组")
            return {
                'cohort_data': cohort_analysis,
                'total_cohorts': len(cohorts),
                'total_users_analyzed': sum(len(users) for users in cohorts.values()),
                'analysis_period': time_range.to_dict()
            }
            
        except Exception as e:
            logger.error(f"生成群组分析失败: {e}")
            raise
    
    @staticmethod
    async def generate_funnel_analysis(time_range: TimeRange) -> Dict[str, Any]:
        """
        生成漏斗分析
        分析用户从初次接触到最终转化的各个阶段
        
        Args:
            time_range: 分析时间范围
            
        Returns:
            漏斗分析数据
        """
        try:
            # 定义转化漏斗阶段
            funnel_stages = [
                {'stage': 'button_click', 'name': '按钮点击', 'action_type': 'button_click'},
                {'stage': 'private_chat', 'name': '私聊启动', 'action_type': 'user_interaction'},
                {'stage': 'merchant_contact', 'name': '商户联系', 'action_type': 'merchant_registration'},
                {'stage': 'order_created', 'name': '订单创建', 'action_type': 'order_created'},
                {'stage': 'order_completed', 'name': '订单完成', 'action_type': 'order_updated'}
            ]
            
            # 获取各阶段数据
            funnel_data = {}
            total_users = set()
            
            for stage in funnel_stages:
                stage_activities = await activity_logs_db.get_recent_activities(
                    limit=10000,
                    action_type=stage['action_type']
                )
                
                # 过滤时间范围内的活动
                filtered_activities = [
                    activity for activity in stage_activities
                    if time_range.start_date <= datetime.fromisoformat(activity['timestamp']) <= time_range.end_date
                ]
                
                stage_users = set(activity['user_id'] for activity in filtered_activities if activity['user_id'])
                total_users.update(stage_users)
                
                funnel_data[stage['stage']] = {
                    'name': stage['name'],
                    'users': len(stage_users),
                    'activities': len(filtered_activities),
                    'user_ids': stage_users
                }
            
            # 计算转化率
            conversion_rates = {}
            previous_stage_users = None
            
            for stage_key in [s['stage'] for s in funnel_stages]:
                current_users = funnel_data[stage_key]['users']
                
                if previous_stage_users is not None:
                    conversion_rate = (current_users / previous_stage_users) * 100 if previous_stage_users > 0 else 0
                    conversion_rates[stage_key] = conversion_rate
                else:
                    conversion_rates[stage_key] = 100  # 第一阶段转化率为100%
                
                previous_stage_users = current_users
            
            # 识别流失点
            drop_off_analysis = {}
            for i, stage_key in enumerate([s['stage'] for s in funnel_stages[:-1]]):
                current_users = funnel_data[stage_key]['users']
                next_stage_key = funnel_stages[i + 1]['stage']
                next_users = funnel_data[next_stage_key]['users']
                
                drop_off_count = current_users - next_users
                drop_off_rate = (drop_off_count / current_users) * 100 if current_users > 0 else 0
                
                drop_off_analysis[f"{stage_key}_to_{next_stage_key}"] = {
                    'drop_off_count': drop_off_count,
                    'drop_off_rate': drop_off_rate,
                    'stage_from': funnel_data[stage_key]['name'],
                    'stage_to': funnel_data[next_stage_key]['name']
                }
            
            logger.info(f"漏斗分析生成完成，分析了 {len(total_users)} 个用户")
            return {
                'funnel_stages': funnel_data,
                'conversion_rates': conversion_rates,
                'drop_off_analysis': drop_off_analysis,
                'total_users_in_funnel': len(total_users),
                'overall_conversion_rate': conversion_rates.get('order_completed', 0),
                'analysis_period': time_range.to_dict()
            }
            
        except Exception as e:
            logger.error(f"生成漏斗分析失败: {e}")
            raise
    
    @staticmethod
    async def generate_user_segmentation_analysis(time_range: TimeRange) -> Dict[str, Any]:
        """
        生成用户分群分析
        基于行为模式将用户分为不同群体
        
        Args:
            time_range: 分析时间范围
            
        Returns:
            用户分群分析数据
        """
        try:
            # 获取用户活动数据
            activities = await activity_logs_db.get_recent_activities(limit=10000)
            
            # 按用户聚合数据
            user_profiles = {}
            for activity in activities:
                if not activity['user_id']:
                    continue
                
                user_id = activity['user_id']
                if user_id not in user_profiles:
                    user_profiles[user_id] = {
                        'total_activities': 0,
                        'button_clicks': 0,
                        'interactions': 0,
                        'orders': 0,
                        'first_activity': None,
                        'last_activity': None,
                        'activity_days': set()
                    }
                
                profile = user_profiles[user_id]
                profile['total_activities'] += 1
                
                activity_date = datetime.fromisoformat(activity['timestamp'])
                profile['activity_days'].add(activity_date.date())
                
                if profile['first_activity'] is None or activity_date < profile['first_activity']:
                    profile['first_activity'] = activity_date
                if profile['last_activity'] is None or activity_date > profile['last_activity']:
                    profile['last_activity'] = activity_date
                
                # 按活动类型分类
                action_type = activity['action_type']
                if action_type == 'button_click':
                    profile['button_clicks'] += 1
                elif action_type == 'user_interaction':
                    profile['interactions'] += 1
                elif action_type in ['order_created', 'order_updated']:
                    profile['orders'] += 1
            
            # 计算用户特征
            for user_id, profile in user_profiles.items():
                profile['activity_span_days'] = (profile['last_activity'] - profile['first_activity']).days if profile['first_activity'] and profile['last_activity'] else 0
                profile['unique_activity_days'] = len(profile['activity_days'])
                profile['avg_activities_per_day'] = profile['total_activities'] / max(profile['unique_activity_days'], 1)
            
            # 用户分群
            segments = {
                'power_users': [],      # 高频高价值用户
                'regular_users': [],    # 常规用户
                'occasional_users': [], # 偶尔使用用户
                'new_users': [],        # 新用户
                'churned_users': []     # 流失用户
            }
            
            current_time = datetime.now()
            
            for user_id, profile in user_profiles.items():
                days_since_last_activity = (current_time - profile['last_activity']).days if profile['last_activity'] else 999
                
                # 分群逻辑
                if profile['total_activities'] >= 20 and profile['orders'] > 0:
                    segments['power_users'].append(user_id)
                elif profile['total_activities'] >= 5 and days_since_last_activity <= 7:
                    segments['regular_users'].append(user_id)
                elif days_since_last_activity > 30:
                    segments['churned_users'].append(user_id)
                elif profile['unique_activity_days'] <= 2:
                    segments['new_users'].append(user_id)
                else:
                    segments['occasional_users'].append(user_id)
            
            # 计算分群统计
            segment_stats = {}
            total_users = len(user_profiles)
            
            for segment_name, user_list in segments.items():
                segment_size = len(user_list)
                segment_profiles = [user_profiles[uid] for uid in user_list]
                
                segment_stats[segment_name] = {
                    'count': segment_size,
                    'percentage': (segment_size / total_users) * 100 if total_users > 0 else 0,
                    'avg_activities': sum(p['total_activities'] for p in segment_profiles) / segment_size if segment_size > 0 else 0,
                    'avg_orders': sum(p['orders'] for p in segment_profiles) / segment_size if segment_size > 0 else 0,
                    'avg_activity_days': sum(p['unique_activity_days'] for p in segment_profiles) / segment_size if segment_size > 0 else 0
                }
            
            logger.info(f"用户分群分析生成完成，分析了 {total_users} 个用户")
            return {
                'segments': segment_stats,
                'total_users': total_users,
                'segment_distribution': {name: len(users) for name, users in segments.items()},
                'analysis_period': time_range.to_dict()
            }
            
        except Exception as e:
            logger.error(f"生成用户分群分析失败: {e}")
            raise
    
    @staticmethod
    async def generate_business_insights(time_range: TimeRange) -> List[AnalyticsInsight]:
        """
        生成业务洞察
        基于数据分析提供可执行的业务建议
        
        Args:
            time_range: 分析时间范围
            
        Returns:
            业务洞察列表
        """
        try:
            insights = []
            
            # 获取基础统计数据
            button_stats = await activity_logs_db.get_button_click_statistics(
                start_date=time_range.start_date,
                end_date=time_range.end_date
            )
            
            activity_stats = await activity_logs_db.get_activity_statistics(
                start_date=time_range.start_date,
                end_date=time_range.end_date
            )
            
            merchants = await merchant_manager.get_all_merchants()
            orders = await order_manager.get_orders_by_timeframe(
                time_range.start_date,
                time_range.end_date
            )
            
            # 洞察1: 用户参与度分析
            if button_stats['unique_users'] > 0:
                click_per_user = button_stats['total_clicks'] / button_stats['unique_users']
                if click_per_user < 2:
                    insights.append(AnalyticsInsight(
                        insight_type="user_engagement",
                        title="用户参与度偏低",
                        description=f"平均每用户点击次数仅为 {click_per_user:.1f} 次，低于理想水平",
                        impact_level="high",
                        recommendation="建议优化按钮文案和位置，增加用户互动激励机制",
                        data_points={
                            'avg_clicks_per_user': click_per_user,
                            'total_users': button_stats['unique_users'],
                            'total_clicks': button_stats['total_clicks']
                        },
                        confidence_score=0.8
                    ))
            
            # 洞察2: 商户转化分析
            active_merchants = len([m for m in merchants if m['status'] == 'active'])
            if len(orders) > 0 and active_merchants > 0:
                orders_per_merchant = len(orders) / active_merchants
                if orders_per_merchant < 1:
                    insights.append(AnalyticsInsight(
                        insight_type="merchant_conversion",
                        title="商户转化效率需要提升",
                        description=f"平均每商户订单数为 {orders_per_merchant:.1f}，转化效率较低",
                        impact_level="medium",
                        recommendation="建议为商户提供更好的展示机会和营销支持",
                        data_points={
                            'orders_per_merchant': orders_per_merchant,
                            'total_orders': len(orders),
                            'active_merchants': active_merchants
                        },
                        confidence_score=0.7
                    ))
            
            # 洞察3: 时间趋势分析
            daily_stats = button_stats.get('daily_stats', {})
            if len(daily_stats) >= 7:
                recent_days = sorted(daily_stats.keys())[-7:]
                recent_clicks = [daily_stats[day] for day in recent_days]
                
                if len(recent_clicks) >= 2:
                    trend = (recent_clicks[-1] - recent_clicks[0]) / max(recent_clicks[0], 1)
                    if trend < -0.2:  # 下降超过20%
                        insights.append(AnalyticsInsight(
                            insight_type="trend_analysis",
                            title="用户活跃度呈下降趋势",
                            description=f"最近7天用户点击量下降了 {abs(trend)*100:.1f}%",
                            impact_level="high",
                            recommendation="需要立即采取措施提升用户活跃度，如推出新活动或优化用户体验",
                            data_points={
                                'trend_percentage': trend * 100,
                                'recent_clicks': recent_clicks,
                                'analysis_days': len(recent_days)
                            },
                            confidence_score=0.9
                        ))
            
            # 洞察4: 高峰时段优化
            hourly_stats = button_stats.get('hourly_stats', {})
            if hourly_stats:
                peak_hour = max(hourly_stats.items(), key=lambda x: x[1])
                quiet_hour = min(hourly_stats.items(), key=lambda x: x[1])
                
                if peak_hour[1] > quiet_hour[1] * 3:  # 高峰时段是低谷的3倍以上
                    insights.append(AnalyticsInsight(
                        insight_type="timing_optimization",
                        title="存在明显的用户活跃时段差异",
                        description=f"高峰时段({peak_hour[0]})的活跃度是低谷时段({quiet_hour[0]})的 {peak_hour[1]/max(quiet_hour[1], 1):.1f} 倍",
                        impact_level="medium",
                        recommendation="建议在高峰时段增加推广力度，在低谷时段推出特殊活动",
                        data_points={
                            'peak_hour': peak_hour[0],
                            'peak_clicks': peak_hour[1],
                            'quiet_hour': quiet_hour[0],
                            'quiet_clicks': quiet_hour[1]
                        },
                        confidence_score=0.8
                    ))
            
            logger.info(f"业务洞察生成完成，生成了 {len(insights)} 个洞察")
            return insights
            
        except Exception as e:
            logger.error(f"生成业务洞察失败: {e}")
            raise
    
    @staticmethod
    async def generate_performance_forecast(time_range: TimeRange, forecast_days: int = 30) -> Dict[str, Any]:
        """
        生成性能预测
        基于历史数据预测未来趋势
        
        Args:
            time_range: 历史数据时间范围
            forecast_days: 预测天数
            
        Returns:
            性能预测数据
        """
        try:
            # 获取历史数据
            button_stats = await activity_logs_db.get_button_click_statistics(
                start_date=time_range.start_date,
                end_date=time_range.end_date
            )
            
            daily_stats = button_stats.get('daily_stats', {})
            if len(daily_stats) < 7:
                return {
                    'forecast_available': False,
                    'reason': '历史数据不足，需要至少7天的数据进行预测',
                    'required_days': 7,
                    'available_days': len(daily_stats)
                }
            
            # 简单的线性趋势预测
            sorted_dates = sorted(daily_stats.keys())
            values = [daily_stats[date] for date in sorted_dates]
            
            # 计算趋势
            n = len(values)
            sum_x = sum(range(n))
            sum_y = sum(values)
            sum_xy = sum(i * values[i] for i in range(n))
            sum_x2 = sum(i * i for i in range(n))
            
            # 线性回归系数
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
            intercept = (sum_y - slope * sum_x) / n
            
            # 生成预测
            forecast_data = {}
            base_date = datetime.strptime(sorted_dates[-1], '%Y-%m-%d')
            
            for i in range(1, forecast_days + 1):
                forecast_date = base_date + timedelta(days=i)
                predicted_value = max(0, intercept + slope * (n + i - 1))  # 确保预测值不为负
                forecast_data[forecast_date.strftime('%Y-%m-%d')] = round(predicted_value)
            
            # 计算预测准确性指标
            recent_actual = values[-7:]  # 最近7天实际值
            recent_predicted = [intercept + slope * (n - 7 + i) for i in range(7)]
            
            # 计算平均绝对误差百分比 (MAPE)
            mape = sum(abs(actual - predicted) / max(actual, 1) for actual, predicted in zip(recent_actual, recent_predicted)) / len(recent_actual) * 100
            
            forecast_summary = {
                'total_predicted_clicks': sum(forecast_data.values()),
                'avg_daily_predicted_clicks': sum(forecast_data.values()) / forecast_days,
                'trend_direction': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable',
                'trend_strength': abs(slope),
                'confidence_level': max(0, min(100, 100 - mape))  # 基于MAPE的置信度
            }
            
            logger.info(f"性能预测生成完成，预测 {forecast_days} 天")
            return {
                'forecast_available': True,
                'forecast_period_days': forecast_days,
                'daily_forecast': forecast_data,
                'forecast_summary': forecast_summary,
                'historical_data': {
                    'dates': sorted_dates,
                    'values': values
                },
                'model_accuracy': {
                    'mape': mape,
                    'confidence_level': forecast_summary['confidence_level']
                }
            }
            
        except Exception as e:
            logger.error(f"生成性能预测失败: {e}")
            raise

# 创建全局高级分析引擎实例
advanced_analytics_engine = AdvancedAnalyticsEngine()