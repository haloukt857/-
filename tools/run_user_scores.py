# -*- coding: utf-8 -*-
"""
一次性聚合用户评分并生成排行榜缓存的便捷脚本。

用法：
    python tools/run_user_scores.py

行为：
    1) 从 merchant_reviews 聚合 M2U 有效评分到 user_scores
    2) 基于 user_scores 生成 user_score_leaderboards（阈值：次数>=6）
    3) 打印各维度的 Top5 概览与计数
"""

import asyncio
import os
import sys
from datetime import datetime
import argparse

# 将项目根目录加入 PYTHONPATH，便于脚本独立运行
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.user_scores_service import user_scores_service
from database.db_connection import db_manager


async def main():
    parser = argparse.ArgumentParser(description='聚合用户评分并生成排行榜缓存')
    parser.add_argument('--min-reviews', type=int, default=6, help='入榜最小有效评价次数（默认6）')
    args = parser.parse_args()
    start = datetime.now()
    print("[1/3] 聚合 user_scores …")
    updated = await user_scores_service.recalculate_all_user_scores()
    print(f"    ✓ 更新 {updated} 个用户")

    print("[2/3] 生成排行榜缓存 user_score_leaderboards …")
    res = await user_scores_service.build_leaderboards(min_reviews=int(args.min_reviews))
    for dim, cnt in res.items():
        print(f"    ✓ {dim}: {cnt} 条")

    print("[3/3] 概览 …")
    row = await db_manager.fetch_one("SELECT COUNT(1) AS c FROM user_scores")
    total_users = int(row['c'] if row else 0)
    print(f"    user_scores 总数: {total_users}")
    rows = await db_manager.fetch_all(
        "SELECT dimension, COUNT(1) AS c FROM user_score_leaderboards GROUP BY dimension ORDER BY dimension"
    )
    for r in rows or []:
        print(f"    leaderboard[{r['dimension']}]: {r['c']} 条")

    print("\n    Top5 预览：")
    dims = ['attack_quality', 'length', 'hardness', 'duration', 'user_temperament']
    for dim in dims:
        print(f"\n  - {dim}：")
        top = await db_manager.fetch_all(
            """
            SELECT user_id, avg_score, reviews_count, rank
            FROM user_score_leaderboards
            WHERE dimension=?
            ORDER BY rank
            LIMIT 5
            """,
            (dim,)
        )
        if not top:
            print("    (无数据)")
            continue
        for t in top:
            print(f"    #{t['rank']}: user {t['user_id']}  {float(t['avg_score']):.2f} 分｜被{int(t['reviews_count'])}位老师/商家评价")

    print(f"\n完成，耗时 {(datetime.now()-start).total_seconds():.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
