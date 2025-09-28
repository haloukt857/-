# -*- coding: utf-8 -*-
"""
历史数据回填激励脚本

用途：当批量导入/生成了大量已确认的 U2M 评价，但没有在“确认当时”触发激励时，
可使用本脚本一次性按当前 points_config 规则回填积分/经验/等级/勋章。

特征：
- 默认按所有有效 U2M（is_confirmed_by_admin=1 AND is_active=1 AND is_deleted=0）回填
- 可选 --reset，将所有用户的 xp/points 置零、level_name 归“新手”、badges 清空后再回填（谨慎）
- 可选 --user-min/--user-max 仅回填特定用户ID范围（方便分批）

示例：
    python3 tools/backfill_incentives.py --reset
    python3 tools/backfill_incentives.py --user-min 100000 --user-max 100999
"""

import asyncio
import os
import sys
import argparse
from datetime import datetime

# 将项目根目录加入路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database.db_connection import db_manager
from database.db_users import user_manager
from services.incentive_processor import incentive_processor


async def reset_users_scope(user_min: int | None, user_max: int | None):
    """将范围内用户的 xp/points/level_name/badges 归零（谨慎）。"""
    print("[reset] 重置用户激励字段…")
    if user_min is None and user_max is None:
        sql = "UPDATE users SET xp=0, points=0, level_name='新手', badges='[]'"
        await db_manager.execute_query(sql)
        return
    # 按范围重置
    where = []
    params = []
    if user_min is not None:
        where.append("user_id >= ?")
        params.append(int(user_min))
    if user_max is not None:
        where.append("user_id <= ?")
        params.append(int(user_max))
    sql = f"UPDATE users SET xp=0, points=0, level_name='新手', badges='[]' WHERE {' AND '.join(where)}"
    await db_manager.execute_query(sql, tuple(params))


async def backfill_u2m(user_min: int | None, user_max: int | None):
    print("[run] 回填 U2M 确认评价 → 激励")
    # 读取符合口径的 U2M
    where = "WHERE is_confirmed_by_admin=1 AND is_active=1 AND is_deleted=0"
    join_where = ""
    params = []
    if user_min is not None:
        join_where += " AND r.customer_user_id >= ?"
        params.append(int(user_min))
    if user_max is not None:
        join_where += " AND r.customer_user_id <= ?"
        params.append(int(user_max))

    sql = f"""
        SELECT r.id as review_id, r.customer_user_id as user_id, r.order_id
        FROM reviews r
        {where} {('AND' + join_where[1:]) if join_where else ''}
        ORDER BY r.id ASC
    """
    rows = await db_manager.fetch_all(sql, tuple(params) if params else None)
    total = len(rows or [])
    ok = 0
    for idx, row in enumerate(rows or [], 1):
        d = dict(row)
        res = await incentive_processor.process_confirmed_review_rewards(
            user_id=int(d['user_id']), review_id=int(d['review_id']), order_id=int(d['order_id'] or 0)
        )
        if res.get('success'):
            ok += 1
        if idx % 500 == 0 or idx == total:
            print(f"  进度 {idx}/{total}，成功 {ok}")
    print(f"完成：处理 {total} 条 U2M，成功 {ok}")


async def main():
    parser = argparse.ArgumentParser(description='回填历史 U2M 确认评价的激励（积分/经验/等级/勋章）')
    parser.add_argument('--reset', action='store_true', help='回填前重置所有用户 xp/points/level/badges（谨慎）')
    parser.add_argument('--user-min', type=int, default=None, help='仅处理 >= 此用户ID 的记录')
    parser.add_argument('--user-max', type=int, default=None, help='仅处理 <= 此用户ID 的记录')
    args = parser.parse_args()

    start = datetime.now()
    if args.reset:
        await reset_users_scope(args.user_min, args.user_max)
    await backfill_u2m(args.user_min, args.user_max)
    print(f"总耗时 {(datetime.now()-start).total_seconds():.2f}s")


if __name__ == '__main__':
    asyncio.run(main())

