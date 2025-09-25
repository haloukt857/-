"""
统计和报告系统模块
提供全面的统计数据生成、时间和按钮过滤、数据聚合和趋势分析功能
支持多种统计类型和格式化输出
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from utils.enums import MERCHANT_STATUS

# 数据库管理器导入
from database.db_logs import ActivityLogsDatabase, activity_logs_db
from database.db_binding_codes import BindingCodesDatabase, binding_codes_db
from database.db_merchants import MerchantManager, merchant_manager
from database.db_orders import OrderManager, order_manager
from database.db_templates import template_manager

# 配置日志
logger = logging.getLogger(__name__)


class StatsPeriod(Enum):
    """统计时间周期枚举"""

    TODAY = "today"
    YESTERDAY = "yesterday"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    ALL_TIME = "all_time"
    CUSTOM = "custom"


class StatsType(Enum):
    """统计类型枚举"""

    BUTTON_CLICKS = "button_clicks"
    USER_ACTIVITY = "user_activity"
    MERCHANT_PERFORMANCE = "merchant_performance"
    ORDER_ANALYTICS = "order_analytics"
    BINDING_CODES = "binding_codes"
    SYSTEM_HEALTH = "system_health"
    COMPREHENSIVE = "comprehensive"


@dataclass
class TimeRange:
    """时间范围数据类"""

    start_date: datetime
    end_date: datetime
    period_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "period_name": self.period_name,
        }


@dataclass
class StatsResult:
    """统计结果数据类"""

    stats_type: str
    time_range: TimeRange
    data: Dict[str, Any]
    generated_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stats_type": self.stats_type,
            "time_range": self.time_range.to_dict(),
            "data": self.data,
            "generated_at": self.generated_at.isoformat(),
        }


class StatisticsEngine:
    """
    统计引擎类
    提供全面的统计数据生成和分析功能
    """

    @staticmethod
    def get_time_range(
        period: StatsPeriod,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None,
    ) -> TimeRange:
        """
        根据周期获取时间范围

        Args:
            period: 统计周期
            custom_start: 自定义开始时间
            custom_end: 自定义结束时间

        Returns:
            时间范围对象
        """
        now = datetime.now()

        if period == StatsPeriod.TODAY:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            period_name = "今日"

        elif period == StatsPeriod.YESTERDAY:
            yesterday = now - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            period_name = "昨日"

        elif period == StatsPeriod.WEEK:
            # 本周（周一到现在）
            days_since_monday = now.weekday()
            start_date = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = now
            period_name = "本周"

        elif period == StatsPeriod.MONTH:
            # 本月
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            period_name = "本月"

        elif period == StatsPeriod.QUARTER:
            # 本季度
            quarter_start_month = ((now.month - 1) // 3) * 3 + 1
            start_date = now.replace(
                month=quarter_start_month,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = now
            period_name = "本季度"

        elif period == StatsPeriod.YEAR:
            # 本年
            start_date = now.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            end_date = now
            period_name = "本年"

        elif period == StatsPeriod.CUSTOM:
            # 自定义时间范围
            if not custom_start or not custom_end:
                raise ValueError("自定义时间范围需要提供开始和结束时间")
            start_date = custom_start
            end_date = custom_end
            period_name = (
                f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"
            )

        else:  # ALL_TIME
            start_date = datetime(2020, 1, 1)  # 假设系统从2020年开始
            end_date = now
            period_name = "全部时间"

        return TimeRange(start_date, end_date, period_name)

    @staticmethod
    async def generate_button_click_analytics(
        time_range: TimeRange,
        button_filter: Optional[str] = None,
        merchant_filter: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        生成按钮点击分析数据（纯调用层）

        Args:
            time_range: 时间范围
            button_filter: 按钮过滤器
            merchant_filter: 商户过滤器

        Returns:
            按钮点击分析数据
        """
        try:
            # 直接调用活动日志管理器的高效聚合查询方法
            analytics_data = (
                await ActivityLogsDatabase.get_comprehensive_button_analytics(
                    start_date=time_range.start_date,
                    end_date=time_range.end_date,
                    button_filter=button_filter,
                    merchant_filter=merchant_filter,
                )
            )

            # 添加时间范围信息
            analytics_data["time_range"] = time_range.to_dict()

            logger.info(f"按钮点击分析生成完成，时间范围: {time_range.period_name}")
            return analytics_data

        except Exception as e:
            logger.error(f"生成按钮点击分析失败: {e}")
            raise

    @staticmethod
    async def generate_user_activity_analytics(
        time_range: TimeRange, user_filter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        生成用户活动分析数据

        Args:
            time_range: 时间范围
            user_filter: 用户过滤器

        Returns:
            用户活动分析数据
        """
        try:
            # 获取活动统计
            activity_stats = await ActivityLogsDatabase.get_activity_statistics(
                start_date=time_range.start_date, end_date=time_range.end_date
            )

            # 用户分层分析
            user_segments = await StatisticsEngine._analyze_user_segments(time_range)

            # 用户留存分析
            retention_analysis = await StatisticsEngine._calculate_user_retention(
                time_range
            )

            # 活动类型分布
            activity_distribution = activity_stats["action_type_stats"]

            # 用户生命周期分析
            lifecycle_analysis = await StatisticsEngine._analyze_user_lifecycle(
                time_range
            )

            analytics_data = {
                "basic_metrics": {
                    "total_activities": activity_stats["total_activities"],
                    "active_users": activity_stats["active_users"],
                    "average_activities_per_user": activity_stats["total_activities"]
                    / max(activity_stats["active_users"], 1),
                },
                "top_users": activity_stats["top_users"],
                "activity_distribution": activity_distribution,
                "daily_activity": activity_stats["daily_activity"],
                "user_segments": user_segments,
                "retention_analysis": retention_analysis,
                "lifecycle_analysis": lifecycle_analysis,
                "time_range": time_range.to_dict(),
            }

            logger.info(f"用户活动分析生成完成，时间范围: {time_range.period_name}")
            return analytics_data

        except Exception as e:
            logger.error(f"生成用户活动分析失败: {e}")
            raise

    @staticmethod
    async def generate_merchant_performance_analytics(
        time_range: TimeRange, merchant_filter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        生成商户表现分析数据（纯调用层）

        Args:
            time_range: 时间范围
            merchant_filter: 商户过滤器

        Returns:
            商户表现分析数据
        """
        try:
            # 直接调用管理器的高效聚合查询方法
            analytics_data = await MerchantManager.get_merchant_performance_analytics(
                start_date=time_range.start_date,
                end_date=time_range.end_date,
                merchant_filter=merchant_filter,
            )

            # 添加时间范围信息
            analytics_data["time_range"] = time_range.to_dict()

            logger.info(f"商户表现分析生成完成，时间范围: {time_range.period_name}")
            return analytics_data

        except Exception as e:
            logger.error(f"生成商户表现分析失败: {e}")
            raise

    @staticmethod
    async def generate_order_analytics(
        time_range: TimeRange, merchant_filter: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        生成订单分析数据

        Args:
            time_range: 时间范围
            merchant_filter: 商户过滤器

        Returns:
            订单分析数据
        """
        try:
            # 获取订单数据
            if merchant_filter:
                orders = await OrderManager.get_orders_by_merchant(merchant_filter)
            else:
                orders = await OrderManager.get_orders_by_timeframe(
                    time_range.start_date, time_range.end_date
                )

            # 基础指标
            total_orders = len(orders)
            completed_orders = len([o for o in orders if o["status"] == "completed"])
            pending_orders = len([o for o in orders if o["status"] == "pending"])

            # 订单类型分析
            order_type_stats = {}
            for order in orders:
                order_type = order.get("order_type", "未知")
                order_type_stats[order_type] = order_type_stats.get(order_type, 0) + 1

            # 时间分布分析
            daily_orders = {}
            hourly_orders = {}

            for order in orders:
                order_date = datetime.fromisoformat(order["created_at"])
                date_key = order_date.strftime("%Y-%m-%d")
                hour_key = order_date.strftime("%H:00")

                daily_orders[date_key] = daily_orders.get(date_key, 0) + 1
                hourly_orders[hour_key] = hourly_orders.get(hour_key, 0) + 1

            # 商户订单分布
            merchant_order_stats = {}
            for order in orders:
                merchant_id = order["merchant_id"]
                merchant_order_stats[merchant_id] = (
                    merchant_order_stats.get(merchant_id, 0) + 1
                )

            # 价格分析（如果有价格数据）
            price_analysis = await StatisticsEngine._analyze_order_prices(orders)

            # 完成率分析
            completion_rate = (completed_orders / max(total_orders, 1)) * 100

            analytics_data = {
                "basic_metrics": {
                    "total_orders": total_orders,
                    "completed_orders": completed_orders,
                    "pending_orders": pending_orders,
                    "completion_rate": completion_rate,
                },
                "order_type_distribution": order_type_stats,
                "daily_distribution": daily_orders,
                "hourly_distribution": hourly_orders,
                "merchant_distribution": merchant_order_stats,
                "price_analysis": price_analysis,
                "time_range": time_range.to_dict(),
            }

            logger.info(f"订单分析生成完成，时间范围: {time_range.period_name}")
            return analytics_data

        except Exception as e:
            logger.error(f"生成订单分析失败: {e}")
            raise

    @staticmethod
    async def generate_binding_code_analytics(time_range: TimeRange) -> Dict[str, Any]:
        """
        生成绑定码分析数据

        Args:
            time_range: 时间范围

        Returns:
            绑定码分析数据
        """
        try:
            # 获取绑定码统计
            binding_stats = await BindingCodesDatabase.get_binding_code_statistics()

            # 获取所有绑定码
            all_codes = await BindingCodesDatabase.get_all_binding_codes(
                include_used=True, include_expired=True
            )

            # 时间范围内的绑定码
            period_codes = [
                code
                for code in all_codes
                if time_range.start_date
                <= datetime.fromisoformat(code["created_at"])
                <= time_range.end_date
            ]

            # 使用情况分析
            period_used = len([c for c in period_codes if c["is_used"]])
            period_expired = len(
                [
                    c
                    for c in period_codes
                    if c["expires_at"]
                    and datetime.fromisoformat(c["expires_at"]) < datetime.now()
                    and not c["is_used"]
                ]
            )

            # 使用时间分析
            usage_time_analysis = await StatisticsEngine._analyze_code_usage_time(
                period_codes
            )

            # 每日生成和使用趋势
            daily_generation = {}
            daily_usage = {}

            for code in period_codes:
                gen_date = datetime.fromisoformat(code["created_at"]).strftime(
                    "%Y-%m-%d"
                )
                daily_generation[gen_date] = daily_generation.get(gen_date, 0) + 1

                if code["is_used"] and code.get("used_at"):
                    use_date = datetime.fromisoformat(code["used_at"]).strftime(
                        "%Y-%m-%d"
                    )
                    daily_usage[use_date] = daily_usage.get(use_date, 0) + 1

            analytics_data = {
                "basic_metrics": {
                    "total_generated": len(period_codes),
                    "total_used": period_used,
                    "total_expired": period_expired,
                    "usage_rate": (period_used / max(len(period_codes), 1)) * 100,
                    "expiry_rate": (period_expired / max(len(period_codes), 1)) * 100,
                },
                "overall_stats": binding_stats,
                "daily_generation": daily_generation,
                "daily_usage": daily_usage,
                "usage_time_analysis": usage_time_analysis,
                "time_range": time_range.to_dict(),
            }

            logger.info(f"绑定码分析生成完成，时间范围: {time_range.period_name}")
            return analytics_data

        except Exception as e:
            logger.error(f"生成绑定码分析失败: {e}")
            raise

    @staticmethod
    async def generate_system_health_analytics(time_range: TimeRange) -> Dict[str, Any]:
        """
        生成系统健康度分析数据

        Args:
            time_range: 时间范围

        Returns:
            系统健康度分析数据
        """
        try:
            # 获取各类统计数据
            button_stats = await ActivityLogsDatabase.get_button_click_statistics(
                start_date=time_range.start_date, end_date=time_range.end_date
            )

            activity_stats = await ActivityLogsDatabase.get_activity_statistics(
                start_date=time_range.start_date, end_date=time_range.end_date
            )

            merchants = await MerchantManager.get_all_merchants()
            orders = await OrderManager.get_orders_by_timeframe(
                time_range.start_date, time_range.end_date
            )

            binding_stats = await BindingCodesDatabase.get_binding_code_statistics()

            # 计算健康度指标
            active_merchants = len([m for m in merchants if m["status"] == "active"])
            merchant_activation_rate = (active_merchants / max(len(merchants), 1)) * 100

            user_engagement_rate = (
                activity_stats["active_users"] / max(button_stats["unique_users"], 1)
            ) * 100

            order_conversion_rate = (
                len(orders) / max(button_stats["total_clicks"], 1)
            ) * 100

            binding_code_efficiency = binding_stats["usage_rate"]

            # 系统活跃度
            system_activity_score = min(
                100,
                (
                    merchant_activation_rate * 0.3
                    + user_engagement_rate * 0.3
                    + order_conversion_rate * 0.2
                    + binding_code_efficiency * 0.2
                ),
            )

            # 错误率分析
            error_logs = await ActivityLogsDatabase.get_recent_activities(
                limit=1000, action_type="error_event"
            )

            period_errors = [
                log
                for log in error_logs
                if time_range.start_date
                <= datetime.fromisoformat(log["timestamp"])
                <= time_range.end_date
            ]

            error_rate = (
                len(period_errors) / max(activity_stats["total_activities"], 1)
            ) * 100

            # 性能指标
            performance_metrics = {
                "average_response_time": 0,  # 需要实际测量
                "uptime_percentage": 99.9,  # 需要实际监控
                "concurrent_users": button_stats["unique_users"],
            }

            analytics_data = {
                "health_score": {
                    "overall_score": system_activity_score,
                    "merchant_activation_rate": merchant_activation_rate,
                    "user_engagement_rate": user_engagement_rate,
                    "order_conversion_rate": order_conversion_rate,
                    "binding_code_efficiency": binding_code_efficiency,
                },
                "system_metrics": {
                    "total_merchants": len(merchants),
                    "active_merchants": active_merchants,
                    "total_users": button_stats["unique_users"],
                    "active_users": activity_stats["active_users"],
                    "total_orders": len(orders),
                    "error_rate": error_rate,
                },
                "performance_metrics": performance_metrics,
                "error_analysis": {
                    "total_errors": len(period_errors),
                    "error_rate": error_rate,
                    "error_types": {},  # 可以进一步分析错误类型
                },
                "time_range": time_range.to_dict(),
            }

            logger.info(f"系统健康度分析生成完成，时间范围: {time_range.period_name}")
            return analytics_data

        except Exception as e:
            logger.error(f"生成系统健康度分析失败: {e}")
            raise

    # 辅助分析方法
    @staticmethod
    async def _calculate_engagement_metrics(
        time_range: TimeRange, button_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算用户参与度指标"""
        try:
            total_clicks = button_stats["total_clicks"]
            unique_users = button_stats["unique_users"]

            # 参与度指标
            engagement_metrics = {
                "click_frequency": total_clicks / max(unique_users, 1),
                "user_retention_rate": 0,  # 需要更复杂的计算
                "session_duration": 0,  # 需要会话跟踪
                "bounce_rate": 0,  # 需要定义跳出标准
            }

            return engagement_metrics

        except Exception as e:
            logger.error(f"计算参与度指标失败: {e}")
            return {}

    @staticmethod
    async def _calculate_trend_analysis(
        time_range: TimeRange, daily_stats: Dict[str, int]
    ) -> Dict[str, Any]:
        """计算趋势分析"""
        try:
            if not daily_stats or len(daily_stats) < 2:
                return {"trend": "insufficient_data", "growth_rate": 0}

            # 按日期排序
            sorted_dates = sorted(daily_stats.keys())
            values = [daily_stats[date] for date in sorted_dates]

            # 计算增长率
            if len(values) >= 2:
                recent_avg = sum(values[-3:]) / min(3, len(values))
                earlier_avg = sum(values[:3]) / min(3, len(values))

                if earlier_avg > 0:
                    growth_rate = ((recent_avg - earlier_avg) / earlier_avg) * 100
                else:
                    growth_rate = 0

                # 判断趋势
                if growth_rate > 10:
                    trend = "increasing"
                elif growth_rate < -10:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                growth_rate = 0
                trend = "stable"

            return {
                "trend": trend,
                "growth_rate": growth_rate,
                "data_points": len(values),
            }

        except Exception as e:
            logger.error(f"计算趋势分析失败: {e}")
            return {"trend": "error", "growth_rate": 0}

    @staticmethod
    async def _analyze_peak_hours(
        time_range: TimeRange, hourly_stats: Dict[str, int]
    ) -> Dict[str, Any]:
        """分析高峰时段"""
        try:
            if not hourly_stats:
                return {"peak_hour": None, "peak_clicks": 0, "quiet_hour": None}

            # 找出最高和最低活跃时段
            sorted_hours = sorted(
                hourly_stats.items(), key=lambda x: x[1], reverse=True
            )

            peak_analysis = {
                "peak_hour": sorted_hours[0][0] if sorted_hours else None,
                "peak_clicks": sorted_hours[0][1] if sorted_hours else 0,
                "quiet_hour": sorted_hours[-1][0] if sorted_hours else None,
                "quiet_clicks": sorted_hours[-1][1] if sorted_hours else 0,
                "hourly_distribution": hourly_stats,
            }

            return peak_analysis

        except Exception as e:
            logger.error(f"分析高峰时段失败: {e}")
            return {}

    @staticmethod
    async def _analyze_user_segments(time_range: TimeRange) -> Dict[str, Any]:
        """分析用户分层"""
        try:
            # 获取用户活动数据
            recent_activities = await ActivityLogsDatabase.get_recent_activities(
                limit=10000
            )

            # 按用户分组统计
            user_activity_count = {}
            for activity in recent_activities:
                if activity["user_id"]:
                    user_id = activity["user_id"]
                    user_activity_count[user_id] = (
                        user_activity_count.get(user_id, 0) + 1
                    )

            # 用户分层
            high_activity_users = len(
                [u for u in user_activity_count.values() if u >= 10]
            )
            medium_activity_users = len(
                [u for u in user_activity_count.values() if 3 <= u < 10]
            )
            low_activity_users = len([u for u in user_activity_count.values() if u < 3])

            segments = {
                "high_activity": high_activity_users,
                "medium_activity": medium_activity_users,
                "low_activity": low_activity_users,
                "total_users": len(user_activity_count),
            }

            return segments

        except Exception as e:
            logger.error(f"分析用户分层失败: {e}")
            return {}

    @staticmethod
    async def _calculate_user_retention(time_range: TimeRange) -> Dict[str, Any]:
        """计算用户留存率"""
        try:
            # 简化的留存率计算
            # 实际实现需要更复杂的用户行为跟踪
            retention_analysis = {
                "day_1_retention": 0,
                "day_7_retention": 0,
                "day_30_retention": 0,
                "note": "需要更长时间的数据积累来计算准确的留存率",
            }

            return retention_analysis

        except Exception as e:
            logger.error(f"计算用户留存率失败: {e}")
            return {}

    @staticmethod
    async def _analyze_user_lifecycle(time_range: TimeRange) -> Dict[str, Any]:
        """分析用户生命周期"""
        try:
            # 用户生命周期分析
            lifecycle_analysis = {
                "new_users": 0,
                "active_users": 0,
                "returning_users": 0,
                "churned_users": 0,
                "note": "需要用户首次访问时间数据来进行准确分析",
            }

            return lifecycle_analysis

        except Exception as e:
            logger.error(f"分析用户生命周期失败: {e}")
            return {}

    @staticmethod
    async def _analyze_merchant_by_region(
        merchant_metrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """按地区分析商户"""
        try:
            region_stats = {}
            for merchant in merchant_metrics:
                # 使用结构化地区名称
                region = merchant.get("region_display") or "未设置"
                if region not in region_stats:
                    region_stats[region] = {
                        "merchant_count": 0,
                        "total_interactions": 0,
                        "total_orders": 0,
                    }

                region_stats[region]["merchant_count"] += 1
                region_stats[region]["total_interactions"] += merchant[
                    "total_interactions"
                ]
                region_stats[region]["total_orders"] += merchant["total_orders"]

            # 计算平均值
            for region, stats in region_stats.items():
                stats["avg_interactions"] = (
                    stats["total_interactions"] / stats["merchant_count"]
                )
                stats["avg_orders"] = stats["total_orders"] / stats["merchant_count"]

            return region_stats

        except Exception as e:
            logger.error(f"按地区分析商户失败: {e}")
            return {}

    @staticmethod
    async def _analyze_merchant_by_category(
        merchant_metrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """按类别分析商户"""
        try:
            category_stats = {}
            for merchant in merchant_metrics:
                # 使用结构化类型 merchant_type 代替旧 category
                category = merchant.get("merchant_type") or "unknown"
                if category not in category_stats:
                    category_stats[category] = {
                        "merchant_count": 0,
                        "total_interactions": 0,
                        "total_orders": 0,
                    }

                category_stats[category]["merchant_count"] += 1
                category_stats[category]["total_interactions"] += merchant[
                    "total_interactions"
                ]
                category_stats[category]["total_orders"] += merchant["total_orders"]

            # 计算平均值
            for category, stats in category_stats.items():
                stats["avg_interactions"] = (
                    stats["total_interactions"] / stats["merchant_count"]
                )
                stats["avg_orders"] = stats["total_orders"] / stats["merchant_count"]

            return category_stats

        except Exception as e:
            logger.error(f"按类别分析商户失败: {e}")
            return {}

    @staticmethod
    async def _categorize_merchant_performance(
        merchant_metrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """商户表现分层"""
        try:
            if not merchant_metrics:
                return {}

            # 按交互数排序
            sorted_merchants = sorted(
                merchant_metrics, key=lambda x: x["total_interactions"], reverse=True
            )
            total_merchants = len(sorted_merchants)

            # 分层标准（基于交互数）
            high_performers = []
            medium_performers = []
            low_performers = []

            for merchant in sorted_merchants:
                interactions = merchant["total_interactions"]
                if interactions >= 50:  # 高表现商户
                    high_performers.append(merchant)
                elif interactions >= 10:  # 中等表现商户
                    medium_performers.append(merchant)
                else:  # 低表现商户
                    low_performers.append(merchant)

            performance_tiers = {
                "high_performers": {
                    "count": len(high_performers),
                    "percentage": (len(high_performers) / total_merchants) * 100
                    if total_merchants > 0
                    else 0,
                    "avg_interactions": sum(
                        m["total_interactions"] for m in high_performers
                    )
                    / len(high_performers)
                    if high_performers
                    else 0,
                    "avg_orders": sum(m["total_orders"] for m in high_performers)
                    / len(high_performers)
                    if high_performers
                    else 0,
                },
                "medium_performers": {
                    "count": len(medium_performers),
                    "percentage": (len(medium_performers) / total_merchants) * 100
                    if total_merchants > 0
                    else 0,
                    "avg_interactions": sum(
                        m["total_interactions"] for m in medium_performers
                    )
                    / len(medium_performers)
                    if medium_performers
                    else 0,
                    "avg_orders": sum(m["total_orders"] for m in medium_performers)
                    / len(medium_performers)
                    if medium_performers
                    else 0,
                },
                "low_performers": {
                    "count": len(low_performers),
                    "percentage": (len(low_performers) / total_merchants) * 100
                    if total_merchants > 0
                    else 0,
                    "avg_interactions": sum(
                        m["total_interactions"] for m in low_performers
                    )
                    / len(low_performers)
                    if low_performers
                    else 0,
                    "avg_orders": sum(m["total_orders"] for m in low_performers)
                    / len(low_performers)
                    if low_performers
                    else 0,
                },
            }

            return performance_tiers

        except Exception as e:
            logger.error(f"商户表现分层失败: {e}")
            return {}

    @staticmethod
    async def _analyze_order_prices(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析订单价格"""
        try:
            orders_with_price = [
                order
                for order in orders
                if order.get("price") and float(order["price"]) > 0
            ]

            if not orders_with_price:
                return {
                    "total_orders_with_price": 0,
                    "average_price": 0,
                    "total_revenue": 0,
                    "min_price": 0,
                    "max_price": 0,
                }

            prices = [float(order["price"]) for order in orders_with_price]

            price_analysis = {
                "total_orders_with_price": len(orders_with_price),
                "average_price": sum(prices) / len(prices),
                "total_revenue": sum(prices),
                "min_price": min(prices),
                "max_price": max(prices),
                "price_ranges": {
                    "under_100": len([p for p in prices if p < 100]),
                    "100_to_500": len([p for p in prices if 100 <= p < 500]),
                    "500_to_1000": len([p for p in prices if 500 <= p < 1000]),
                    "over_1000": len([p for p in prices if p >= 1000]),
                },
            }

            return price_analysis

        except Exception as e:
            logger.error(f"分析订单价格失败: {e}")
            return {}

    @staticmethod
    async def _analyze_code_usage_time(codes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析绑定码使用时间"""
        try:
            used_codes = [
                code for code in codes if code["is_used"] and code.get("used_at")
            ]

            if not used_codes:
                return {
                    "average_usage_time": 0,
                    "quick_usage_count": 0,
                    "delayed_usage_count": 0,
                    "usage_time_distribution": {},
                }

            usage_times = []
            quick_usage_count = 0
            delayed_usage_count = 0

            for code in used_codes:
                created_at = datetime.fromisoformat(code["created_at"])
                used_at = datetime.fromisoformat(code["used_at"])
                usage_time_hours = (used_at - created_at).total_seconds() / 3600

                usage_times.append(usage_time_hours)

                if usage_time_hours <= 1:  # 1小时内使用
                    quick_usage_count += 1
                elif usage_time_hours >= 24:  # 24小时后使用
                    delayed_usage_count += 1

            # 使用时间分布
            usage_time_distribution = {
                "within_1_hour": len([t for t in usage_times if t <= 1]),
                "1_to_6_hours": len([t for t in usage_times if 1 < t <= 6]),
                "6_to_24_hours": len([t for t in usage_times if 6 < t <= 24]),
                "1_to_7_days": len([t for t in usage_times if 24 < t <= 168]),
                "over_7_days": len([t for t in usage_times if t > 168]),
            }

            usage_time_analysis = {
                "average_usage_time": sum(usage_times) / len(usage_times)
                if usage_times
                else 0,
                "quick_usage_count": quick_usage_count,
                "delayed_usage_count": delayed_usage_count,
                "usage_time_distribution": usage_time_distribution,
                "median_usage_time": sorted(usage_times)[len(usage_times) // 2]
                if usage_times
                else 0,
            }

            return usage_time_analysis

        except Exception as e:
            logger.error(f"分析绑定码使用时间失败: {e}")
            return {}
            logger.error(f"按类别分析商户失败: {e}")
            return {}

    @staticmethod
    async def _categorize_merchant_performance(
        merchant_metrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """商户表现分层"""
        try:
            if not merchant_metrics:
                return {}

            # 按交互数量分层
            interactions = [m["total_interactions"] for m in merchant_metrics]
            interactions.sort(reverse=True)

            # 计算分位数
            total_merchants = len(interactions)
            top_20_percent = max(1, total_merchants // 5)
            top_50_percent = max(1, total_merchants // 2)

            performance_tiers = {
                "top_performers": {
                    "count": top_20_percent,
                    "min_interactions": interactions[top_20_percent - 1]
                    if top_20_percent <= len(interactions)
                    else 0,
                    "merchants": merchant_metrics[:top_20_percent],
                },
                "good_performers": {
                    "count": top_50_percent - top_20_percent,
                    "min_interactions": interactions[top_50_percent - 1]
                    if top_50_percent <= len(interactions)
                    else 0,
                    "merchants": merchant_metrics[top_20_percent:top_50_percent],
                },
                "average_performers": {
                    "count": total_merchants - top_50_percent,
                    "merchants": merchant_metrics[top_50_percent:],
                },
            }

            return performance_tiers

        except Exception as e:
            logger.error(f"商户表现分层失败: {e}")
            return {}

    @staticmethod
    async def _analyze_order_prices(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析订单价格"""
        try:
            prices = [
                float(order.get("price", 0)) for order in orders if order.get("price")
            ]

            if not prices:
                return {"note": "没有价格数据"}

            prices.sort()
            total_orders = len(prices)

            price_analysis = {
                "total_revenue": sum(prices),
                "average_price": sum(prices) / total_orders,
                "median_price": prices[total_orders // 2],
                "min_price": min(prices),
                "max_price": max(prices),
                "price_range": max(prices) - min(prices),
            }

            return price_analysis

        except Exception as e:
            logger.error(f"分析订单价格失败: {e}")
            return {}

    @staticmethod
    async def _analyze_code_usage_time(codes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析绑定码使用时间"""
        try:
            usage_times = []

            for code in codes:
                if code["is_used"] and code.get("used_at"):
                    created_at = datetime.fromisoformat(code["created_at"])
                    used_at = datetime.fromisoformat(code["used_at"])
                    usage_time = (used_at - created_at).total_seconds() / 3600  # 转换为小时
                    usage_times.append(usage_time)

            if not usage_times:
                return {"note": "没有使用时间数据"}

            usage_times.sort()
            total_used = len(usage_times)

            usage_analysis = {
                "average_usage_time_hours": sum(usage_times) / total_used,
                "median_usage_time_hours": usage_times[total_used // 2],
                "fastest_usage_hours": min(usage_times),
                "slowest_usage_hours": max(usage_times),
                "quick_usage_count": len([t for t in usage_times if t <= 1]),  # 1小时内使用
                "delayed_usage_count": len(
                    [t for t in usage_times if t > 12]
                ),  # 12小时后使用
            }

            return usage_analysis

        except Exception as e:
            logger.error(f"分析绑定码使用时间失败: {e}")
            return {}


class StatisticsFormatter:
    """
    统计数据格式化器
    将统计数据格式化为用户友好的文本格式
    """

    @staticmethod
    async def format_comprehensive_stats(stats_result: StatsResult) -> str:
        """
        格式化综合统计数据（使用模板系统）

        Args:
            stats_result: 统计结果对象

        Returns:
            格式化的统计文本
        """
        try:
            data = stats_result.data
            time_range = stats_result.time_range

            # 使用模板系统
            template = await template_manager.get_template(
                "stats_comprehensive_report",
                default="""
📊 {period_name}综合统计报告

⏰ 统计时间: {generated_at}
📅 数据范围: {start_date} 至 {end_date}

🔘 按钮数据:
• 总点击数: {total_clicks:,}
• 独立用户: {unique_users:,}
• 平均点击: {avg_clicks:.1f}

👥 用户数据:
• 总活动数: {total_activities:,}
• 活跃用户: {active_users:,}

🏪 商户数据:
• 总商户数: {total_merchants:,}
• 活跃商户: {active_merchants:,}

📋 订单数据:
• 总订单数: {total_orders:,}
• 完成订单: {completed_orders:,}
• 完成率: {completion_rate:.1f}%

🔑 绑定码数据:
• 总生成数: {total_generated:,}
• 使用率: {usage_rate:.1f}%

📈 系统健康度:
• 综合评分: {overall_score:.1f}/100
• 商户激活率: {merchant_activation_rate:.1f}%
• 用户参与度: {user_engagement_rate:.1f}%
• 订单转化率: {order_conversion_rate:.1f}%
""",
            )

            # 格式化数据
            formatted_text = template.format(
                period_name=time_range.period_name,
                generated_at=stats_result.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
                start_date=time_range.start_date.strftime("%Y-%m-%d"),
                end_date=time_range.end_date.strftime("%Y-%m-%d"),
                total_clicks=data.get("button_clicks", {}).get("total_clicks", 0),
                unique_users=data.get("button_clicks", {}).get("unique_users", 0),
                avg_clicks=data.get("button_clicks", {}).get(
                    "average_clicks_per_user", 0
                ),
                total_activities=data.get("user_activity", {}).get(
                    "total_activities", 0
                ),
                active_users=data.get("user_activity", {}).get("active_users", 0),
                total_merchants=data.get("merchant_performance", {}).get(
                    "total_merchants", 0
                ),
                active_merchants=data.get("merchant_performance", {}).get(
                    "active_merchants", 0
                ),
                total_orders=data.get("order_analytics", {}).get("total_orders", 0),
                completed_orders=data.get("order_analytics", {}).get(
                    "completed_orders", 0
                ),
                completion_rate=data.get("order_analytics", {}).get(
                    "completion_rate", 0
                ),
                total_generated=data.get("binding_codes", {}).get("total_generated", 0),
                usage_rate=data.get("binding_codes", {}).get("usage_rate", 0),
                overall_score=data.get("system_health", {}).get("overall_score", 0),
                merchant_activation_rate=data.get("system_health", {}).get(
                    "merchant_activation_rate", 0
                ),
                user_engagement_rate=data.get("system_health", {}).get(
                    "user_engagement_rate", 0
                ),
                order_conversion_rate=data.get("system_health", {}).get(
                    "order_conversion_rate", 0
                ),
            )

            return formatted_text.strip()

        except Exception as e:
            logger.error(f"格式化综合统计失败: {e}")
            error_template = await template_manager.get_template(
                "error_stats_format_failed", default="❌ 格式化统计数据失败"
            )
            return error_template

    @staticmethod
    def format_button_stats(stats_result: StatsResult) -> str:
        """格式化按钮统计数据"""
        try:
            data = stats_result.data
            time_range = stats_result.time_range

            formatted_text = f"""
🔘 {time_range.period_name}按钮点击统计

📊 基础指标:
• 总点击数: {data.get('basic_metrics', {}).get('total_clicks', 0):,}
• 独立用户: {data.get('basic_metrics', {}).get('unique_users', 0):,}
• 平均点击: {data.get('basic_metrics', {}).get('average_clicks_per_user', 0):.1f}
• 点击率: {data.get('basic_metrics', {}).get('click_through_rate', 0):.1f}%

🏆 热门按钮排行:
            """

            # 添加按钮排行
            button_performance = data.get("button_performance", {})
            sorted_buttons = sorted(
                button_performance.items(),
                key=lambda x: x[1].get("clicks", 0),
                reverse=True,
            )

            for i, (button_id, stats) in enumerate(sorted_buttons[:10], 1):
                formatted_text += f"\n{i}. {button_id}"
                formatted_text += f"\n   点击: {stats.get('clicks', 0)} | 用户: {stats.get('unique_users', 0)}"

            # 添加趋势分析
            trend_analysis = data.get("trend_analysis", {})
            if trend_analysis:
                trend_emoji = (
                    "📈"
                    if trend_analysis.get("trend") == "increasing"
                    else "📉"
                    if trend_analysis.get("trend") == "decreasing"
                    else "➡️"
                )
                formatted_text += f"\n\n{trend_emoji} 趋势分析:"
                formatted_text += f"\n• 趋势: {trend_analysis.get('trend', '未知')}"
                formatted_text += (
                    f"\n• 增长率: {trend_analysis.get('growth_rate', 0):.1f}%"
                )

            # 添加高峰时段
            peak_hours = data.get("peak_hours", {})
            if peak_hours.get("peak_hour"):
                formatted_text += f"\n\n⏰ 活跃时段:"
                formatted_text += f"\n• 高峰时段: {peak_hours.get('peak_hour')} ({peak_hours.get('peak_clicks', 0)}次点击)"
                formatted_text += f"\n• 低谷时段: {peak_hours.get('quiet_hour')} ({peak_hours.get('quiet_clicks', 0)}次点击)"

            return formatted_text.strip()

        except Exception as e:
            logger.error(f"格式化按钮统计失败: {e}")
            return "❌ 格式化按钮统计失败"

    @staticmethod
    def format_merchant_stats(stats_result: StatsResult) -> str:
        """格式化商户统计数据"""
        try:
            data = stats_result.data
            time_range = stats_result.time_range

            formatted_text = f"""
🏪 {time_range.period_name}商户表现统计

📊 基础指标:
• 总商户数: {data.get('basic_metrics', {}).get('total_merchants', 0):,}
• 活跃商户: {data.get('basic_metrics', {}).get('active_merchants', 0):,}
• 平均交互数: {data.get('basic_metrics', {}).get('average_interactions_per_merchant', 0):.1f}
• 平均订单数: {data.get('basic_metrics', {}).get('average_orders_per_merchant', 0):.1f}

🏆 商户排行榜:
            """

            # 添加商户排行
            merchant_rankings = data.get("merchant_rankings", [])
            for i, merchant in enumerate(merchant_rankings[:10], 1):
                formatted_text += f"\n{i}. {merchant.get('merchant_name', '未知商户')}"
                formatted_text += f"\n   交互: {merchant.get('total_interactions', 0)} | 订单: {merchant.get('total_orders', 0)} | 转化率: {merchant.get('conversion_rate', 0):.1f}%"

            # 添加地区分析
            region_analysis = data.get("region_analysis", {})
            if region_analysis:
                formatted_text += f"\n\n🌍 地区分布:"
                sorted_regions = sorted(
                    region_analysis.items(),
                    key=lambda x: x[1].get("merchant_count", 0),
                    reverse=True,
                )
                for region, stats in sorted_regions[:5]:
                    formatted_text += f"\n• {region}: {stats.get('merchant_count', 0)}个商户 (平均{stats.get('avg_interactions', 0):.1f}次交互)"

            # 添加类别分析
            category_analysis = data.get("category_analysis", {})
            if category_analysis:
                formatted_text += f"\n\n🏷️ 类别分布:"
                sorted_categories = sorted(
                    category_analysis.items(),
                    key=lambda x: x[1].get("merchant_count", 0),
                    reverse=True,
                )
                for category, stats in sorted_categories[:5]:
                    formatted_text += f"\n• {category}: {stats.get('merchant_count', 0)}个商户 (平均{stats.get('avg_orders', 0):.1f}个订单)"

            return formatted_text.strip()

        except Exception as e:
            logger.error(f"格式化商户统计失败: {e}")
            return "❌ 格式化商户统计失败"

    @staticmethod
    def format_user_activity_stats(stats_result: StatsResult) -> str:
        """格式化用户活动统计数据"""
        try:
            data = stats_result.data
            time_range = stats_result.time_range

            formatted_text = f"""
👥 {time_range.period_name}用户活动统计

📊 基础指标:
• 总活动数: {data.get('basic_metrics', {}).get('total_activities', 0):,}
• 活跃用户: {data.get('basic_metrics', {}).get('active_users', 0):,}
• 平均活动: {data.get('basic_metrics', {}).get('average_activities_per_user', 0):.1f}

🏆 最活跃用户:
            """

            # 最活跃用户排行
            top_users = data.get("top_users", [])
            for i, user in enumerate(top_users[:10], 1):
                formatted_text += f"\n{i}. 用户 {user.get('user_id', '未知')}: {user.get('activity_count', 0)}次活动"

            # 活动类型分布
            activity_distribution = data.get("activity_distribution", {})
            if activity_distribution:
                formatted_text += "\n\n📋 活动类型分布:"
                sorted_activities = sorted(
                    activity_distribution.items(), key=lambda x: x[1], reverse=True
                )
                for action_type, count in sorted_activities[:5]:
                    formatted_text += f"\n• {action_type}: {count:,}次"

            # 用户分层
            user_segments = data.get("user_segments", {})
            if user_segments:
                formatted_text += f"\n\n👥 用户分层:"
                formatted_text += (
                    f"\n• 高活跃用户: {user_segments.get('high_activity', 0):,}"
                )
                formatted_text += (
                    f"\n• 中活跃用户: {user_segments.get('medium_activity', 0):,}"
                )
                formatted_text += f"\n• 低活跃用户: {user_segments.get('low_activity', 0):,}"

            # 留存分析
            retention_analysis = data.get("retention_analysis", {})
            if retention_analysis and retention_analysis.get("note"):
                formatted_text += f"\n\n📈 留存分析:"
                formatted_text += f"\n• {retention_analysis.get('note', '暂无数据')}"

            return formatted_text.strip()

        except Exception as e:
            logger.error(f"格式化用户活动统计失败: {e}")
            return "❌ 格式化用户活动统计失败"

    @staticmethod
    def format_order_analytics(stats_result: StatsResult) -> str:
        """格式化订单分析数据"""
        try:
            data = stats_result.data
            time_range = stats_result.time_range

            formatted_text = f"""
📋 {time_range.period_name}订单分析统计

📊 基础指标:
• 总订单数: {data.get('basic_metrics', {}).get('total_orders', 0):,}
• 完成订单: {data.get('basic_metrics', {}).get('completed_orders', 0):,}
• 待处理订单: {data.get('basic_metrics', {}).get('pending_orders', 0):,}
• 完成率: {data.get('basic_metrics', {}).get('completion_rate', 0):.1f}%

📈 订单类型分布:
            """

            # 订单类型分布
            order_type_distribution = data.get("order_type_distribution", {})
            for order_type, count in sorted(
                order_type_distribution.items(), key=lambda x: x[1], reverse=True
            ):
                formatted_text += f"\n• {order_type}: {count:,}个订单"

            # 商户订单分布（前10名）
            merchant_distribution = data.get("merchant_distribution", {})
            if merchant_distribution:
                formatted_text += f"\n\n🏪 商户订单排行:"
                sorted_merchants = sorted(
                    merchant_distribution.items(), key=lambda x: x[1], reverse=True
                )
                for i, (merchant_id, count) in enumerate(sorted_merchants[:10], 1):
                    formatted_text += f"\n{i}. 商户 {merchant_id}: {count:,}个订单"

            # 时间分布分析
            daily_distribution = data.get("daily_distribution", {})
            if daily_distribution:
                formatted_text += f"\n\n📅 每日订单趋势:"
                sorted_days = sorted(
                    daily_distribution.items(), key=lambda x: x[0], reverse=True
                )
                for date, count in sorted_days[:7]:  # 显示最近7天
                    formatted_text += f"\n• {date}: {count:,}个订单"

            # 价格分析
            price_analysis = data.get("price_analysis", {})
            if price_analysis and price_analysis.get("total_orders_with_price", 0) > 0:
                formatted_text += f"\n\n💰 价格分析:"
                formatted_text += (
                    f"\n• 平均价格: ¥{price_analysis.get('average_price', 0):.2f}"
                )
                formatted_text += (
                    f"\n• 总收入: ¥{price_analysis.get('total_revenue', 0):.2f}"
                )
                formatted_text += (
                    f"\n• 有价格订单: {price_analysis.get('total_orders_with_price', 0):,}"
                )

            return formatted_text.strip()

        except Exception as e:
            logger.error(f"格式化订单分析失败: {e}")
            return "❌ 格式化订单分析失败"

    @staticmethod
    def format_binding_code_analytics(stats_result: StatsResult) -> str:
        """格式化绑定码分析数据"""
        try:
            data = stats_result.data
            time_range = stats_result.time_range

            formatted_text = f"""
🔑 {time_range.period_name}绑定码分析统计

📊 基础指标:
• 总生成数: {data.get('basic_metrics', {}).get('total_generated', 0):,}
• 已使用数: {data.get('basic_metrics', {}).get('total_used', 0):,}
• 已过期数: {data.get('basic_metrics', {}).get('total_expired', 0):,}
• 使用率: {data.get('basic_metrics', {}).get('usage_rate', 0):.1f}%
• 过期率: {data.get('basic_metrics', {}).get('expiry_rate', 0):.1f}%

📈 使用趋势:
            """

            # 每日生成趋势
            daily_generation = data.get("daily_generation", {})
            if daily_generation:
                formatted_text += f"\n\n📅 每日生成趋势:"
                sorted_days = sorted(
                    daily_generation.items(), key=lambda x: x[0], reverse=True
                )
                for date, count in sorted_days[:7]:  # 显示最近7天
                    formatted_text += f"\n• {date}: {count:,}个绑定码"

            # 每日使用趋势
            daily_usage = data.get("daily_usage", {})
            if daily_usage:
                formatted_text += f"\n\n✅ 每日使用趋势:"
                sorted_usage_days = sorted(
                    daily_usage.items(), key=lambda x: x[0], reverse=True
                )
                for date, count in sorted_usage_days[:7]:  # 显示最近7天
                    formatted_text += f"\n• {date}: {count:,}个绑定码被使用"

            # 使用时间分析
            usage_time_analysis = data.get("usage_time_analysis", {})
            if usage_time_analysis:
                formatted_text += f"\n\n⏱️ 使用时间分析:"
                if usage_time_analysis.get("average_usage_time"):
                    formatted_text += f"\n• 平均使用时间: {usage_time_analysis.get('average_usage_time', 0):.1f}小时"
                if usage_time_analysis.get("quick_usage_count"):
                    formatted_text += f"\n• 快速使用(1小时内): {usage_time_analysis.get('quick_usage_count', 0):,}个"
                if usage_time_analysis.get("delayed_usage_count"):
                    formatted_text += f"\n• 延迟使用(24小时后): {usage_time_analysis.get('delayed_usage_count', 0):,}个"

            # 整体统计
            overall_stats = data.get("overall_stats", {})
            if overall_stats:
                formatted_text += f"\n\n📊 历史总览:"
                formatted_text += (
                    f"\n• 历史总生成: {overall_stats.get('total_generated', 0):,}"
                )
                formatted_text += f"\n• 历史总使用: {overall_stats.get('total_used', 0):,}"
                formatted_text += (
                    f"\n• 历史使用率: {overall_stats.get('usage_rate', 0):.1f}%"
                )

            return formatted_text.strip()

        except Exception as e:
            logger.error(f"格式化绑定码分析失败: {e}")
            return "❌ 格式化绑定码分析失败"

    @staticmethod
    def format_system_health_analytics(stats_result: StatsResult) -> str:
        """格式化系统健康度分析数据"""
        try:
            data = stats_result.data
            time_range = stats_result.time_range

            # 获取健康度评分
            health_score = data.get("health_score", {})
            overall_score = health_score.get("overall_score", 0)

            # 根据评分确定健康状态
            if overall_score >= 80:
                health_status = "🟢 优秀"
                health_emoji = "🟢"
            elif overall_score >= 60:
                health_status = "🟡 良好"
                health_emoji = "🟡"
            elif overall_score >= 40:
                health_status = "🟠 一般"
                health_emoji = "🟠"
            else:
                health_status = "🔴 需要改进"
                health_emoji = "🔴"

            formatted_text = f"""
📈 {time_range.period_name}系统健康度分析

{health_emoji} 整体健康状态: {health_status} ({overall_score:.1f}/100)

📊 核心指标:
• 商户激活率: {health_score.get('merchant_activation_rate', 0):.1f}%
• 用户参与度: {health_score.get('user_engagement_rate', 0):.1f}%
• 订单转化率: {health_score.get('order_conversion_rate', 0):.1f}%
• 绑定码效率: {health_score.get('binding_code_efficiency', 0):.1f}%

🔢 系统指标:
• 总商户数: {data.get('system_metrics', {}).get('total_merchants', 0):,}
• 活跃商户: {data.get('system_metrics', {}).get('active_merchants', 0):,}
• 总用户数: {data.get('system_metrics', {}).get('total_users', 0):,}
• 活跃用户: {data.get('system_metrics', {}).get('active_users', 0):,}
• 总订单数: {data.get('system_metrics', {}).get('total_orders', 0):,}

⚡ 性能指标:
• 并发用户数: {data.get('performance_metrics', {}).get('concurrent_users', 0):,}
• 系统正常运行时间: {data.get('performance_metrics', {}).get('uptime_percentage', 0):.1f}%
            """

            # 错误分析
            error_analysis = data.get("error_analysis", {})
            if error_analysis:
                error_rate = error_analysis.get("error_rate", 0)
                error_emoji = "🟢" if error_rate < 1 else "🟡" if error_rate < 5 else "🔴"
                formatted_text += f"\n\n{error_emoji} 错误分析:"
                formatted_text += f"\n• 错误率: {error_rate:.2f}%"
                formatted_text += f"\n• 错误总数: {error_analysis.get('total_errors', 0):,}"

            # 系统建议
            formatted_text += f"\n\n💡 系统建议:"
            if overall_score >= 80:
                formatted_text += f"\n• 系统运行良好，继续保持当前状态"
            elif overall_score >= 60:
                formatted_text += f"\n• 系统整体良好，可优化用户参与度"
            elif overall_score >= 40:
                formatted_text += f"\n• 建议关注商户激活和用户转化"
            else:
                formatted_text += f"\n• 系统需要重点优化，建议检查核心功能"

            return formatted_text.strip()

        except Exception as e:
            logger.error(f"格式化系统健康度分析失败: {e}")
            return "❌ 格式化系统健康度分析失败"


# 创建全局统计引擎实例
statistics_engine = StatisticsEngine()
statistics_formatter = StatisticsFormatter()
