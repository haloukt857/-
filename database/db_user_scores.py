# -*- coding: utf-8 -*-
"""
用户评分聚合（m2u 方向）数据访问层

表：user_scores（新增表）

职责（最小集）：
- upsert_scores：写入/更新用户五维平均分与样本数
- get_by_user_id：按用户读取聚合
"""

from typing import Any, Dict, Optional
from datetime import datetime
import logging

from database.db_connection import db_manager

logger = logging.getLogger(__name__)


class UserScoresManager:
    @staticmethod
    async def upsert_scores(
        user_id: int,
        averages: Dict[str, float],
        total_count: int,
        updated_at: Optional[datetime] = None,
    ) -> bool:
        updated_at = updated_at or datetime.now()
        sql = (
            "INSERT INTO user_scores (user_id, avg_attack_quality, avg_length, avg_hardness, avg_duration, avg_user_temperament, total_reviews_count, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "avg_attack_quality=excluded.avg_attack_quality, "
            "avg_length=excluded.avg_length, "
            "avg_hardness=excluded.avg_hardness, "
            "avg_duration=excluded.avg_duration, "
            "avg_user_temperament=excluded.avg_user_temperament, "
            "total_reviews_count=excluded.total_reviews_count, "
            "updated_at=excluded.updated_at"
        )
        params = (
            user_id,
            float(averages.get("avg_attack_quality") or 0.0),
            float(averages.get("avg_length") or 0.0),
            float(averages.get("avg_hardness") or 0.0),
            float(averages.get("avg_duration") or 0.0),
            float(averages.get("avg_user_temperament") or 0.0),
            int(total_count or 0),
            updated_at,
        )
        try:
            rc = await db_manager.execute_query(sql, params)
            return bool(rc is not None)
        except Exception as e:
            logger.error(f"upsert user_scores failed: {e}")
            return False

    @staticmethod
    async def get_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM user_scores WHERE user_id=?"
        row = await db_manager.fetch_one(sql, (user_id,))
        return dict(row) if row else None


user_scores_manager = UserScoresManager()

