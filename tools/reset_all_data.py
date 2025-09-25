#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地数据库重置工具（双击/命令行均可使用）

功能：
- 备份当前数据库到 data/backups/
- 删除数据库文件及 WAL/SHM 辅助文件
- 重新初始化数据库（schema 自修复 + 关键模板）
- 可选：导入基础城市/区县种子（北京/上海/广州 + 常用区）

用法：
  python tools/reset_all_data.py --yes [--preserve-regions] [--no-backup]

注意：执行前请关闭正在运行的 Web/Bot 进程，以避免旧进程持有连接。
"""

import argparse
import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path
import sys

# 将项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pathmanager import PathManager


async def seed_regions_basic():
    """导入基础地区种子（京/沪/穗 + 常见区县）。"""
    try:
        from database.db_connection import db_manager
        cities = [
            (1, '北京', True, 1),
            (2, '上海', True, 2),
            (3, '广州', True, 3),
        ]
        for cid, name, active, order in cities:
            await db_manager.execute_query(
                "INSERT OR IGNORE INTO cities (id, name, is_active, display_order) VALUES (?, ?, ?, ?)",
                (cid, name, active, order)
            )

        districts = [
            (1, 1, '朝阳区', True, 1),
            (2, 1, '海淀区', True, 2),
            (3, 2, '浦东新区', True, 1),
            (4, 2, '黄浦区', True, 2),
            (5, 3, '天河区', True, 1),
            (6, 3, '越秀区', True, 2),
        ]
        for did, cid, name, active, order in districts:
            await db_manager.execute_query(
                "INSERT OR IGNORE INTO districts (id, city_id, name, is_active, display_order) VALUES (?, ?, ?, ?, ?)",
                (did, cid, name, active, order)
            )
        print("[OK] 基础地区种子导入完成")
    except Exception as e:
        print(f"[WARN] 导入基础地区种子失败: {e}")


async def bump_schema_version(max_per_day: int = 500):
    """将 system_config.schema_version 更新为当天的递增版本。

    格式：YYYY.MM.DD.N（N 从 1 开始，最大 max_per_day）。
    若当前为当天版本，则 N+1；否则置为当天.1。
    """
    try:
        from database.db_connection import db_manager
        from datetime import datetime
        today_prefix = datetime.now().strftime('%Y.%m.%d.')
        row = await db_manager.fetch_one("SELECT config_value FROM system_config WHERE config_key = 'schema_version'")
        current = row['config_value'] if row else None
        next_version = None
        if isinstance(current, str) and current.startswith(today_prefix):
            try:
                n = int(current.split('.')[-1])
                n = min(n + 1, max_per_day)
                next_version = f"{today_prefix}{n}"
            except Exception:
                next_version = f"{today_prefix}1"
        else:
            next_version = f"{today_prefix}1"

        # 更新或插入
        if row:
            await db_manager.execute_query(
                "UPDATE system_config SET config_value = ?, updated_at = CURRENT_TIMESTAMP WHERE config_key = 'schema_version'",
                (next_version,)
            )
        else:
            await db_manager.execute_query(
                "INSERT INTO system_config (config_key, config_value, description) VALUES ('schema_version', ?, '数据库架构版本（自动重置更新）')",
                (next_version,)
            )
        print(f"[OK] schema_version -> {next_version}")
    except Exception as e:
        print(f"[WARN] 自动更新 schema_version 失败: {e}")


async def init_database():
    from database.db_init import DatabaseInitializer
    initializer = DatabaseInitializer()
    ok = await initializer.initialize_database()
    return ok


def backup_and_remove_db(no_backup: bool = False) -> Path:
    db_path = Path(PathManager.get_database_path())
    backups_dir = ROOT / 'data' / 'backups'
    backups_dir.mkdir(parents=True, exist_ok=True)
    backup_path = None

    if db_path.exists() and not no_backup:
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        backup_path = backups_dir / f"{db_path.stem}.{ts}{db_path.suffix}"
        shutil.copy2(db_path, backup_path)
        print(f"[OK] 已备份到: {backup_path}")

    # 关闭连接池并清理（尽最大可能释放句柄）
    try:
        from database.db_connection import db_manager
        loop = asyncio.get_event_loop()
        if loop and loop.is_running():
            pass
        else:
            asyncio.run(db_manager.close_all_connections())
    except Exception:
        pass

    # 删除数据库文件与 WAL/SHM
    try:
        if db_path.exists():
            db_path.unlink()
    except Exception:
        # 如果被占用，尝试改名让新库可写
        try:
            ts = datetime.now().strftime('%Y%m%d%H%M%S')
            db_path.rename(db_path.with_suffix(f".locked.{ts}{db_path.suffix}"))
            print("[WARN] 数据库文件被占用，已重命名释放路径")
        except Exception:
            pass
    for suffix in ("-wal", "-shm"):
        aux = Path(str(db_path) + suffix)
        if aux.exists():
            try:
                aux.unlink()
            except Exception:
                pass

    return db_path


async def main():
    parser = argparse.ArgumentParser(description="本地数据库重置工具")
    parser.add_argument('--yes', action='store_true', help='无需确认')
    parser.add_argument('--no-backup', action='store_true', help='不备份直接重置')
    parser.add_argument('--preserve-regions', action='store_true', help='保留城市/区县基础数据（自动导入种子）')
    args = parser.parse_args()

    if not args.yes:
        ans = input('此操作将删除并重建数据库，是否继续? [y/N]: ').strip().lower()
        if ans != 'y':
            print('已取消')
            return

    db_path = backup_and_remove_db(no_backup=args.no_backup)
    # 初始化新数据库
    ok = await init_database()
    if not ok:
        print('❌ 初始化失败')
        return

    # 额外校验：确保关键字段存在
    try:
        from database.db_connection import db_manager
        def get_cols(table):
            rows = asyncio.get_event_loop().run_until_complete(db_manager.fetch_all(f"PRAGMA table_info({table})"))
            return [r[1] if isinstance(r, tuple) else r['name'] for r in rows]
        m_cols = await db_manager.fetch_all("PRAGMA table_info(merchants)")
        m_names = [c[1] if isinstance(c, tuple) else c['name'] for c in m_cols]
        print('[OK] 字段检查：merchants.adv_sentence 存在' if 'adv_sentence' in m_names else '[WARN] 字段检查：未发现 merchants.adv_sentence')

        # reviews / merchant_reviews 的报告字段
        rv_cols = await db_manager.fetch_all("PRAGMA table_info(reviews)")
        rv_names = [c[1] if isinstance(c, tuple) else c['name'] for c in rv_cols]
        print('[OK] 字段检查：reviews.report_message_id 存在' if 'report_message_id' in rv_names else '[WARN] 字段检查：未发现 reviews.report_message_id')

        mr_cols = await db_manager.fetch_all("PRAGMA table_info(merchant_reviews)")
        mr_names = [c[1] if isinstance(c, tuple) else c['name'] for c in mr_cols]
        print('[OK] 字段检查：merchant_reviews.report_message_id 存在' if 'report_message_id' in mr_names else '[WARN] 字段检查：未发现 merchant_reviews.report_message_id')

        # posting_channels.role 用途字段
        pc_cols = await db_manager.fetch_all("PRAGMA table_info(posting_channels)")
        pc_names = [c[1] if isinstance(c, tuple) else c['name'] for c in pc_cols]
        print('[OK] 字段检查：posting_channels.role 存在' if 'role' in pc_names else '[WARN] 字段检查：未发现 posting_channels.role')
    except Exception as e:
        print(f"[WARN] 字段检查失败: {e}")

    # 可选导入地区
    if args.preserve_regions:
        await seed_regions_basic()

    # 保持与系统目标版本一致：不再自动递增 schema_version
    # 说明：DatabaseInitializer.initialize_database() 已设置为目标版本（database/db_init.py 的 current_schema_version）。

    # 更新 db_manager 的路径并清空连接池
    try:
        from database.db_connection import db_manager
        db_manager.set_db_path(str(db_path))
        await db_manager.close_all_connections()
    except Exception:
        pass

    # 输出统计，确认干净
    try:
        from database.db_connection import db_manager
        for table in ("merchants", "orders", "binding_codes"):
            row = await db_manager.fetch_one(f"SELECT COUNT(*) AS c FROM {table}")
            print(f"[OK] {table} = {row['c'] if row else 0}")
    except Exception as e:
        print(f"[WARN] 统计失败: {e}")

    print('✅ 数据库重置完成')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n已取消')
