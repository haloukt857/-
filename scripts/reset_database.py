#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
硬重置数据库并按当前代码初始化到最新架构。

用法:
  python3 scripts/reset_database.py           # 交互式提示后执行
  python3 scripts/reset_database.py --yes     # 无提示直接执行
"""

import asyncio
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，便于导入 pathmanager 等本地模块
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pathmanager import PathManager
from database.db_connection import db_manager
from database.db_init import db_initializer


async def hard_reset_and_init():
    db_path = db_manager.db_path
    wal_path = f"{db_path}-wal"
    shm_path = f"{db_path}-shm"

    # 关闭连接池
    await db_manager.close_all_connections()

    # 删除数据库文件
    for p in (db_path, wal_path, shm_path):
        try:
            if os.path.exists(p):
                os.remove(p)
                print(f"🗑️  已删除: {p}")
        except Exception as e:
            print(f"⚠️  删除失败 {p}: {e}")

    # 重新初始化数据库
    print("🚀 执行数据库全新初始化...")
    ok = await db_initializer.initialize_database()
    if not ok:
        print("❌ 数据库初始化失败")
        sys.exit(1)
    print("✅ 数据库已重置并初始化完成")


if __name__ == "__main__":
    proceed = "--yes" in sys.argv or os.getenv("DB_RESET_CONFIRM", "").lower() in {"1", "true", "yes"}
    if not proceed:
        db_path = PathManager.get_database_path()
        ans = input(f"确认硬重置数据库吗? 将删除 {db_path} (y/N): ").strip().lower()
        proceed = ans in {"y", "yes"}
    if not proceed:
        print("已取消。")
        sys.exit(0)
    asyncio.run(hard_reset_and_init())
