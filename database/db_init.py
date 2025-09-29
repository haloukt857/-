"""
数据库初始化模块
负责创建数据库表结构、执行迁移和初始化系统配置
"""

import os
import logging
import glob
import re
from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime, timedelta

# 导入数据库连接管理器
from .db_connection import db_manager
from .schema_sync import schema_sync

# 导入路径管理器
from pathmanager import PathManager

# 配置日志
logger = logging.getLogger(__name__)

class DatabaseInitializer:
    """数据库初始化器类"""
    
    def __init__(self):
        """初始化数据库初始化器"""
        self.current_schema_version = "2025.09.28.1"
        self.migrations_dir = PathManager.get_database_migration_path()
        self.migration_history = []
    
    async def initialize_database(self) -> bool:
        """
        智能数据库初始化 - 支持全新创建和增量迁移
        
        Returns:
            初始化是否成功
        """
        try:
            logger.info("开始数据库初始化...")
            
            # 检查数据库是否存在以及当前版本
            current_version = await self.get_schema_version()
            is_fresh_install = current_version is None
            
            if is_fresh_install:
                logger.info("检测到新数据库，执行完整初始化...")
                success = await self._fresh_install()
            else:
                logger.info(f"检测到现有数据库，版本: {current_version}")
                if current_version != self.current_schema_version:
                    logger.info(f"需要迁移到版本: {self.current_schema_version}")
                    success = await self._migrate_database(current_version, self.current_schema_version)
                else:
                    logger.info("数据库版本已是最新，无需迁移")
                    success = await self._verify_tables()
                    if not success:
                        logger.warning("检测到表缺失或结构不完整，尝试执行Schema自修复...")
                        # 首选：重新执行schema.sql（开发阶段的稳妥自修复）
                        try:
                            await self._auto_generate_migration(current_version, self.current_schema_version)
                        except Exception as e:
                            logger.warning(f"自动迁移执行异常: {e}")
                        # 其次：执行结构同步（字段/索引等）
                        try:
                            _ = await schema_sync.synchronize_schema()
                        except Exception as e:
                            logger.warning(f"Schema同步异常: {e}")
                        # 补齐已知缺失模块（自动回复/关键词）
                        try:
                            await self._ensure_auto_reply_and_keywords_tables()
                        except Exception as e:
                            logger.warning(f"补齐自动回复/关键词表异常: {e}")
                        # 再次验证
                        success = await self._verify_tables()
            
            if success:
                # 确保关键模板存在 + 补齐所有关键键
                await self._ensure_critical_templates()
                await self._verify_critical_templates()
                logger.info(f"数据库就绪，当前版本: {self.current_schema_version}")
                return True
            else:
                logger.error("数据库初始化失败")
                return False
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            return False
    
    async def _verify_tables(self) -> bool:
        """
        验证所有必需的表是否存在
        
        Returns:
            所有表是否都存在
        """
        required_tables = [
            'merchants', 'orders', 'binding_codes', 'button_configs',
            'activity_logs', 'fsm_states', 'system_config',
            'auto_reply_triggers', 'auto_reply_messages', 'auto_reply_daily_stats',
            'cities', 'districts', 'keywords', 'merchant_keywords',
            'posting_time_slots', 'posting_channels'
        ]
        
        try:
            for table in required_tables:
                result = await db_manager.fetch_one(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                
                if not result:
                    logger.error(f"表 {table} 不存在")
                    return False
                    
                logger.debug(f"表 {table} 验证成功")
            
            logger.info("所有数据库表验证成功")
            return True
            
        except Exception as e:
            logger.error(f"表验证失败: {e}")
            return False
    
    async def _execute_sql_script(self, sql_script: str):
        """执行SQL脚本 - 使用SQLite原生executescript方法"""
        try:
            # 清理SQL脚本：只移除注释，保持结构完整
            clean_lines = []
            for line in sql_script.split('\n'):
                # 移除行内注释但保持行结构
                if '--' in line:
                    line = line[:line.index('--')]
                line = line.rstrip()
                if line:  # 保留空行以维持语句结构
                    clean_lines.append(line)
            
            clean_sql = '\n'.join(clean_lines)
            
            # 使用SQLite的executescript方法执行多语句脚本
            async with db_manager.get_connection() as conn:
                await conn.executescript(clean_sql)
                await conn.commit()
            
            logger.info("✅ SQL脚本执行完成")
            
        except Exception as e:
            logger.error(f"SQL脚本执行失败: {e}")
            raise

    async def _ensure_auto_reply_and_keywords_tables(self):
        """显式补齐自动回复与关键词相关表（容错修复）。"""
        ddl = """
        CREATE TABLE IF NOT EXISTS auto_reply_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            trigger_text TEXT NOT NULL,
            match_type TEXT NOT NULL CHECK (match_type IN ('exact','contains')),
            is_active BOOLEAN DEFAULT TRUE,
            priority_order INTEGER DEFAULT 0,
            trigger_count INTEGER DEFAULT 0,
            last_triggered_at TIMESTAMP,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trigger_text, match_type)
        );
        CREATE TABLE IF NOT EXISTS auto_reply_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_id INTEGER NOT NULL,
            message_content TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            display_order INTEGER DEFAULT 0,
            send_count INTEGER DEFAULT 0,
            last_sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trigger_id) REFERENCES auto_reply_triggers(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS auto_reply_daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_id INTEGER NOT NULL,
            stat_date DATE NOT NULL,
            trigger_count INTEGER DEFAULT 0,
            unique_users_count INTEGER DEFAULT 0,
            total_messages_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trigger_id) REFERENCES auto_reply_triggers(id) ON DELETE CASCADE,
            UNIQUE(trigger_id, stat_date)
        );
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS merchant_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id INTEGER NOT NULL,
            keyword_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(merchant_id, keyword_id),
            FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE,
            FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_auto_triggers_active ON auto_reply_triggers(is_active);
        CREATE INDEX IF NOT EXISTS idx_auto_triggers_text ON auto_reply_triggers(trigger_text);
        CREATE INDEX IF NOT EXISTS idx_auto_msgs_trigger ON auto_reply_messages(trigger_id);
        CREATE INDEX IF NOT EXISTS idx_auto_stats_date ON auto_reply_daily_stats(stat_date);
        -- 固定发送时间槽位配置
        CREATE TABLE IF NOT EXISTS posting_time_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time_str TEXT NOT NULL,              -- 格式 HH:MM
            is_active BOOLEAN DEFAULT 1,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        -- 发布频道配置（支持多条，置顶一条为当前使用）
        CREATE TABLE IF NOT EXISTS posting_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT,
            channel_chat_id TEXT,      -- 如 -100xxxx 或 @username
            channel_link TEXT,         -- https://t.me/xxx
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        await self._execute_sql_script(ddl)

        # adv_sentence 字段由 schema.sql（全新安装）或 migrations 统一管理，不在此处重复兜底

    async def _log_initialization(self):
        """记录初始化日志"""
        try:
            await db_manager.execute_query(
                """INSERT INTO activity_logs (user_id, action_type, details, timestamp) 
                   VALUES (?, ?, ?, ?)""",
                (
                    0,  # 系统用户ID
                    'system_init',
                    json.dumps({
                        'action': 'database_initialized',
                        'schema_version': self.current_schema_version,
                        'timestamp': datetime.now().isoformat()
                    }, ensure_ascii=False),
                    datetime.now()
                )
            )
            logger.info("数据库初始化日志记录完成")
        except Exception as e:
            logger.warning(f"记录初始化日志失败: {e}")
    
    async def get_schema_version(self) -> Optional[str]:
        """
        获取当前数据库架构版本
        
        Returns:
            架构版本字符串
        """
        try:
            result = await db_manager.fetch_one(
                "SELECT config_value FROM system_config WHERE config_key = ?",
                ('schema_version',)
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"获取架构版本失败: {e}")
            return None
    
    async def update_schema_version(self, version: str) -> bool:
        """
        更新数据库架构版本
        
        Args:
            version: 新的版本号
            
        Returns:
            更新是否成功
        """
        try:
            await db_manager.execute_query(
                """INSERT OR REPLACE INTO system_config (config_key, config_value, description) 
                   VALUES (?, ?, ?)""",
                ('schema_version', version, '数据库架构版本')
            )
            logger.info(f"架构版本更新为: {version}")
            return True
        except Exception as e:
            logger.error(f"更新架构版本失败: {e}")
            return False
    
    async def run_migration(self, migration_name: str, migration_sql: str) -> bool:
        """
        执行数据库迁移
        
        Args:
            migration_name: 迁移名称
            migration_sql: 迁移SQL语句
            
        Returns:
            迁移是否成功
        """
        try:
            logger.info(f"开始执行迁移: {migration_name}")
            
            # 检查迁移是否已经执行过
            if await self._is_migration_applied(migration_name):
                logger.info(f"迁移 {migration_name} 已经执行过，跳过")
                return True
            
            # 根据内容选择执行策略：包含事务/触发器的迁移使用 executescript，避免分号拆分导致的语法不完整
            lower_sql = migration_sql.lower()
            contains_complex = any(k in lower_sql for k in [
                'create trigger', 'begin transaction', 'commit', 'pragma foreign_keys'
            ])

            success_count = 0
            error_count = 0

            if contains_complex:
                try:
                    await self._execute_sql_script(migration_sql)
                    success_count = 1
                    sql_statements = [migration_sql]
                except Exception as stmt_error:
                    logger.error(f"整脚本执行失败: {stmt_error}")
                    sql_statements = [migration_sql]
                    error_count = 1
            else:
                sql_statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
                for statement in sql_statements:
                    if statement:
                        try:
                            await db_manager.execute_query(statement)
                            success_count += 1
                            logger.debug(f"SQL语句执行成功: {statement[:50]}...")
                        except Exception as stmt_error:
                            error_msg = str(stmt_error).lower()
                            # SQLite容错处理：忽略可预期的错误
                            if any(ignore_phrase in error_msg for ignore_phrase in [
                                'duplicate column name',  # 列已存在
                                'table already exists',   # 表已存在
                                'index already exists',   # 索引已存在
                            ]):
                                logger.warning(f"忽略预期错误: {stmt_error}")
                                logger.info(f"SQL语句跳过（结构已存在）: {statement[:50]}...")
                                success_count += 1
                            else:
                                logger.error(f"SQL语句执行失败: {statement[:50]}... | 错误: {stmt_error}")
                                error_count += 1
            
            # 判断迁移成功条件：至少有一条语句成功，或者所有错误都是可忽略的
            if success_count > 0 or error_count == 0:
                # 记录迁移历史
                await self._record_migration(migration_name)
                logger.info(f"✅ 迁移 {migration_name} 执行成功 (成功:{success_count}, 跳过:{len(sql_statements)-success_count-error_count}, 错误:{error_count})")
                return True
            else:
                logger.error(f"❌ 迁移 {migration_name} 执行失败，所有语句都失败了")
                return False
            
        except Exception as e:
            logger.error(f"迁移 {migration_name} 执行失败: {e}")
            return False
    
    async def _is_migration_applied(self, migration_name: str) -> bool:
        """检查迁移是否已经应用"""
        try:
            # 首先确保迁移历史表存在
            await db_manager.execute_query("""
                CREATE TABLE IF NOT EXISTS migration_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            result = await db_manager.fetch_one(
                "SELECT migration_name FROM migration_history WHERE migration_name = ?",
                (migration_name,)
            )
            return result is not None
        except Exception as e:
            logger.error(f"检查迁移状态失败: {e}")
            return False
    
    async def _record_migration(self, migration_name: str):
        """记录迁移历史"""
        try:
            await db_manager.execute_query(
                "INSERT INTO migration_history (migration_name) VALUES (?)",
                (migration_name,)
            )
        except Exception as e:
            logger.error(f"记录迁移历史失败: {e}")
    
    async def cleanup_expired_data(self):
        """清理过期数据"""
        try:
            logger.info("开始清理过期数据...")
            
            # 清理过期的绑定码
            expired_time = datetime.now() - timedelta(hours=24)
            result = await db_manager.execute_query(
                "DELETE FROM binding_codes WHERE expires_at < ? AND is_used = FALSE",
                (expired_time,)
            )
            logger.info(f"清理了 {result} 个过期绑定码")
            
            # 清理旧的活动日志（保留30天）
            old_log_time = datetime.now() - timedelta(days=30)
            result = await db_manager.execute_query(
                "DELETE FROM activity_logs WHERE timestamp < ?",
                (old_log_time,)
            )
            logger.info(f"清理了 {result} 条旧活动日志")
            
            # 清理旧的FSM状态（保留7天）
            old_state_time = datetime.now() - timedelta(days=7)
            result = await db_manager.execute_query(
                "DELETE FROM fsm_states WHERE updated_at < ?",
                (old_state_time,)
            )
            logger.info(f"清理了 {result} 个旧FSM状态")
            
            # 清理旧的自动回复每日统计（保留90天）
            old_stats_time = datetime.now() - timedelta(days=90)
            result = await db_manager.execute_query(
                "DELETE FROM auto_reply_daily_stats WHERE stat_date < ?",
                (old_stats_time.date(),)
            )
            logger.info(f"清理了 {result} 条旧自动回复统计")
            
            logger.info("过期数据清理完成")
            
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")

    async def _fresh_install(self) -> bool:
        """
        全新数据库安装
        
        Returns:
            安装是否成功
        """
        logger.info("执行全新数据库安装...")
        
        try:
            # 若数据库文件已存在但无版本信息，视为“脏新库”，先做硬重置
            try:
                # 检查是否已有任意用户表（排除 sqlite 内置和临时表）
                existing_tables = await db_manager.fetch_all(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            except Exception:
                existing_tables = []

            if existing_tables:
                logger.warning("检测到无版本但存在旧表的数据库，执行硬重置以确保全新架构…")
                try:
                    # 关闭连接池，删除数据库文件及其 WAL/SHM
                    await db_manager.close_all_connections()
                    db_path = db_manager.db_path
                    wal_path = f"{db_path}-wal"
                    shm_path = f"{db_path}-shm"
                    for p in (db_path, wal_path, shm_path):
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                                logger.info(f"已删除数据库相关文件: {p}")
                        except Exception as e:
                            logger.warning(f"删除文件失败 {p}: {e}")
                except Exception as e:
                    logger.warning(f"硬重置数据库时出现问题(可忽略): {e}")

            # 读取并执行主要架构SQL
            schema_path = PathManager.get_database_schema_path()
            
            if not os.path.exists(schema_path):
                logger.error(f"架构文件不存在: {schema_path}")
                return False
            
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # 执行主架构创建
            await self._execute_sql_script(schema_sql)
            
            # 跳过扩展架构执行 - V2.0迁移脚本已包含所有必要字段和表
            logger.info("V2.0架构：跳过扩展架构执行，所有字段已在主架构中包含")
            
            # 确保所有必需表都存在（包括posting_time_slots等）
            await self._ensure_auto_reply_and_keywords_tables()
            
            # adv_sentence 字段由 schema.sql（全新安装）或 migrations 统一管理，不在此处重复兜底
            
            # 执行自动回复架构
            auto_reply_schema_path = PathManager.get_database_schema_path('schema_auto_reply.sql')
            if os.path.exists(auto_reply_schema_path):
                logger.info("执行自动回复功能架构...")
                with open(auto_reply_schema_path, 'r', encoding='utf-8') as f:
                    auto_reply_sql = f.read()
                await self._execute_sql_script(auto_reply_sql)
                logger.info("自动回复功能架构执行完成")
            else:
                logger.warning("自动回复架构文件不存在，跳过自动回复功能初始化")
            
            # 执行至最新版本的迁移（确保 fresh install 也包含增量结构，如评价V2表）
            try:
                _ = await self._migrate_database("0.0.0.0", self.current_schema_version)
            except Exception as e:
                logger.warning(f"fresh install 迁移执行异常（将直接设置版本号）：{e}")
                await self.update_schema_version(self.current_schema_version)
            
            # 执行模板数据初始化
            logger.info("📄 执行模板数据初始化...")
            templates_init_success = await self._initialize_templates()
            
            if not templates_init_success:
                logger.warning("模板数据初始化出现问题，但继续后续流程")
            
            # 执行Schema结构同步检查（确保所有字段都存在）
            logger.info("🔄 执行Schema结构同步检查...")
            schema_sync_success = await schema_sync.synchronize_schema()
            
            if not schema_sync_success:
                logger.warning("Schema同步出现问题，但继续验证表结构")
            
            # 验证安装
            if await self._verify_tables():
                logger.info("✅ 全新安装完成")
                await self._log_initialization()
                return True
            else:
                logger.error("安装后表验证失败")
                return False
                
        except Exception as e:
            logger.error(f"全新安装失败: {e}")
            return False

    async def _get_table_columns(self, table_name: str) -> set:
        """获取指定表的所有列名集合。"""
        try:
            rows = await db_manager.fetch_all(f"PRAGMA table_info({table_name})")
            return {row['name'] for row in rows} if rows else set()
        except Exception:
            return set()

    async def _filter_extended_sql(self, raw_sql: str) -> str:
        """
        过滤扩展SQL中的重复 ADD COLUMN 语句，避免 fresh install 时重复添加列。

        仅针对以下语句做去重：
        - ALTER TABLE merchants ADD COLUMN ...
        - ALTER TABLE cities ADD COLUMN code ...
        其他 CREATE TABLE/INDEX/TRIGGER 语句原样保留。
        """
        import re
        merchants_cols = await self._get_table_columns('merchants')
        cities_cols = await self._get_table_columns('cities')

        filtered_lines = []
        for line in raw_sql.splitlines():
            line_strip = line.strip()
            m = re.match(r"(?i)ALTER\s+TABLE\s+merchants\s+ADD\s+COLUMN\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", line_strip)
            if m:
                col = m.group(1)
                if col in merchants_cols:
                    continue  # 跳过已存在的列
            m2 = re.match(r"(?i)ALTER\s+TABLE\s+cities\s+ADD\s+COLUMN\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", line_strip)
            if m2:
                col2 = m2.group(1)
                if col2 in cities_cols:
                    continue
            filtered_lines.append(line)
        return "\n".join(filtered_lines)

    async def _migrate_database(self, from_version: str, to_version: str) -> bool:
        """
        执行数据库迁移
        
        Args:
            from_version: 源版本
            to_version: 目标版本
            
        Returns:
            迁移是否成功
        """
        logger.info(f"开始迁移: {from_version} -> {to_version}")
        
        try:
            # 获取需要执行的迁移文件
            migration_files = self._get_migration_files(from_version, to_version)
            
            if not migration_files:
                logger.info("未找到需要执行的迁移文件，执行自动迁移")
                # 开发阶段：直接更新到最新版本
                await self._auto_generate_migration(from_version, to_version)
                return True
            
            # 按版本顺序执行迁移
            for migration_file in sorted(migration_files):
                logger.info(f"执行迁移: {migration_file}")
                
                migration_path = PathManager.get_database_migration_file_path(migration_file)
                with open(migration_path, 'r', encoding='utf-8') as f:
                    migration_sql = f.read()
                
                # 条件跳过：2025-09-16-2 城市区县切换在新库（已无旧表/旧列）上无需执行
                try:
                    if '2025_09_16_2_切换为城市区县并重命名外键' in migration_file:
                        # 检查是否存在旧结构
                        has_old_cols = False
                        try:
                            cols = await db_manager.fetch_all("PRAGMA table_info(merchants)")
                            names = [c[1] if isinstance(c, tuple) else c['name'] for c in cols]
                            if 'province_id' in names or 'region_id' in names:
                                has_old_cols = True
                        except Exception:
                            pass
                        # 检查旧表
                        async def table_exists(name: str) -> bool:
                            try:
                                row = await db_manager.fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
                                return bool(row)
                            except Exception:
                                return False
                        if not has_old_cols and not (await table_exists('provinces')) and not (await table_exists('regions')):
                            logger.info("跳过迁移 2025_09_16_2：未检测到旧表/旧列（已是新结构）")
                            await self._record_migration(migration_file)
                            continue
                except Exception as e:
                    logger.warning(f"迁移前置检查异常（继续尝试执行）: {e}")

                # 执行迁移
                success = await self.run_migration(migration_file, migration_sql)
                if not success:
                    logger.error(f"迁移失败: {migration_file}")
                    return False
            
            # 更新到目标版本
            await self.update_schema_version(to_version)
            
            # 验证并补齐关键模板（迁移时确保模板完整性）
            logger.info("📄 验证迁移后模板完整性...")
            await self._verify_critical_templates()
            
            # 执行Schema结构同步检查（确保迁移后所有字段都存在）
            logger.info("🔄 执行迁移后Schema结构同步检查...")
            schema_sync_success = await schema_sync.synchronize_schema()
            
            if not schema_sync_success:
                logger.warning("Schema同步出现问题，但继续验证表结构")
            
            # 验证迁移结果
            if await self._verify_tables():
                logger.info(f"✅ 迁移完成: {to_version}")
                return True
            else:
                logger.error("迁移后表验证失败")
                return False
                
        except Exception as e:
            logger.error(f"数据库迁移失败: {e}")
            return False

    def _get_migration_files(self, from_version: str, to_version: str) -> List[str]:
        """
        获取需要执行的迁移文件列表（按版本排序）
        """
        if not os.path.exists(self.migrations_dir):
            return []

        pattern = r'migration_(\d{4})_(\d{2})_(\d{2})_(\d+)_.*\.sql'
        files: List[tuple[str, str]] = []  # (version, filename)

        for filename in os.listdir(self.migrations_dir):
            if filename.endswith('.sql') and filename.startswith('migration_'):
                m = re.match(pattern, filename)
                if not m:
                    continue
                year, month, day, num = m.groups()
                file_version = f"{year}.{int(month):02d}.{int(day):02d}.{num}"
                if self._version_compare(file_version, from_version) > 0 and \
                   self._version_compare(file_version, to_version) <= 0:
                    files.append((file_version, filename))

        # 按版本从小到大排序，确保 16.15 在 16.2 之前执行
        files.sort(key=lambda x: [int(p) for p in x[0].split('.')])
        return [fn for _, fn in files]

    def _version_compare(self, version1: str, version2: str) -> int:
        """
        比较两个版本号
        
        Returns:
            1 if version1 > version2
            0 if version1 == version2
            -1 if version1 < version2
        """
        def parse_version(version):
            parts = version.split('.')
            return [int(p) for p in parts]
        
        try:
            v1_parts = parse_version(version1)
            v2_parts = parse_version(version2)
            
            for i in range(max(len(v1_parts), len(v2_parts))):
                v1_part = v1_parts[i] if i < len(v1_parts) else 0
                v2_part = v2_parts[i] if i < len(v2_parts) else 0
                
                if v1_part > v2_part:
                    return 1
                elif v1_part < v2_part:
                    return -1
            
            return 0
        except:
            # 如果版本格式有问题，默认认为版本1更新
            return 1

    async def _auto_generate_migration(self, from_version: str, to_version: str):
        """
        自动生成迁移（当没有迁移文件时）
        这种情况通常发生在开发阶段直接修改schema.sql
        """
        logger.info(f"自动生成迁移: {from_version} -> {to_version}")
        
        # 开发模式：直接更新版本号，确保本地云端一致
        await self.update_schema_version(to_version)
        
        # 重新执行schema以确保表结构最新
        schema_path = PathManager.get_database_schema_path()
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            await self._execute_sql_script(schema_sql)
        
        logger.info("✅ 自动迁移完成（确保本地云端同步）")
    
    async def _initialize_templates(self) -> bool:
        """
        初始化模板数据
        
        Returns:
            初始化是否成功
        """
        try:
            logger.info("开始初始化模板数据...")
            
            # 检查模板表是否存在
            templates_table_check = await db_manager.fetch_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='templates'"
            )
            
            if not templates_table_check:
                logger.warning("模板表不存在，跳过模板初始化")
                return False
            
            # 执行模板数据初始化脚本
            templates_schema_path = PathManager.get_database_schema_path('schema_templates.sql')
            if os.path.exists(templates_schema_path):
                logger.info("执行模板数据初始化脚本...")
                with open(templates_schema_path, 'r', encoding='utf-8') as f:
                    templates_sql = f.read()
                await self._execute_sql_script(templates_sql)
                logger.info("✅ 模板数据初始化完成")
                
                # 验证关键模板是否存在
                await self._verify_critical_templates()
                return True
            else:
                logger.warning("模板初始化脚本不存在，跳过模板初始化")
                return False
                
        except Exception as e:
            logger.error(f"模板数据初始化失败: {e}")
            return False
    
    async def _verify_critical_templates(self) -> bool:
        """
        验证关键模板是否存在，如缺失则自动补齐
        
        Returns:
            验证是否成功
        """
        critical_templates = [
            'binding_code_prompt',
            'error_general', 
            'binding_code_request',
            'invalid_binding_code',
            'channel_post_template',
            'binding_success',
            # 绑定流程按钮与状态
            'binding_btn_cancel',
            'binding_btn_preview',
            'merchant_registration_pending',
            'binding_callback_failed',
            'system_initializing',
            'quick_bind_success',
            'merchant_already_registered',
            'merchant_account_suspended',
            'merchant_not_registered',
            'error_system',
            # 商户面板
            'merchant_panel_title',
            'merchant_panel_basic_info',
            'merchant_panel_status_desc',
            'merchant_panel_status_pending_submission',
            'merchant_panel_status_pending_approval',
            'merchant_panel_status_approved',
            'merchant_panel_status_published',
            'merchant_panel_status_expired',
            'merchant_panel_error',
            # 商户帮助
            'merchant_help_welcome',
            'merchant_help_register',
            'merchant_help_existing',
            # 管理员
            'admin_unauthorized',
            'admin_help',
            'status_cancelled',
            # 用户中心与数据校验（标准 user_* 前缀）
            'user_welcome_message',
            'user_no_profile',
            'data_invalid_format',
            'user_profile_title',
            'user_profile_level',
            'user_profile_xp',
            'user_profile_points',
            'user_profile_orders',
            'user_profile_badges',
            'user_profile_card'
        ]
        
        missing_templates = []
        
        for template_key in critical_templates:
            result = await db_manager.fetch_one(
                "SELECT key FROM templates WHERE key = ?", 
                (template_key,)
            )
            
            if not result:
                missing_templates.append(template_key)
        
        if missing_templates:
            logger.warning(f"检测到缺失的关键模板: {missing_templates}")
            
            # 自动补齐缺失的关键模板
            default_templates = {
                'binding_code_prompt': '🔑 请输入您的绑定码：',
                'error_general': '❌ 系统暂时无法处理您的请求。请稍后重试。',
            'binding_code_request': '🔑 要上榜，您需要一个绑定码。请联系管理员获取您的绑定码。',
                'invalid_binding_code': '❌ 绑定码无效或已过期。请联系管理员获取新的绑定码。',
                'channel_post_template': '{adv_html}\n\n💃🏻昵称：{nickname_html}\n🌈地区：{district_html}\n🎫课费：{price_p_html}      {price_pp_html}\n🏷️标签：{tags_html}\n✍️评价：「{report_html}」\n\n🎉优惠：{offer_html}',
                'binding_success': '🎉 注册成功！您的商户资料已成功创建并激活。',
                # 绑定流程通用按钮
                'binding_btn_cancel': '❌ 取消注册',
                'binding_btn_preview': '📋 预览信息',
                'merchant_registration_pending': '⏳ 您的注册正在处理中，请稍候。',
                'binding_callback_failed': '处理失败，请重试',
                'system_initializing': '系统初始化中，请稍候…',
                'quick_bind_success': '绑定成功！系统将引导你完善资料。',
                'merchant_already_registered': '您已注册，当前状态：{status_display}',
                'merchant_account_suspended': '您的账号已被暂停，请联系管理员。',
                'merchant_not_registered': '您还不是商户，请先发送“上榜流程”并完成绑定。',
                'error_system': '❌',
                # 商户面板
                'merchant_panel_title': '商户面板',
                'merchant_panel_basic_info': '基本信息',
                'merchant_panel_status_desc': '状态说明',
                'merchant_panel_status_pending_submission': '请在机器人中继续完善信息后再提交审核。',
                'merchant_panel_status_pending_approval': '资料已提交，等待管理员审核。',
                'merchant_panel_status_approved': '已审核通过，等待发布。',
                'merchant_panel_status_published': '已发布，当前活跃。',
                'merchant_panel_status_expired': '已过期或被暂停。',
                'merchant_panel_error': '获取商户面板信息失败，请稍后重试。',
                # 商户帮助
                'merchant_help_welcome': '👋 欢迎使用商户助手。',
                'merchant_help_register': '发送“上榜流程”开始注册，或输入绑定码完成绑定。',
                'merchant_help_existing': '已注册商户请点击“我的资料”查看与管理。',
                # 管理员
                'admin_unauthorized': '❌ 你没有管理员权限。',
                'admin_help': '管理员命令：/set_button /help 等。',
                'status_cancelled': '❌ 操作已取消。',
                # 用户中心与数据校验默认文案
                'user_welcome_message': '👋 欢迎！这是你的主菜单。',
                'user_no_profile': 'ℹ️ 暂无个人资料，请先完善信息。',
                'data_invalid_format': '格式错误',
                'user_profile_title': '📋 用户资料',
                'user_profile_level': '等级：{level_name}',
                'user_profile_xp': '经验值：{xp}',
                'user_profile_points': '积分：{points}',
                'user_profile_orders': '完成订单：{order_count}',
                'user_profile_badges': '勋章：{badges_text}',
                'user_profile_card': (
                    '👤 {username}    {level_name}\n'
                    '═══════════════════════════\n\n'
                    '    📊 成长值\n'
                    '    🔥 XP: {xp}    💰 积分: {points}\n\n'
                    '    🏆 战绩: {order_count} 胜\n\n'
                    '    🏅 勋章: {badges_text}\n\n'
                    '═══════════════════════════'
                )
            }
            
            for template_key in missing_templates:
                if template_key in default_templates:
                    try:
                        await db_manager.execute_query(
                            "INSERT OR IGNORE INTO templates (key, content) VALUES (?, ?)",
                            (
                                template_key,
                                default_templates[template_key]
                            )
                        )
                        logger.info(f"✅ 自动补齐模板: {template_key}")
                    except Exception as e:
                        logger.error(f"补齐模板失败 {template_key}: {e}")
            
            return len(missing_templates) == 0
        else:
            logger.info("✅ 所有关键模板验证通过")
            # 兼容性修正：将历史模板中的“/panel/商户面板”引导改为“我的资料”按钮
            try:
                row = await db_manager.fetch_one(
                    "SELECT content FROM templates WHERE key = ?",
                    ('merchant_help_existing',)
                )
                if row:
                    content = row['content'] if isinstance(row, dict) else row[0]
                    if isinstance(content, str) and ("/panel" in content or "商户面板" in content):
                        new_content = content.replace('/panel', '点击“我的资料”').replace('商户面板', '“我的资料”')
                        await db_manager.execute_query(
                            "UPDATE templates SET content = ? WHERE key = ?",
                            (new_content, 'merchant_help_existing')
                        )
                        logger.info("🔧 已更新 merchant_help_existing 模板为“我的资料”引导")
            except Exception as e:
                logger.debug(f"模板兼容修正跳过: {e}")
            return True

    def generate_migration_file(self, description: str) -> str:
        """
        开发工具：生成新的迁移文件
        
        Args:
            description: 迁移描述
            
        Returns:
            生成的文件路径
        """
        # 自动生成下一个版本号
        next_version = self._generate_next_version()
        
        # 生成文件名
        version_parts = next_version.split('.')
        year, month, day, num = version_parts
        
        # 清理描述，生成安全的文件名
        safe_desc = re.sub(r'[^\w\u4e00-\u9fff]', '_', description)
        filename = f"migration_{year}_{month}_{day}_{num}_{safe_desc}.sql"
        
        # 创建迁移目录
        PathManager.ensure_directory(self.migrations_dir)
        
        # 生成迁移文件内容
        migration_content = f"""-- {filename}
-- 描述: {description}  
-- 前置版本: {self.current_schema_version}
-- 目标版本: {next_version}
-- 生成时间: {datetime.now().isoformat()}

-- 向前迁移 (UP)
-- 在这里添加你的数据库结构更改

-- 更新版本号
INSERT OR REPLACE INTO system_config (config_key, config_value, description) 
VALUES ('schema_version', '{next_version}', '{description}');

-- 向后迁移 (DOWN) - 可选，用于回滚
-- 取消注释并添加回滚逻辑
-- UPDATE system_config SET config_value = '{self.current_schema_version}' WHERE config_key = 'schema_version';
"""
        
        # 写入文件
        file_path = PathManager.get_database_migration_file_path(filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(migration_content)
        
        # 更新当前代码中的版本号
        self.current_schema_version = next_version
        
        logger.info(f"✅ 迁移文件已生成: {filename}")
        logger.info(f"📝 请更新代码中的 current_schema_version 为: {next_version}")
        return file_path

    def _generate_next_version(self) -> str:
        """自动生成下一个版本号"""
        today = datetime.now()
        base_version = f"{today.year}.{today.month:02d}.{today.day:02d}"
        
        # 查找今天已有的版本
        existing_versions = []
        if os.path.exists(self.migrations_dir):
            pattern = r'migration_(\d{4})_(\d{2})_(\d{2})_(\d+)_.*\.sql'
            for filename in os.listdir(self.migrations_dir):
                match = re.match(pattern, filename)
                if match:
                    year, month, day, num = match.groups()
                    if f"{year}.{int(month):02d}.{int(day):02d}" == base_version:
                        existing_versions.append(int(num))
        
        # 生成下一个编号
        next_number = max(existing_versions + [0]) + 1
        return f"{base_version}.{next_number}"
    
    async def get_database_stats(self) -> Dict[str, int]:
        """
        获取数据库统计信息
        
        Returns:
            包含各表记录数的字典
        """
        stats = {}
        tables = [
            'merchants', 'orders', 'binding_codes', 'button_configs', 'activity_logs', 'fsm_states',
            'auto_reply_triggers', 'auto_reply_messages', 'auto_reply_daily_stats',
            'cities', 'districts', 'keywords', 'merchant_keywords'
        ]
        
        try:
            for table in tables:
                result = await db_manager.fetch_one(f"SELECT COUNT(*) FROM {table}")
                stats[table] = result[0] if result else 0
            
            logger.debug(f"数据库统计信息: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            return {}
    
    async def backup_database(self, backup_path: str) -> bool:
        """
        备份数据库
        
        Args:
            backup_path: 备份文件路径
            
        Returns:
            备份是否成功
        """
        try:
            import shutil
            
            # 确保备份目录存在
            PathManager.ensure_parent_directory(backup_path)
            
            # 复制数据库文件
            db_path = db_manager.db_path
            shutil.copy2(db_path, backup_path)
            
            logger.info(f"数据库备份成功: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return False

    async def _ensure_critical_templates(self):
        """确保关键模板存在于数据库中"""
        try:
            from config import MESSAGE_TEMPLATES
            
            # 需要同步到数据库的关键模板
            critical_templates = [
                "channel_info_display",
                "channel_click_notification", 
                "order_notification_merchant"
            ]
            
            for template_key in critical_templates:
                # 检查模板是否已存在于数据库
                result = await db_manager.fetch_one(
                    "SELECT key FROM templates WHERE key = ?",
                    (template_key,)
                )
                
                if not result:
                    # 从config.py获取模板内容
                    template_content = MESSAGE_TEMPLATES.get(template_key)
                    if template_content:
                        logger.info(f"添加缺失的{template_key}模板")
                        await db_manager.execute_query(
                            "INSERT OR IGNORE INTO templates (key, content) VALUES (?, ?)",
                            (template_key, template_content.strip())
                        )
                        logger.info(f"✅ {template_key}模板添加成功")
                    else:
                        logger.warning(f"config.py中未找到{template_key}模板定义")
                else:
                    logger.debug(f"{template_key}模板已存在")
                
        except Exception as e:
            logger.error(f"确保关键模板存在失败: {e}")
            # 不抛出异常，避免影响系统启动

# 创建全局数据库初始化器实例
db_initializer = DatabaseInitializer()

async def init_database() -> bool:
    """
    初始化数据库的便捷函数
    
    Returns:
        初始化是否成功
    """
    return await db_initializer.initialize_database()

async def cleanup_database():
    """清理数据库的便捷函数"""
    await db_initializer.cleanup_expired_data()

async def get_db_stats() -> Dict[str, int]:
    """获取数据库统计信息的便捷函数"""
    return await db_initializer.get_database_stats()
