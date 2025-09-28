# -*- coding: utf-8 -*-
"""
一键生成“完整演示数据”的脚本。

目标：
- 清理或在现有库的基础上，批量生成：用户/商户/订单、U2M+M2U评价（已管理员确认）、
  等级配置、20个勋章+触发器、按规则回填积分/经验/等级/勋章、生成用户排行榜缓存。

使用：
  python3 tools/bootstrap_demo_data.py \
      --users 500 --merchants 200 --orders 3000 \
      --low 0.25 --mid 0.5 --high 0.25 --m2u-rate 0.7 \
      [--clean]

完成后：
- 用户中心/排行榜 可见合理分布
- 激励系统/等级/勋章 已配置示例
- 随时可用现有 reset 脚本恢复干净库
"""

import asyncio
import os
import sys
import argparse
from datetime import datetime

# 根路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database.db_connection import db_manager
from database.db_incentives import incentive_manager
from services.incentive_processor import incentive_processor
from services.user_scores_service import user_scores_service

# 复用生成数据逻辑
from tools.generate_review_dataset import generate_dataset


async def clean_database():
    print("[clean] 清理核心业务表…")
    tables = [
        'merchant_reviews', 'reviews', 'orders',
        'user_scores', 'user_score_leaderboards',
        'user_badges', 'badge_triggers', 'badges',
        'user_levels',
        # 用户/商户可选清理（这里不删除users/merchants，避免破坏其他功能）
    ]
    for t in tables:
        try:
            await db_manager.execute_query(f"DELETE FROM {t}")
        except Exception as e:
            print(f"  - 跳过 {t}: {e}")
    # 归零用户激励字段
    try:
        await db_manager.execute_query("UPDATE users SET xp=0, points=0, level_name='新手', badges='[]'")
    except Exception:
        pass


async def seed_levels():
    print("[seed] 等级配置…")
    # 7个示例等级，经验阈值与升级奖励分布合理
    # 为演示环境降低阈值，使分布更均匀
    levels = [
        ("新手", 0, 0),
        ("青铜", 60, 10),
        ("白银", 120, 15),
        ("黄金", 200, 20),
        ("铂金", 320, 25),
        ("钻石", 480, 30),
        ("王者", 700, 50),
    ]
    for name, xp, pts in levels:
        try:
            await incentive_manager.add_level(name, xp, pts)
        except Exception:
            # 已存在则尝试更新
            try:
                rows = await db_manager.fetch_all("SELECT id FROM user_levels WHERE level_name=?", (name,))
                if rows:
                    await incentive_manager.update_level(rows[0]['id'], name, xp, pts)
            except Exception:
                pass


async def seed_badges_and_triggers():
    print("[seed] 勋章与触发器（20个）…")
    badges = [
        ("初出茅庐", "🌱", "XP ≥100" , [("total_xp_min", 100)]),
        ("见习达人", "🎯", "XP ≥300", [("total_xp_min", 300)]),
        ("成长先锋", "🚀", "XP ≥600", [("total_xp_min", 600)]),
        ("长度大王", "📏", "长度均分≥9 且 M2U≥6", [("m2u_avg_length_min", 9.0),("m2u_reviews_min", 6)]),
        ("硬度大王", "🧱", "硬度均分≥9 且 M2U≥6", [("m2u_avg_hardness_min", 9.0),("m2u_reviews_min", 6)]),
        ("时间掌控者", "⏱", "时间均分≥9 且 M2U≥6", [("m2u_avg_duration_min", 9.0),("m2u_reviews_min", 6)]),
        ("素质优等", "🛡", "素质均分≥9 且 M2U≥6", [("m2u_avg_attack_quality_min", 9.0),("m2u_reviews_min", 6)]),
        ("气质非凡", "✨", "气质均分≥9 且 M2U≥6", [("m2u_avg_user_temperament_min", 9.0),("m2u_reviews_min", 6)]),
        ("评价达人", "📝", "U2M确认≥10", [("u2m_confirmed_reviews_min", 10)]),
        ("评价王者", "👑", "U2M确认≥30", [("u2m_confirmed_reviews_min", 30)]),
        ("出击常客", "🥾", "订单≥10", [("order_count_min", 10)]),
        ("出击狂魔", "🔥", "订单≥50", [("order_count_min", 50)]),
        ("顶级好评", "💯", "长度均分≥9.5 且 M2U≥10", [("m2u_avg_length_min", 9.5),("m2u_reviews_min", 10)]),
        ("深藏不露", "🧠", "积分≥1000", [("total_points_min", 1000)]),
        ("吝啬王", "🪙", "积分≥1000 且订单≤0", [("total_points_min", 1000),("order_count_max", 0)]),
        ("新星崛起", "⭐", "XP ≥500", [("total_xp_min", 500)]),
        ("超新星", "🌟", "XP ≥1500", [("total_xp_min", 1500)]),
        ("百战成名", "🏵", "订单≥100", [("order_count_min", 100)]),
        ("口碑认证", "✅", "长度均分≥8.5 且 M2U≥12", [("m2u_avg_length_min", 8.5),("m2u_reviews_min", 12)]),
        ("均衡选手", "⚖️", "多维度均分≥8 且 M2U≥8", [
            ("m2u_avg_length_min", 8.0), ("m2u_avg_hardness_min", 8.0), ("m2u_avg_attack_quality_min", 8.0), ("m2u_reviews_min", 8)
        ]),
    ]

    for name, icon, desc, triggers in badges:
        try:
            bid = await incentive_manager.add_badge(name, icon, desc)
        except Exception:
            # 已存在则获取ID
            row = await db_manager.fetch_one("SELECT id FROM badges WHERE badge_name=?", (name,))
            bid = row['id'] if row else None
        if not bid:
            continue
        # 添加触发器
        for ttype, tval in triggers:
            try:
                await incentive_manager.add_trigger(bid, ttype, int(tval) if isinstance(tval, float) and tval.is_integer() else tval)
            except Exception:
                pass


async def backfill_incentives_for_all_u2m():
    print("[backfill] 回填 U2M → 积分/经验/等级/勋章 …")
    rows = await db_manager.fetch_all(
        "SELECT id as review_id, customer_user_id as user_id, order_id FROM reviews WHERE is_confirmed_by_admin=1 AND is_active=1 AND is_deleted=0 ORDER BY id"
    )
    total = len(rows or [])
    ok = 0
    for idx, r in enumerate(rows or [], 1):
        d = dict(r)
        res = await incentive_processor.process_confirmed_review_rewards(int(d['user_id']), int(d['review_id']), int(d['order_id'] or 0))
        if res.get('success'):
            ok += 1
        if idx % 500 == 0 or idx == total:
            print(f"  进度 {idx}/{total}，成功 {ok}")
    print(f"[backfill] 完成：{ok}/{total}")


async def main():
    parser = argparse.ArgumentParser(description='一键生成完整演示数据')
    parser.add_argument('--users', type=int, default=500)
    parser.add_argument('--merchants', type=int, default=200)
    parser.add_argument('--orders', type=int, default=3000)
    parser.add_argument('--low', type=float, default=0.25)
    parser.add_argument('--mid', type=float, default=0.5)
    parser.add_argument('--high', type=float, default=0.25)
    parser.add_argument('--m2u-rate', type=float, default=0.7)
    parser.add_argument('--clean', action='store_true', help='清理相关表后再生成')
    args = parser.parse_args()

    start = datetime.now()
    if args.clean:
        await clean_database()

    await seed_levels()
    await seed_badges_and_triggers()

    print("[gen] 生成订单与评价数据…")
    await generate_dataset(args.users, args.merchants, args.orders, args.low, args.mid, args.high, args.m2u_rate)

    await backfill_incentives_for_all_u2m()

    print("[scores] 聚合 user_scores 与排行榜缓存 …")
    await user_scores_service.recalculate_all_user_scores()
    await user_scores_service.build_leaderboards(min_reviews=6)

    print(f"完成，总耗时 {(datetime.now()-start).total_seconds():.2f}s")


if __name__ == '__main__':
    asyncio.run(main())
