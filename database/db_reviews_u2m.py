# -*- coding: utf-8 -*-
"""
U2M（用户→商户/老师）评价数据访问层

表：reviews（沿用现有表，已通过迁移新增最小管理字段）

职责（最小集）：
- create：创建一条评价（五维评分+可选文本）
- get_by_order_id：按订单获取
- list_by_merchant：按商户分页列出（默认仅返回确认+启用+未删除；不读取长文本）
- update_scores / update_text：评分或文本更新
- confirm_by_admin：管理员确认
- toggle_active / soft_delete：启用/暂停与软删
- set_report_link：保存报告频道链接

说明：
- 列表查询不返回 text_review_by_user（避免大文本I/O），详情再取。
- 门禁（商户启用且未过期）的业务过滤由上层 service 注入，这里不做跨表过滤。
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import logging

from database.db_connection import db_manager

logger = logging.getLogger(__name__)


REQUIRED_RATING_KEYS = [
    "rating_appearance",
    "rating_figure",
    "rating_service",
    "rating_attitude",
    "rating_environment",
]


def _validate_ratings(ratings: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        for k in REQUIRED_RATING_KEYS:
            if k not in ratings:
                return False, f"missing rating key: {k}"
            v = ratings[k]
            if not isinstance(v, int) or not (1 <= v <= 10):
                return False, f"invalid rating: {k}={v} (must be int 1..10)"
        return True, ""
    except Exception as e:
        return False, str(e)


class U2MReviewsManager:
    """U2M 评价管理器（reviews 表）"""

    @staticmethod
    async def create(
        order_id: int,
        merchant_id: int,
        user_id: int,
        ratings: Dict[str, int],
        text: Optional[str] = None,
        is_anonymous: bool = False,
    ) -> Optional[int]:
        ok, msg = _validate_ratings(ratings)
        if not ok:
            logger.error(f"create review invalid ratings: {msg}")
            return None

        sql = (
            "INSERT INTO reviews (order_id, merchant_id, customer_user_id, "
            "rating_appearance, rating_figure, rating_service, rating_attitude, rating_environment, "
            "text_review_by_user, is_anonymous) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            order_id,
            merchant_id,
            user_id,
            ratings["rating_appearance"],
            ratings["rating_figure"],
            ratings["rating_service"],
            ratings["rating_attitude"],
            ratings["rating_environment"],
            text,
            1 if is_anonymous else 0,
        )
        try:
            new_id = await db_manager.get_last_insert_id(sql, params)
            return new_id
        except Exception as e:
            logger.error(f"insert review failed: {e}")
            return None

    @staticmethod
    async def get_by_order_id(order_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM reviews WHERE order_id = ? LIMIT 1"
        row = await db_manager.fetch_one(sql, (order_id,))
        return dict(row) if row else None

    @staticmethod
    async def list_by_merchant(
        merchant_id: int,
        limit: int = 20,
        offset: int = 0,
        admin_mode: bool = False,
    ) -> List[Dict[str, Any]]:
        """分页列出商户评价（不返回长文本）。"""
        base_cols = (
            "id, order_id, merchant_id, customer_user_id, "
            "rating_appearance, rating_figure, rating_service, rating_attitude, rating_environment, "
            "is_confirmed_by_admin, is_active, is_deleted, report_post_url, created_at"
        )
        if admin_mode:
            sql = (
                f"SELECT {base_cols} FROM reviews "
                "WHERE merchant_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params = (merchant_id, int(limit), int(offset))
        else:
            sql = (
                f"SELECT {base_cols} FROM reviews "
                "WHERE merchant_id = ? AND is_confirmed_by_admin = 1 AND is_active = 1 AND is_deleted = 0 "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params = (merchant_id, int(limit), int(offset))

        rows = await db_manager.fetch_all(sql, params)
        return [dict(r) for r in rows] if rows else []

    @staticmethod
    async def update_scores(review_id: int, ratings: Dict[str, int]) -> bool:
        ok, msg = _validate_ratings(ratings)
        if not ok:
            logger.error(f"update_scores invalid ratings: {msg}")
            return False
        sql = (
            "UPDATE reviews SET "
            "rating_appearance=?, rating_figure=?, rating_service=?, rating_attitude=?, rating_environment=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?"
        )
        params = (
            ratings["rating_appearance"],
            ratings["rating_figure"],
            ratings["rating_service"],
            ratings["rating_attitude"],
            ratings["rating_environment"],
            review_id,
        )
        try:
            rc = await db_manager.execute_query(sql, params)
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"update_scores failed: {e}")
            return False

    @staticmethod
    async def update_text(review_id: int, text: Optional[str]) -> bool:
        sql = "UPDATE reviews SET text_review_by_user=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, (text, review_id))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"update_text failed: {e}")
            return False

    @staticmethod
    async def confirm_by_admin(review_id: int, admin_id: int) -> bool:
        sql = (
            "UPDATE reviews SET is_confirmed_by_admin=1, confirmed_by_admin_id=?, "
            "confirmed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND is_deleted=0"
        )
        try:
            rc = await db_manager.execute_query(sql, (admin_id, review_id))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"confirm_by_admin failed: {e}")
            return False

    @staticmethod
    async def toggle_active(review_id: int, is_active: bool) -> bool:
        sql = "UPDATE reviews SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, (1 if is_active else 0, review_id))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"toggle_active failed: {e}")
            return False

    @staticmethod
    async def soft_delete(review_id: int) -> bool:
        sql = "UPDATE reviews SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, (review_id,))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"soft_delete failed: {e}")
            return False

    @staticmethod
    async def set_anonymous_flag(review_id: int, is_anonymous: bool) -> bool:
        sql = "UPDATE reviews SET is_anonymous=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, (1 if is_anonymous else 0, review_id))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"set_anonymous_flag failed: {e}")
            return False

    @staticmethod
    async def set_report_link(review_id: int, url: str, published_at: Optional[datetime] = None) -> bool:
        if published_at is None:
            sql = "UPDATE reviews SET report_post_url=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
            params = (url, review_id)
        else:
            sql = "UPDATE reviews SET report_post_url=?, published_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
            params = (url, published_at, review_id)
        try:
            rc = await db_manager.execute_query(sql, params)
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"set_report_link failed: {e}")
            return False

    @staticmethod
    async def set_report_meta(review_id: int, message_id: int, url: Optional[str] = None, published_at: Optional[datetime] = None) -> bool:
        fields = []
        params = []
        if url is not None:
            fields.append("report_post_url=?")
            params.append(url)
        if published_at is not None:
            fields.append("published_at=?")
            params.append(published_at)
        fields.append("report_message_id=?")
        params.append(int(message_id))
        fields.append("updated_at=CURRENT_TIMESTAMP")
        params.append(review_id)
        sql = f"UPDATE reviews SET {', '.join(fields)} WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, tuple(params))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"set_report_meta failed: {e}")
            return False


# 实例（按项目习惯导出实例供导入使用）
u2m_reviews_manager = U2MReviewsManager()
