#!/usr/bin/env python3
"""
强制重建数据库（带备份）

用法示例：
  python tools/reset_database.py --yes             # 备份后重建并初始化
  python tools/reset_database.py --yes --no-backup  # 不备份，直接重建
"""

import argparse
import asyncio
import shutil
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pathmanager import PathManager


async def init_db() -> bool:
    from database.db_init import init_database

    ok = await init_database()
    return ok


def backup_db(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = backup_dir / f"{db_path.stem}.{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def main():
    parser = argparse.ArgumentParser(description="强制重建数据库（带可选备份）")
    parser.add_argument("--yes", action="store_true", help="无需交互确认，直接执行")
    parser.add_argument("--no-backup", action="store_true", help="跳过备份当前数据库")
    parser.add_argument(
        "--backup-dir",
        default=str(Path("data/backups")),
        help="备份目录（默认 data/backups）",
    )
    args = parser.parse_args()

    db_path = Path(PathManager.get_database_path())
    print(f"数据库路径: {db_path}")

    if not args.yes:
        ans = input("此操作将删除并重建数据库，是否继续? [y/N]: ").strip().lower()
        if ans != "y":
            print("已取消")
            return 0

    # 备份
    if db_path.exists() and not args.no_backup:
        backup_path = backup_db(db_path, Path(args.backup_dir))
        print(f"已备份到: {backup_path}")

    # 删除数据库文件
    if db_path.exists():
        db_path.unlink()
        print("已删除旧数据库文件")

    # 重新初始化
    ok = asyncio.run(init_db())
    if not ok:
        print("❌ 初始化失败", file=sys.stderr)
        return 1

    print("✅ 数据库重建并初始化完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
