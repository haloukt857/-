# -*- coding: utf-8 -*-
"""
评价数据库管理器

负责与 `reviews` 和 `merchant_scores` 表相关的所有数据库操作。
实现双向评价系统的完整功能流程。
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# 导入项目模块
# 评价系统数据库管理模块

from database.db_connection import db_manager

logger = logging.getLogger(__name__)

class ReviewManager:
    """评价系统管理器
    
    核心功能:
    1. 创建用户评价记录
    2. 商家确认评价有效性
    3. 查询商家评价记录
    4. 计算和更新商家平均分
    """

    @staticmethod
    async def create_review(order_id: int, merchant_id: int, customer_user_id: int, 
                           ratings: Dict[str, int], text_review: Optional[str] = None) -> Optional[int]:
        """
        创建一条新的评价记录
        
        Args:
            order_id: 订单ID
            merchant_id: 商家ID (永久ID)
            customer_user_id: 用户ID (Telegram用户ID)
            ratings: 评分字典，包含5个维度评分
                    {'appearance': 8, 'figure': 9, 'service': 7, 'attitude': 10, 'environment': 8}
            text_review: 文字评价 (可选)
            
        Returns:
            int: 新创建的评价记录ID，失败返回None
        """
        # 验证评分数据
        required_ratings = ['appearance', 'figure', 'service', 'attitude', 'environment']
        for rating_key in required_ratings:
            if rating_key not in ratings:
                logger.error(f"评分数据缺少必要维度: {rating_key}")
                return None
            if not isinstance(ratings[rating_key], int) or not (1 <= ratings[rating_key] <= 10):
                logger.error(f"评分维度 {rating_key} 数据无效: {ratings[rating_key]}，必须是1-10的整数")
                return None
        
        query = """
            INSERT INTO reviews (
                order_id, merchant_id, customer_user_id, 
                rating_appearance, rating_figure, rating_service, rating_attitude, rating_environment, 
                text_review_by_user, status, is_confirmed_by_merchant
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            order_id, merchant_id, customer_user_id,
            ratings['appearance'], ratings['figure'], ratings['service'],
            ratings['attitude'], ratings['environment'], text_review,
            'pending_merchant_review', False
        )
        try:
            return await db_manager.get_last_insert_id(query, params)
        except Exception as e:
            logger.error(f"创建评价时出错: {e}")
            return None

    @staticmethod
    async def confirm_review(review_id: int) -> bool:
        """
        商家确认评价有效性
        
        核心业务逻辑：
        1. 更新评价确认状态
        2. 触发完整的用户激励流程（积分、经验、等级、勋章）
        
        Args:
            review_id: 评价记录ID
            
        Returns:
            bool: 确认成功返回True，失败返回False
        """
        try:
            # 获取评价详情
            review_detail = await ReviewManager.get_review_detail(review_id)
            if not review_detail:
                logger.error(f"评价不存在: review_id={review_id}")
                return False
            
            if review_detail.get('is_confirmed_by_merchant'):
                logger.warning(f"评价已被确认: review_id={review_id}")
                return True  # 已确认的评价返回成功
            
            # 更新确认状态
            query = """
                UPDATE reviews 
                SET is_confirmed_by_merchant = TRUE, status = 'completed' 
                WHERE id = ? AND is_confirmed_by_merchant = FALSE
            """
            result = await db_manager.execute_query(query, (review_id,))
            
            if not result:
                logger.error(f"评价确认更新失败: review_id={review_id}")
                return False
            
            logger.info(f"评价 {review_id} 已被商家确认为有效")
            
            # 触发激励系统处理
            try:
                from services.incentive_processor import incentive_processor
                
                incentive_result = await incentive_processor.process_confirmed_review_rewards(
                    user_id=review_detail['customer_user_id'],
                    review_id=review_id,
                    order_id=review_detail['order_id']
                )
                
                if incentive_result['success']:
                    logger.info(f"激励处理成功: user_id={review_detail['customer_user_id']}, "
                              f"积分+{incentive_result['points_earned']}, "
                              f"经验+{incentive_result['xp_earned']}, "
                              f"等级升级={incentive_result['level_upgraded']}, "
                              f"新勋章数量={len(incentive_result['new_badges'])}")
                else:
                    logger.error(f"激励处理失败: {incentive_result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"激励处理出错: {e}")
                # 激励处理失败不影响评价确认的成功
            
            return True
            
        except Exception as e:
            logger.error(f"确认评价 {review_id} 时出错: {e}")
            return False

    @staticmethod
    async def get_reviews_by_merchant(merchant_id: int, confirmed_only: bool = True, 
                                    limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取指定商家的评价记录
        
        Args:
            merchant_id: 商家ID (永久ID)
            confirmed_only: 是否只返回已确认的评价
            limit: 返回记录数限制
            offset: 偏移量，用于分页
            
        Returns:
            List[Dict]: 评价记录列表
        """
        where_condition = "WHERE r.merchant_id = ?"
        params = [merchant_id]
        
        if confirmed_only:
            where_condition += " AND r.is_confirmed_by_merchant = TRUE"
        
        query = f"""
            SELECT 
                r.id, r.order_id, r.merchant_id, r.customer_user_id,
                r.rating_appearance, r.rating_figure, r.rating_service, 
                r.rating_attitude, r.rating_environment,
                r.text_review_by_user, r.is_confirmed_by_merchant, r.status,
                r.created_at,
                u.username as customer_username
            FROM reviews r
            LEFT JOIN users u ON r.customer_user_id = u.user_id
            {where_condition}
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
        """
        
        params.extend([limit, offset])
        
        try:
            results = await db_manager.fetch_all(query, tuple(params))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取商家 {merchant_id} 的评价记录时出错: {e}")
            return []

    @staticmethod
    async def calculate_and_update_merchant_scores(merchant_id: int) -> bool:
        """
        计算并更新商家的平均评分
        
        Args:
            merchant_id: 商家ID (永久ID)
            
        Returns:
            bool: 更新成功返回True，失败返回False
        """
        # 计算该商家所有已确认评价的平均分
        query = """
            SELECT 
                AVG(CAST(rating_appearance AS REAL)) as avg_appearance,
                AVG(CAST(rating_figure AS REAL)) as avg_figure,
                AVG(CAST(rating_service AS REAL)) as avg_service,
                AVG(CAST(rating_attitude AS REAL)) as avg_attitude,
                AVG(CAST(rating_environment AS REAL)) as avg_environment,
                COUNT(*) as total_reviews_count
            FROM reviews 
            WHERE merchant_id = ? AND is_confirmed_by_merchant = TRUE
        """
        
        try:
            result = await db_manager.fetch_one(query, (merchant_id,))
            
            if not result or result['total_reviews_count'] == 0:
                logger.info(f"商家 {merchant_id} 暂无有效评价记录")
                return True
                
            # 更新或插入merchant_scores表
            upsert_query = """
                INSERT INTO merchant_scores (
                    merchant_id, avg_appearance, avg_figure, avg_service, 
                    avg_attitude, avg_environment, total_reviews_count, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(merchant_id) DO UPDATE SET
                    avg_appearance = excluded.avg_appearance,
                    avg_figure = excluded.avg_figure,
                    avg_service = excluded.avg_service,
                    avg_attitude = excluded.avg_attitude,
                    avg_environment = excluded.avg_environment,
                    total_reviews_count = excluded.total_reviews_count,
                    updated_at = excluded.updated_at
            """
            
            params = (
                merchant_id,
                round(result['avg_appearance'], 2) if result['avg_appearance'] else None,
                round(result['avg_figure'], 2) if result['avg_figure'] else None,
                round(result['avg_service'], 2) if result['avg_service'] else None,
                round(result['avg_attitude'], 2) if result['avg_attitude'] else None,
                round(result['avg_environment'], 2) if result['avg_environment'] else None,
                result['total_reviews_count'],
                datetime.now()
            )
            
            await db_manager.execute_query(upsert_query, params)
            logger.info(f"商家 {merchant_id} 的平均分已更新，有效评价数: {result['total_reviews_count']}")
            return True
            
        except Exception as e:
            logger.error(f"计算商家 {merchant_id} 平均分时出错: {e}")
            return False

    @staticmethod
    async def get_merchant_scores(merchant_id: int) -> Optional[Dict[str, Any]]:
        """
        获取商家的平均分数据
        
        Args:
            merchant_id: 商家ID (永久ID)
            
        Returns:
            Dict: 包含平均分的字典，失败返回None
        """
        query = "SELECT * FROM merchant_scores WHERE merchant_id = ?"
        
        try:
            result = await db_manager.fetch_one(query, (merchant_id,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取商家 {merchant_id} 的平均分时出错: {e}")
            return None

    @staticmethod
    async def get_review_by_order_id(order_id: int) -> Optional[Dict[str, Any]]:
        """
        根据订单ID获取评价记录
        
        Args:
            order_id: 订单ID
            
        Returns:
            Dict: 评价记录字典，不存在返回None
        """
        query = "SELECT * FROM reviews WHERE order_id = ?"
        
        try:
            result = await db_manager.fetch_one(query, (order_id,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取订单 {order_id} 的评价记录时出错: {e}")
            return None

    @staticmethod
    async def get_reviews_by_order_id(order_id: int) -> List[Dict[str, Any]]:
        """
        根据订单ID获取评价记录列表（兼容接口）。

        说明：当前 `reviews.order_id` 设计为唯一（一单一评），
        因此通常返回0或1条记录。此方法为兼容 Web 服务中
        `get_reviews_by_order_id` 的调用，返回列表类型。

        Args:
            order_id: 订单ID

        Returns:
            List[Dict]: 评价记录列表（可能为空或仅含一条）
        """
        try:
            # 虽为唯一，这里仍以列表形式返回，避免调用方改动
            query = "SELECT * FROM reviews WHERE order_id = ? ORDER BY created_at DESC"
            results = await db_manager.fetch_all(query, (order_id,))
            return [dict(row) for row in results] if results else []
        except Exception as e:
            logger.error(f"获取订单 {order_id} 的评价记录列表时出错: {e}")
            return []

    @staticmethod
    async def get_review_details(review_id: int) -> Optional[Dict[str, Any]]:
        """
        获取评价详情
        
        Args:
            review_id: 评价ID
            
        Returns:
            Dict: 评价详情字典，不存在返回None
        """
        query = """
            SELECT 
                r.*,
                m.name as merchant_name,
                u.username as customer_username
            FROM reviews r
            LEFT JOIN merchants m ON r.merchant_id = m.id
            LEFT JOIN users u ON r.customer_user_id = u.user_id
            WHERE r.id = ?
        """
        
        try:
            result = await db_manager.fetch_one(query, (review_id,))
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"获取评价 {review_id} 详情时出错: {e}")
            return None

    @staticmethod
    async def get_pending_reviews_for_merchant(merchant_id: int) -> List[Dict[str, Any]]:
        """
        获取指定商家的待确认评价列表
        
        Args:
            merchant_id: 商家ID (永久ID)
            
        Returns:
            List[Dict]: 待确认评价记录列表
        """
        query = """
            SELECT 
                r.*,
                o.price as order_price,
                u.username as customer_username
            FROM reviews r
            LEFT JOIN orders o ON r.order_id = o.id
            LEFT JOIN users u ON r.customer_user_id = u.user_id
            WHERE r.merchant_id = ? AND r.is_confirmed_by_merchant = FALSE
            ORDER BY r.created_at DESC
        """
        
        try:
            results = await db_manager.fetch_all(query, (merchant_id,))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取商家 {merchant_id} 的待确认评价时出错: {e}")
            return []

    # ==================== V2.0 扩展方法 - Web管理界面支持 ==================== #
    
    @staticmethod
    async def get_reviews_with_details(status: str = None, merchant_id: int = None, 
                                     is_confirmed: bool = None, date_from: str = None, 
                                     date_to: str = None, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """获取评价列表，支持多种筛选条件和分页"""
        try:
            where_conditions = []
            params = []
            
            # 构建WHERE条件
            if status:
                where_conditions.append("r.status = ?")
                params.append(status)
            
            if merchant_id:
                where_conditions.append("r.merchant_id = ?")
                params.append(merchant_id)
            
            if is_confirmed is not None:
                where_conditions.append("r.is_confirmed_by_merchant = ?")
                params.append(is_confirmed)
            
            if date_from:
                where_conditions.append("DATE(r.created_at) >= ?")
                params.append(date_from)
            
            if date_to:
                where_conditions.append("DATE(r.created_at) <= ?")
                params.append(date_to)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    r.*,
                    m.name as merchant_name,
                    u.username as customer_username
                FROM reviews r
                LEFT JOIN merchants m ON r.merchant_id = m.id
                LEFT JOIN users u ON r.customer_user_id = u.user_id
                {where_clause}
                ORDER BY r.created_at DESC
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            results = await db_manager.fetch_all(query, tuple(params))
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"获取评价列表失败: {e}")
            return []
    
    @staticmethod
    async def count_reviews(status: str = None, merchant_id: int = None, 
                          is_confirmed: bool = None, date_from: str = None, 
                          date_to: str = None) -> int:
        """统计评价总数，支持筛选条件"""
        try:
            where_conditions = []
            params = []
            
            if status:
                where_conditions.append("status = ?")
                params.append(status)
            
            if merchant_id:
                where_conditions.append("merchant_id = ?")
                params.append(merchant_id)
            
            if is_confirmed is not None:
                where_conditions.append("is_confirmed_by_merchant = ?")
                params.append(is_confirmed)
            
            if date_from:
                where_conditions.append("DATE(created_at) >= ?")
                params.append(date_from)
            
            if date_to:
                where_conditions.append("DATE(created_at) <= ?")
                params.append(date_to)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"SELECT COUNT(*) as count FROM reviews {where_clause}"
            result = await db_manager.fetch_one(query, tuple(params))
            
            return result['count'] if result else 0
            
        except Exception as e:
            logger.error(f"统计评价总数失败: {e}")
            return 0
    
    @staticmethod
    async def get_review_detail(review_id: int) -> Optional[Dict[str, Any]]:
        """获取评价详细信息，包括用户和商户信息"""
        try:
            query = """
                SELECT 
                    r.*,
                    m.name as merchant_name,
                    u.username as customer_username
                FROM reviews r
                LEFT JOIN merchants m ON r.merchant_id = m.id 
                LEFT JOIN users u ON r.customer_user_id = u.user_id
                WHERE r.id = ?
            """
            
            result = await db_manager.fetch_one(query, (review_id,))
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"获取评价 {review_id} 详情失败: {e}")
            return None
    
    @staticmethod
    async def get_average_rating() -> float:
        """获取全平台平均评分"""
        try:
            query = """
                SELECT AVG((
                    rating_appearance + rating_figure + rating_service + 
                    rating_attitude + rating_environment
                ) / 5.0) as avg_rating
                FROM reviews 
                WHERE is_confirmed_by_merchant = TRUE
                AND rating_appearance > 0
            """
            
            result = await db_manager.fetch_one(query)
            return result['avg_rating'] or 0
            
        except Exception as e:
            logger.error(f"获取平均评分失败: {e}")
            return 0

    # ==================== 便捷统计方法（供Web服务调用） ==================== #

    @staticmethod
    async def count_confirmed_reviews() -> int:
        """统计已确认评价数"""
        try:
            return await ReviewManager.count_reviews(is_confirmed=True)
        except Exception as e:
            logger.error(f"统计已确认评价数失败: {e}")
            return 0

    @staticmethod
    async def count_reviews_since(start_time: datetime) -> int:
        """统计自指定时间起的评价数"""
        try:
            return await ReviewManager.count_reviews(date_from=start_time)
        except Exception as e:
            logger.error(f"统计自时间起评价数失败: {e}")
            return 0

    @staticmethod
    async def count_reviews_in_range(start_time: datetime, end_time: datetime) -> int:
        """统计时间区间内的评价数"""
        try:
            return await ReviewManager.count_reviews(date_from=start_time, date_to=end_time)
        except Exception as e:
            logger.error(f"统计时间区间评价数失败: {e}")
            return 0

    @staticmethod
    async def get_top_rated_merchants(limit: int = 10) -> List[Dict[str, Any]]:
        """按平均评分排行的商户列表（基于merchant_scores）"""
        try:
            query = """
                SELECT m.id as merchant_id, m.name as merchant_name,
                       ms.avg_appearance, ms.avg_figure, ms.avg_service, ms.avg_attitude, ms.avg_environment,
                       (COALESCE(ms.avg_appearance,0)+COALESCE(ms.avg_figure,0)+COALESCE(ms.avg_service,0)+COALESCE(ms.avg_attitude,0)+COALESCE(ms.avg_environment,0))/5.0 as avg_rating,
                       ms.total_reviews_count
                FROM merchant_scores ms
                JOIN merchants m ON ms.merchant_id = m.id
                ORDER BY avg_rating DESC, ms.total_reviews_count DESC
                LIMIT ?
            """
            results = await db_manager.fetch_all(query, (int(limit),))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取评分最高商户失败: {e}")
            return []

    @staticmethod
    async def get_daily_review_counts(days: int = 30) -> List[Dict[str, Any]]:
        """最近N天每日评价数量（已确认）"""
        try:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=max(0, int(days) - 1)))
            query = """
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM reviews
                WHERE created_at >= ? AND is_confirmed_by_merchant = TRUE
                GROUP BY DATE(created_at)
                ORDER BY day ASC
            """
            results = await db_manager.fetch_all(query, (start_date,))
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"获取每日评价数失败: {e}")
            return []

# 创建实例
review_manager = ReviewManager()
