# -*- coding: utf-8 -*-
"""
用户评分聚合与排行榜服务

职责：
- 从 merchant_reviews 聚合 M2U 五维平均分与次数，写入 user_scores（有效口径）
- 依据 user_scores 生成各维度排行榜缓存 user_score_leaderboards（阈值：次数>=6）
"""

import logging
from datetime import datetime
from typing import Dict, List

from database.db_connection import db_manager
from database.db_user_scores import user_scores_manager

logger = logging.getLogger(__name__)


DIM_COLUMNS = {
    'attack_quality': 'avg_attack_quality',
    'length': 'avg_length',
    'hardness': 'avg_hardness',
    'duration': 'avg_duration',
    'user_temperament': 'avg_user_temperament',
}


class UserScoresService:
    @staticmethod
    async def recalculate_all_user_scores() -> int:
        """全量聚合 M2U 有效评价到 user_scores。返回更新用户数。"""
        sql = """
            SELECT 
                user_id,
                AVG(CAST(rating_attack_quality AS REAL)) AS avg_attack_quality,
                AVG(CAST(rating_length AS REAL)) AS avg_length,
                AVG(CAST(rating_hardness AS REAL)) AS avg_hardness,
                AVG(CAST(rating_duration AS REAL)) AS avg_duration,
                AVG(CAST(rating_user_temperament AS REAL)) AS avg_user_temperament,
                COUNT(*) AS total_reviews_count
            FROM merchant_reviews
            WHERE is_confirmed_by_admin=1 AND is_active=1 AND is_deleted=0
            GROUP BY user_id
        """
        rows = await db_manager.fetch_all(sql)
        updated = 0
        now = datetime.now()
        for row in rows or []:
            d = dict(row)
            user_id = int(d['user_id'])
            avgs = {
                'avg_attack_quality': round(d['avg_attack_quality'] or 0.0, 2),
                'avg_length': round(d['avg_length'] or 0.0, 2),
                'avg_hardness': round(d['avg_hardness'] or 0.0, 2),
                'avg_duration': round(d['avg_duration'] or 0.0, 2),
                'avg_user_temperament': round(d['avg_user_temperament'] or 0.0, 2),
            }
            cnt = int(d['total_reviews_count'] or 0)
            ok = await user_scores_manager.upsert_scores(user_id, avgs, cnt, now)
            if ok:
                updated += 1
        logger.info(f"user_scores 聚合完成：更新 {updated} 个用户")
        return updated

    @staticmethod
    async def build_leaderboards(min_reviews: int = 6) -> Dict[str, int]:
        """基于 user_scores 生成五个维度的排行榜缓存。返回各维度写入数量。"""
        results = {}
        now = datetime.now()
        for dim, col in DIM_COLUMNS.items():
            # 读取候选，按分数降序、次数降序、更新时间降序
            sql = f"""
                SELECT user_id, {col} AS avg_score, total_reviews_count
                FROM user_scores
                WHERE total_reviews_count >= ?
                ORDER BY {col} DESC, total_reviews_count DESC, updated_at DESC
            """
            rows = await db_manager.fetch_all(sql, (int(min_reviews),))
            # 计算竞赛排名
            rank = 0
            last_score = None
            emitted = 0
            # 清理旧缓存（按维度）
            await db_manager.execute_query("DELETE FROM user_score_leaderboards WHERE dimension=?", (dim,))
            for idx, row in enumerate(rows or [], start=1):
                d = dict(row)
                score = float(d['avg_score'] or 0.0)
                if last_score is None or score < last_score:
                    rank = idx
                last_score = score
                # 写入缓存
                await db_manager.execute_query(
                    """
                    INSERT OR REPLACE INTO user_score_leaderboards
                    (dimension, user_id, avg_score, reviews_count, rank, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (dim, int(d['user_id']), round(score, 2), int(d['total_reviews_count'] or 0), int(rank), now)
                )
                emitted += 1
            results[dim] = emitted
            logger.info(f"leaderboard[{dim}] 生成完成：{emitted} 条")
        return results


user_scores_service = UserScoresService()

