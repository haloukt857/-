# -*- coding: utf-8 -*-
"""
批量生成模拟评价数据（U2M/M2U）脚本，用于压力与可视化验证。

特性：
- 生成用户、商户、订单
- 为每个订单生成 U2M（并管理员确认）；按比例生成 M2U（需 U2M 已确认）并管理员确认
- 评分分布支持低/中/高三段权重（可配置）
- 目标规模：默认 3,000 单（--orders 3000），可调整

用法示例：
    python3 tools/generate_review_dataset.py --users 500 --merchants 200 --orders 3000 \
        --low 0.25 --mid 0.5 --high 0.25 --m2u-rate 0.7

注意：
- 本脚本直接写库，不触发发布/激励。用于验证聚合、列表、排行榜等只读功能。
- 生成后可运行：python3 tools/run_user_scores.py  生成排行榜缓存。
"""

import asyncio
import os
import sys
import random
from datetime import datetime, timedelta
import argparse

# 追加根目录进路径，便于独立运行
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database.db_connection import db_manager
from database.db_users import user_manager
from database.db_merchants import MerchantManager
from database.db_orders import OrderManager
from database.db_reviews_u2m import u2m_reviews_manager
from database.db_merchant_reviews import merchant_reviews_manager


def tri_modal_score(low_w: float, mid_w: float, high_w: float) -> int:
    r = random.random()
    if r < low_w:
        return random.randint(1, 4)  # 低分
    elif r < low_w + mid_w:
        return random.randint(5, 7)  # 中分
    else:
        return random.randint(8, 10)  # 高分


def make_u2m_ratings(low: float, mid: float, high: float) -> dict:
    return {
        'rating_appearance': tri_modal_score(low, mid, high),
        'rating_figure': tri_modal_score(low, mid, high),
        'rating_service': tri_modal_score(low, mid, high),
        'rating_attitude': tri_modal_score(low, mid, high),
        'rating_environment': tri_modal_score(low, mid, high),
    }


def make_m2u_ratings(low: float, mid: float, high: float) -> dict:
    return {
        'rating_attack_quality': tri_modal_score(low, mid, high),
        'rating_length': tri_modal_score(low, mid, high),
        'rating_hardness': tri_modal_score(low, mid, high),
        'rating_duration': tri_modal_score(low, mid, high),
        'rating_user_temperament': tri_modal_score(low, mid, high),
    }


async def ensure_users(n_users: int) -> list[int]:
    """确保生成 n_users 个用户，返回用户ID列表。"""
    base = 100000  # 避免与真实用户冲突
    ids = []
    for i in range(n_users):
        uid = base + i
        uname = f"user_{uid}"
        await user_manager.create_or_update_user(uid, uname)
        ids.append(uid)
    return ids


async def ensure_merchants(n_merchants: int) -> list[int]:
    """确保生成 n_merchants 个商户，返回商户ID列表。"""
    ids = []
    base = 900000
    for i in range(n_merchants):
        chat_id = base + i
        mid = await MerchantManager.create_merchant({
            'telegram_chat_id': chat_id,
            'name': f"老师_{i+1}",
            'merchant_type': 'teacher',
            'status': 'approved',
            'p_price': random.choice([100, 150, 200, 250, 300]),
            'pp_price': random.choice([200, 300, 400, 500]),
        })
        if mid:
            ids.append(mid)
    return ids


async def generate_dataset(users_cnt: int, merchants_cnt: int, orders_cnt: int,
                           low: float, mid: float, high: float,
                           m2u_rate: float) -> None:
    rand = random.Random(42)
    random.seed(42)
    # 1) 准备用户与商户
    users = await ensure_users(users_cnt)
    merchants = await ensure_merchants(merchants_cnt)
    if not users or not merchants:
        print("用户或商户创建失败或为空")
        return

    # 2) 生成订单+评价
    base_time = datetime.now() - timedelta(days=60)
    created_u2m = 0
    created_m2u = 0
    for i in range(orders_cnt):
        user_id = rand.choice(users)
        merchant_id = rand.choice(merchants)
        course_type = rand.choice(['P', 'PP'])
        price = rand.choice([100, 150, 200, 250, 300, 400])
        # 创建订单
        order_id = await OrderManager.create_order({
            'customer_user_id': user_id,
            'customer_username': f'user_{user_id}',
            'merchant_id': merchant_id,
            'course_type': course_type,
            'price': price,
            'status': '已完成',
            'completion_time': base_time + timedelta(minutes=i)
        })
        if not order_id:
            continue
        # U2M 评分 + 管理员确认
        u2m = make_u2m_ratings(low, mid, high)
        text_u = ("不错" * rand.randint(0, 8)) if rand.random() < 0.5 else None
        is_anon = rand.random() < 0.3
        rid = await u2m_reviews_manager.create(order_id, merchant_id, user_id, u2m, text_u, is_anonymous=is_anon)
        if rid:
            ok = await u2m_reviews_manager.confirm_by_admin(rid, admin_id=1)
            if ok:
                created_u2m += 1
        # 按概率生成 M2U（依赖 U2M 已确认的门槛，这里总是满足）
        if rand.random() < m2u_rate:
            m2u = make_m2u_ratings(low, mid, high)
            text_m = ("表现不错" * rand.randint(0, 6)) if rand.random() < 0.4 else None
            mid_ = await merchant_reviews_manager.create(order_id, merchant_id, user_id, m2u, text_m)
            if mid_:
                ok2 = await merchant_reviews_manager.confirm_by_admin(mid_, admin_id=1)
                if ok2:
                    created_m2u += 1

    print(f"生成完成：U2M {created_u2m} 条，M2U {created_m2u} 条（订单 {orders_cnt}）")


async def main():
    parser = argparse.ArgumentParser(description='生成模拟评价数据集（U2M/M2U）')
    parser.add_argument('--users', type=int, default=500, help='生成用户数量')
    parser.add_argument('--merchants', type=int, default=200, help='生成商户数量')
    parser.add_argument('--orders', type=int, default=3000, help='生成订单/评价数量')
    parser.add_argument('--low', type=float, default=0.25, help='低分权重 0..1')
    parser.add_argument('--mid', type=float, default=0.5, help='中分权重 0..1')
    parser.add_argument('--high', type=float, default=0.25, help='高分权重 0..1')
    parser.add_argument('--m2u-rate', type=float, default=0.7, help='生成M2U的概率 0..1')
    args = parser.parse_args()

    s = args.low + args.mid + args.high
    if abs(s - 1.0) > 1e-6:
        args.low, args.mid, args.high = args.low / s, args.mid / s, args.high / s

    await generate_dataset(args.users, args.merchants, args.orders,
                           args.low, args.mid, args.high, args.m2u_rate)


if __name__ == "__main__":
    asyncio.run(main())

