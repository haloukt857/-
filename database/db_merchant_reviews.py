# -*- coding: utf-8 -*-
"""
M2U（商户/老师→用户）评价数据访问层

表：merchant_reviews（新增表）

职责（最小集）：
- create / get_by_order_id
- list_by_merchant / list_by_user（不读取长文本）
- update_scores / update_text
- confirm_by_admin / toggle_active / soft_delete
- set_report_link
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from database.db_connection import db_manager

logger = logging.getLogger(__name__)


REQUIRED_RATING_KEYS_M2U = [
    "rating_attack_quality",
    "rating_length",
    "rating_hardness",
    "rating_duration",
    "rating_user_temperament",
]


def _validate_ratings_m2u(ratings: Dict[str, Any]) -> bool:
    try:
        for k in REQUIRED_RATING_KEYS_M2U:
            v = ratings.get(k)
            if not isinstance(v, int) or not (1 <= v <= 10):
                return False
        return True
    except Exception:
        return False


class MerchantReviewsManager:
    @staticmethod
    async def create(
        order_id: int,
        merchant_id: int,
        user_id: int,
        ratings: Dict[str, int],
        text: Optional[str] = None,
    ) -> Optional[int]:
        if not _validate_ratings_m2u(ratings):
            logger.error("create m2u invalid ratings")
            return None
        sql = (
            "INSERT INTO merchant_reviews (order_id, merchant_id, user_id, "
            "rating_attack_quality, rating_length, rating_hardness, rating_duration, rating_user_temperament, "
            "text_review_by_merchant) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            order_id,
            merchant_id,
            user_id,
            ratings["rating_attack_quality"],
            ratings["rating_length"],
            ratings["rating_hardness"],
            ratings["rating_duration"],
            ratings["rating_user_temperament"],
            text,
        )
        try:
            new_id = await db_manager.get_last_insert_id(sql, params)
            return new_id
        except Exception as e:
            logger.error(f"insert merchant_review failed: {e}")
            return None

    @staticmethod
    async def get_by_order_id(order_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM merchant_reviews WHERE order_id=? LIMIT 1"
        row = await db_manager.fetch_one(sql, (order_id,))
        return dict(row) if row else None

    @staticmethod
    async def list_by_merchant(
        merchant_id: int,
        limit: int = 20,
        offset: int = 0,
        admin_mode: bool = False,
    ) -> List[Dict[str, Any]]:
        cols = (
            "id, order_id, merchant_id, user_id, "
            "rating_attack_quality, rating_length, rating_hardness, rating_duration, rating_user_temperament, "
            "is_confirmed_by_admin, is_active, is_deleted, report_post_url, created_at"
        )
        if admin_mode:
            sql = (
                f"SELECT {cols} FROM merchant_reviews WHERE merchant_id=? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params = (merchant_id, int(limit), int(offset))
        else:
            sql = (
                f"SELECT {cols} FROM merchant_reviews WHERE merchant_id=? "
                "AND is_confirmed_by_admin=1 AND is_active=1 AND is_deleted=0 "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params = (merchant_id, int(limit), int(offset))
        rows = await db_manager.fetch_all(sql, params)
        return [dict(r) for r in rows] if rows else []

    @staticmethod
    async def list_by_user(
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        admin_mode: bool = False,
    ) -> List[Dict[str, Any]]:
        cols = (
            "id, order_id, merchant_id, user_id, "
            "rating_attack_quality, rating_length, rating_hardness, rating_duration, rating_user_temperament, "
            "is_confirmed_by_admin, is_active, is_deleted, report_post_url, created_at"
        )
        if admin_mode:
            sql = (
                f"SELECT {cols} FROM merchant_reviews WHERE user_id=? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params = (user_id, int(limit), int(offset))
        else:
            sql = (
                f"SELECT {cols} FROM merchant_reviews WHERE user_id=? "
                "AND is_confirmed_by_admin=1 AND is_active=1 AND is_deleted=0 "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params = (user_id, int(limit), int(offset))
        rows = await db_manager.fetch_all(sql, params)
        return [dict(r) for r in rows] if rows else []

    @staticmethod
    async def update_scores(review_id: int, ratings: Dict[str, int]) -> bool:
        if not _validate_ratings_m2u(ratings):
            logger.error("update_scores m2u invalid ratings")
            return False
        sql = (
            "UPDATE merchant_reviews SET "
            "rating_attack_quality=?, rating_length=?, rating_hardness=?, rating_duration=?, rating_user_temperament=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?"
        )
        params = (
            ratings["rating_attack_quality"],
            ratings["rating_length"],
            ratings["rating_hardness"],
            ratings["rating_duration"],
            ratings["rating_user_temperament"],
            review_id,
        )
        try:
            rc = await db_manager.execute_query(sql, params)
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"update_scores m2u failed: {e}")
            return False

    @staticmethod
    async def update_text(review_id: int, text: Optional[str]) -> bool:
        sql = "UPDATE merchant_reviews SET text_review_by_merchant=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, (text, review_id))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"update_text m2u failed: {e}")
            return False

    @staticmethod
    async def confirm_by_admin(review_id: int, admin_id: int) -> bool:
        sql = (
            "UPDATE merchant_reviews SET is_confirmed_by_admin=1, confirmed_by_admin_id=?, "
            "confirmed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND is_deleted=0"
        )
        try:
            rc = await db_manager.execute_query(sql, (admin_id, review_id))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"confirm_by_admin m2u failed: {e}")
            return False

    @staticmethod
    async def toggle_active(review_id: int, is_active: bool) -> bool:
        sql = "UPDATE merchant_reviews SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, (1 if is_active else 0, review_id))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"toggle_active m2u failed: {e}")
            return False

    @staticmethod
    async def soft_delete(review_id: int) -> bool:
        sql = "UPDATE merchant_reviews SET is_deleted=1, updated_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, (review_id,))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"soft_delete m2u failed: {e}")
            return False

    # 注意：匿名标记以同订单 U2M 的 reviews.is_anonymous 为唯一真源，此处不提供 M2U 匿名设置接口

    @staticmethod
    async def set_report_link(review_id: int, url: str, published_at: Optional[datetime] = None) -> bool:
        if published_at is None:
            sql = "UPDATE merchant_reviews SET report_post_url=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
            params = (url, review_id)
        else:
            sql = "UPDATE merchant_reviews SET report_post_url=?, published_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?"
            params = (url, published_at, review_id)
        try:
            rc = await db_manager.execute_query(sql, params)
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"set_report_link m2u failed: {e}")
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
        sql = f"UPDATE merchant_reviews SET {', '.join(fields)} WHERE id=?"
        try:
            rc = await db_manager.execute_query(sql, tuple(params))
            return bool(rc and rc >= 0)
        except Exception as e:
            logger.error(f"set_report_meta m2u failed: {e}")
            return False


merchant_reviews_manager = MerchantReviewsManager()
