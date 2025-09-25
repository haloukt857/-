# -*- coding: utf-8 -*-
"""
开发工具路由（仅开发环境启用）

提供一键重置“数据库模板（templates）”为默认值的接口。
说明：重置为脚本 scripts/initialize_templates.py 中的 COMPREHENSIVE_TEMPLATES。
"""

import os
import json
import logging
from typing import Dict
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import WEB_CONFIG
from database.db_templates import save_template

logger = logging.getLogger(__name__)


async def reset_templates(request: Request):
    """重置数据库中的所有模板为默认内容（开发环境）。"""
    # 仅允许在开发模式下使用
    if os.getenv('RUN_MODE', 'dev') != 'dev':
        return JSONResponse({"success": False, "error": "仅开发模式可用"}, status_code=403)

    # 获取密码（支持JSON或表单）
    try:
        password = None
        content_type = request.headers.get('content-type', '')
        if 'application/json' in content_type:
            body = await request.json()
            password = (body or {}).get('password')
        else:
            form = await request.form()
            password = form.get('password')
    except Exception:
        password = None

    if not password or password != WEB_CONFIG.get('admin_password'):
        return JSONResponse({"success": False, "error": "管理员密码不正确"}, status_code=401)

    # 导入默认模板字典
    try:
        from scripts.initialize_templates import COMPREHENSIVE_TEMPLATES  # type: ignore
    except Exception as e:
        logger.error(f"导入默认模板失败: {e}")
        return JSONResponse({"success": False, "error": "无法加载默认模板"}, status_code=500)

    # 执行重置：逐条覆盖写入（存在则更新，不存在则创建）
    updated = 0
    for key, content in COMPREHENSIVE_TEMPLATES.items():
        try:
            ok = await save_template(key, content)
            if ok:
                updated += 1
        except Exception as e:
            logger.warning(f"重置模板失败: {key}, 错误: {e}")

    logger.info(f"开发工具: 模板重置完成，共处理 {updated} 条")
    return JSONResponse({"success": True, "updated": updated})

async def reset_database(request: Request):
    """重置整个数据库（删除文件并按 schema 重新初始化，仅开发模式）。"""
    import os
    from pathlib import Path
    from pathmanager import PathManager
    if os.getenv('RUN_MODE', 'dev') != 'dev':
        return JSONResponse({"success": False, "error": "仅开发模式可用"}, status_code=403)
    # 校验密码
    try:
        password = None
        content_type = request.headers.get('content-type', '')
        if 'application/json' in content_type:
            body = await request.json()
            password = (body or {}).get('password')
        else:
            form = await request.form()
            password = form.get('password')
    except Exception:
        password = None
    if not password or password != WEB_CONFIG.get('admin_password'):
        return JSONResponse({"success": False, "error": "管理员密码不正确"}, status_code=401)

    # 备份 + 删除 + 重新初始化
    try:
        # 先关闭现有连接，释放句柄
        try:
            from database.db_connection import db_manager
            await db_manager.close_all_connections()
        except Exception:
            pass
        db_path = Path(PathManager.get_database_path())
        backups_dir = Path('data/backups')
        backups_dir.mkdir(parents=True, exist_ok=True)
        backup_path = None
        if db_path.exists():
            from datetime import datetime
            import shutil
            ts = datetime.now().strftime('%Y%m%d%H%M%S')
            backup_path = backups_dir / f"{db_path.stem}.{ts}{db_path.suffix}"
            shutil.copy2(db_path, backup_path)
            try:
                db_path.unlink()
            except Exception:
                pass
            # 尝试删除 WAL/SHM 文件
            for suffix in ["-wal", "-shm"]:
                aux = Path(str(db_path) + suffix)
                if aux.exists():
                    try:
                        aux.unlink()
                    except Exception:
                        pass
        # 重新初始化
        from database.db_init import DatabaseInitializer
        initializer = DatabaseInitializer()
        ok = await initializer.initialize_database()
        if not ok:
            return JSONResponse({"success": False, "error": "初始化失败"}, status_code=500)
        # 可选：重置后导入基础地区种子
        try:
            body = await request.json()
        except Exception:
            body = {}
        preserve_regions = bool((body or {}).get('preserve_regions'))
        if preserve_regions:
            await _seed_regions_basic()
        # 更新 db_manager 的 db_path 并清空连接池，确保后续连接指向新文件
        try:
            from database.db_connection import db_manager
            db_manager.set_db_path(str(db_path))
            await db_manager.close_all_connections()
        except Exception:
            pass
        # 自动更新 schema_version 到当天递增版本
        try:
            await _bump_schema_version()
        except Exception as e:
            logger.warning(f"自动更新 schema_version 失败: {e}")
        # 清理应用层缓存
        try:
            from ..services.cache_service import CacheService
            for ns in [
                "dashboard", "order_mgmt", "post_mgmt", "merchant_mgmt", "review_mgmt"
            ]:
                CacheService.clear_namespace(ns)
        except Exception:
            pass
        return JSONResponse({"success": True, "backup": str(backup_path) if backup_path else None})
    except Exception as e:
        logger.error(f"重置数据库失败: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

async def _seed_regions_basic():
    """导入基础地区种子（小型数据集：北京/上海/广州 + 常见区）。"""
    try:
        from database.db_connection import db_manager
        # 插入城市
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
        # 插入区县
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
        logger.info("基础地区种子导入完成")
    except Exception as e:
        logger.error(f"导入基础地区种子失败: {e}")

async def _bump_schema_version(max_per_day: int = 500):
    """将 system_config.schema_version 更新为当天的递增版本。"""
    from datetime import datetime
    try:
        from database.db_connection import db_manager
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
        logger.info(f"schema_version 已更新为: {next_version}")
    except Exception as e:
        logger.error(f"更新 schema_version 失败: {e}")
