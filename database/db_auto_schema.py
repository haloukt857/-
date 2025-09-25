"""
自动数据库架构管理器
根据Python代码中的数据库操作自动推断和创建表结构
"""

import os
import re
import ast
import logging
import importlib
from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime
from .db_connection import db_manager
from pathmanager import PathManager

logger = logging.getLogger(__name__)

class SchemaField:
    """数据库字段定义"""
    def __init__(self, name: str, type_: str, nullable: bool = True, 
                 primary_key: bool = False, unique: bool = False, 
                 default: Any = None):
        self.name = name
        self.type = type_
        self.nullable = nullable
        self.primary_key = primary_key
        self.unique = unique
        self.default = default
    
    def to_sql(self) -> str:
        """转换为SQL定义"""
        sql = f"{self.name} {self.type}"
        
        if self.primary_key:
            sql += " PRIMARY KEY"
            if self.type.upper() == "INTEGER":
                sql += " AUTOINCREMENT"
        
        if not self.nullable and not self.primary_key:
            sql += " NOT NULL"
        
        if self.unique and not self.primary_key:
            sql += " UNIQUE"
        
        if self.default is not None:
            if isinstance(self.default, str):
                sql += f" DEFAULT '{self.default}'"
            else:
                sql += f" DEFAULT {self.default}"
        
        return sql

class TableSchema:
    """数据库表架构"""
    def __init__(self, name: str):
        self.name = name
        self.fields: List[SchemaField] = []
        self.indexes: List[str] = []
        self.foreign_keys: List[str] = []
    
    def add_field(self, field: SchemaField):
        """添加字段"""
        self.fields.append(field)
    
    def add_index(self, columns: List[str], unique: bool = False):
        """添加索引"""
        index_type = "UNIQUE INDEX" if unique else "INDEX"
        index_name = f"idx_{self.name}_{'_'.join(columns)}"
        self.indexes.append(f"CREATE {index_type} {index_name} ON {self.name} ({', '.join(columns)})")
    
    def to_sql(self) -> str:
        """转换为CREATE TABLE SQL语句"""
        if not self.fields:
            return ""
        
        field_definitions = [field.to_sql() for field in self.fields]
        
        sql = f"CREATE TABLE IF NOT EXISTS {self.name} (\n"
        sql += ",\n".join(f"    {field_def}" for field_def in field_definitions)
        
        if self.foreign_keys:
            sql += ",\n" + ",\n".join(f"    {fk}" for fk in self.foreign_keys)
        
        sql += "\n)"
        
        return sql

class AutoSchemaManager:
    """自动架构管理器"""
    
    def __init__(self):
        self.schemas: Dict[str, TableSchema] = {}
        self.database_dir = PathManager.get_database_directory()
    
    async def analyze_codebase(self) -> Dict[str, TableSchema]:
        """分析代码库并推断表结构"""
        logger.info("开始分析代码库，推断数据库表结构...")
        
        # 分析所有数据库操作文件
        db_files = [f for f in os.listdir(self.database_dir) 
                   if f.startswith('db_') and f.endswith('.py') and f != 'db_auto_schema.py']
        
        for db_file in db_files:
            logger.info(f"分析文件: {db_file}")
            await self._analyze_db_file(db_file)
        
        # 手动定义一些核心表结构（基于实际使用模式）
        await self._define_core_schemas()
        
        logger.info(f"分析完成，发现 {len(self.schemas)} 个表")
        return self.schemas
    
    async def _analyze_db_file(self, filename: str):
        """分析单个数据库文件"""
        file_path = os.path.join(self.database_dir, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找SQL查询中的表名和字段
            await self._extract_sql_patterns(content)
            
        except Exception as e:
            logger.warning(f"分析文件 {filename} 失败: {e}")
    
    async def _extract_sql_patterns(self, content: str):
        """从代码中提取SQL模式"""
        # 查找INSERT语句
        insert_pattern = r'INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(\w+)\s*\((.*?)\)\s*VALUES'
        insert_matches = re.finditer(insert_pattern, content, re.IGNORECASE | re.DOTALL)
        
        for match in insert_matches:
            table_name = match.group(1)
            columns = [col.strip() for col in match.group(2).split(',')]
            await self._update_table_schema(table_name, columns)
        
        # 查找UPDATE语句
        update_pattern = r'UPDATE\s+(\w+)\s+SET\s+(.*?)\s+WHERE'
        update_matches = re.finditer(update_pattern, content, re.IGNORECASE | re.DOTALL)
        
        for match in update_matches:
            table_name = match.group(1)
            set_clause = match.group(2)
            columns = [col.split('=')[0].strip() for col in set_clause.split(',')]
            await self._update_table_schema(table_name, columns)
        
        # 查找SELECT语句中的表名
        select_pattern = r'SELECT\s+.*?\s+FROM\s+(\w+)'
        select_matches = re.finditer(select_pattern, content, re.IGNORECASE)
        
        for match in select_matches:
            table_name = match.group(1)
            if table_name not in self.schemas:
                self.schemas[table_name] = TableSchema(table_name)
    
    async def _update_table_schema(self, table_name: str, columns: List[str]):
        """更新表架构"""
        if table_name not in self.schemas:
            self.schemas[table_name] = TableSchema(table_name)
        
        schema = self.schemas[table_name]
        existing_fields = {field.name for field in schema.fields}
        
        for column in columns:
            column = column.strip()
            if column and column not in existing_fields:
                # 根据字段名推断类型
                field_type = self._infer_field_type(column)
                schema.add_field(SchemaField(column, field_type))
    
    def _infer_field_type(self, field_name: str) -> str:
        """根据字段名推断数据类型"""
        field_name = field_name.lower()
        
        # ID字段
        if field_name in ['id', 'merchant_id', 'user_id', 'chat_id', 'order_id', 'trigger_id', 'message_id']:
            return "INTEGER"
        
        # 时间字段
        if any(time_word in field_name for time_word in ['timestamp', 'created_at', 'updated_at', 'expires_at', 'date']):
            return "TIMESTAMP"
        
        # 布尔字段
        if any(bool_word in field_name for bool_word in ['is_', 'has_', 'enabled', 'active']):
            return "BOOLEAN"
        
        # 计数字段
        if any(count_word in field_name for count_word in ['count', 'num_', 'total_', 'amount']):
            return "INTEGER"
        
        # 状态字段（通常较短）
        if field_name in ['status', 'type', 'category', 'region']:
            return "VARCHAR(50)"
        
        # 名称字段
        if 'name' in field_name or field_name in ['title', 'subject']:
            return "VARCHAR(255)"
        
        # 长文本字段
        if any(text_word in field_name for text_word in ['content', 'description', 'details', 'data', 'profile_data']):
            return "TEXT"
        
        # 默认为文本
        return "TEXT"
    
    async def _define_core_schemas(self):
        """定义核心表结构（基于实际业务需求）"""
        
        # 商户表
        merchants = TableSchema("merchants")
        merchants.add_field(SchemaField("id", "INTEGER", primary_key=True))
        merchants.add_field(SchemaField("chat_id", "INTEGER", nullable=False, unique=True))
        merchants.add_field(SchemaField("name", "VARCHAR(255)", nullable=False))
        merchants.add_field(SchemaField("region", "VARCHAR(100)"))
        merchants.add_field(SchemaField("category", "VARCHAR(100)"))
        merchants.add_field(SchemaField("contact_info", "TEXT"))
        merchants.add_field(SchemaField("profile_data", "TEXT"))
        merchants.add_field(SchemaField("status", "VARCHAR(20)", default="pending"))
        merchants.add_field(SchemaField("binding_code", "VARCHAR(20)"))
        merchants.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        merchants.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        # 新上榜流程扩展字段
        merchants.add_field(SchemaField("merchant_type", "TEXT", default="teacher"))
        merchants.add_field(SchemaField("city_id", "INTEGER"))
        merchants.add_field(SchemaField("district_id", "INTEGER"))
        merchants.add_field(SchemaField("p_price", "INTEGER"))
        merchants.add_field(SchemaField("pp_price", "INTEGER"))
        merchants.add_field(SchemaField("custom_description", "TEXT"))
        merchants.add_field(SchemaField("user_info", "TEXT"))
        merchants.add_field(SchemaField("channel_link", "TEXT"))
        merchants.add_index(["chat_id"], unique=True)
        merchants.add_index(["status"])
        merchants.add_index(["binding_code"])
        merchants.add_index(["city_id"])
        merchants.add_index(["district_id"])
        merchants.add_index(["merchant_type"])
        self.schemas["merchants"] = merchants
        
        # 订单表
        orders = TableSchema("orders")
        orders.add_field(SchemaField("id", "INTEGER", primary_key=True))
        orders.add_field(SchemaField("merchant_id", "INTEGER", nullable=False))
        orders.add_field(SchemaField("user_id", "INTEGER", nullable=False))
        orders.add_field(SchemaField("chat_id", "INTEGER", nullable=False))
        orders.add_field(SchemaField("order_type", "VARCHAR(50)"))  # 添加订单类型
        orders.add_field(SchemaField("order_data", "TEXT"))
        orders.add_field(SchemaField("status", "VARCHAR(20)", default="pending"))
        orders.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        orders.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        orders.foreign_keys.append("FOREIGN KEY (merchant_id) REFERENCES merchants(id)")
        orders.add_index(["merchant_id"])
        orders.add_index(["user_id"])
        orders.add_index(["status"])
        orders.add_index(["order_type"])
        self.schemas["orders"] = orders
        
        # 绑定码表
        binding_codes = TableSchema("binding_codes")
        binding_codes.add_field(SchemaField("id", "INTEGER", primary_key=True))
        binding_codes.add_field(SchemaField("code", "VARCHAR(20)", nullable=False, unique=True))
        binding_codes.add_field(SchemaField("merchant_id", "INTEGER"))
        binding_codes.add_field(SchemaField("is_used", "BOOLEAN", default="FALSE"))
        binding_codes.add_field(SchemaField("used_by_user_id", "INTEGER"))
        binding_codes.add_field(SchemaField("expires_at", "TIMESTAMP"))
        binding_codes.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        binding_codes.add_field(SchemaField("used_at", "TIMESTAMP"))
        binding_codes.add_index(["code"], unique=True)
        binding_codes.add_index(["is_used"])
        binding_codes.add_index(["expires_at"])
        self.schemas["binding_codes"] = binding_codes
        
        # 活动日志表
        activity_logs = TableSchema("activity_logs")
        activity_logs.add_field(SchemaField("id", "INTEGER", primary_key=True))
        activity_logs.add_field(SchemaField("user_id", "INTEGER", nullable=False))
        activity_logs.add_field(SchemaField("action_type", "VARCHAR(50)", nullable=False))
        activity_logs.add_field(SchemaField("details", "TEXT"))
        activity_logs.add_field(SchemaField("timestamp", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        activity_logs.add_field(SchemaField("merchant_id", "INTEGER"))
        activity_logs.add_field(SchemaField("button_id", "INTEGER"))
        activity_logs.add_index(["user_id"])
        activity_logs.add_index(["action_type"])
        activity_logs.add_index(["timestamp"])
        activity_logs.add_index(["merchant_id"])
        self.schemas["activity_logs"] = activity_logs
        
        # FSM状态表
        fsm_states = TableSchema("fsm_states")
        fsm_states.add_field(SchemaField("id", "INTEGER", primary_key=True))
        fsm_states.add_field(SchemaField("user_id", "INTEGER", nullable=False, unique=True))
        fsm_states.add_field(SchemaField("state", "VARCHAR(100)"))
        fsm_states.add_field(SchemaField("data", "TEXT"))
        fsm_states.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        fsm_states.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        fsm_states.add_index(["user_id"], unique=True)
        self.schemas["fsm_states"] = fsm_states
        
        # 系统配置表
        system_config = TableSchema("system_config")
        system_config.add_field(SchemaField("id", "INTEGER", primary_key=True))
        system_config.add_field(SchemaField("config_key", "VARCHAR(100)", nullable=False, unique=True))
        system_config.add_field(SchemaField("config_value", "TEXT"))
        system_config.add_field(SchemaField("description", "TEXT"))
        system_config.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        system_config.add_index(["config_key"], unique=True)
        self.schemas["system_config"] = system_config
        
        # 按钮配置表
        button_configs = TableSchema("button_configs")
        button_configs.add_field(SchemaField("id", "INTEGER", primary_key=True))
        button_configs.add_field(SchemaField("button_type", "VARCHAR(50)", nullable=False))
        button_configs.add_field(SchemaField("config_data", "TEXT"))
        button_configs.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        button_configs.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        self.schemas["button_configs"] = button_configs
        
        # 自动回复表 - 修复缺失字段
        auto_reply_triggers = TableSchema("auto_reply_triggers")
        auto_reply_triggers.add_field(SchemaField("id", "INTEGER", primary_key=True))
        auto_reply_triggers.add_field(SchemaField("admin_id", "INTEGER", nullable=False))
        auto_reply_triggers.add_field(SchemaField("trigger_text", "TEXT", nullable=False))
        auto_reply_triggers.add_field(SchemaField("match_type", "VARCHAR(20)", default="contains"))
        auto_reply_triggers.add_field(SchemaField("created_by", "INTEGER", nullable=False))  # 添加缺失字段
        auto_reply_triggers.add_field(SchemaField("priority_order", "INTEGER", default="0"))
        auto_reply_triggers.add_field(SchemaField("is_active", "BOOLEAN", default="TRUE"))
        auto_reply_triggers.add_field(SchemaField("trigger_count", "INTEGER", default="0"))  # 添加统计字段
        auto_reply_triggers.add_field(SchemaField("last_triggered_at", "TIMESTAMP"))  # 添加最后触发时间
        auto_reply_triggers.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        auto_reply_triggers.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        auto_reply_triggers.add_index(["admin_id"])
        auto_reply_triggers.add_index(["is_active"])
        auto_reply_triggers.add_index(["priority_order"])
        auto_reply_triggers.add_index(["created_by"])  # 添加索引
        self.schemas["auto_reply_triggers"] = auto_reply_triggers
        
        auto_reply_messages = TableSchema("auto_reply_messages")
        auto_reply_messages.add_field(SchemaField("id", "INTEGER", primary_key=True))
        auto_reply_messages.add_field(SchemaField("trigger_id", "INTEGER", nullable=False))
        auto_reply_messages.add_field(SchemaField("message_content", "TEXT", nullable=False))
        auto_reply_messages.add_field(SchemaField("display_order", "INTEGER", default="0"))
        auto_reply_messages.add_field(SchemaField("is_active", "BOOLEAN", default="TRUE"))
        auto_reply_messages.add_field(SchemaField("send_count", "INTEGER", default="0"))  # 添加统计字段
        auto_reply_messages.add_field(SchemaField("last_sent_at", "TIMESTAMP"))  # 添加最后发送时间
        auto_reply_messages.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        auto_reply_messages.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))  # 添加更新时间
        auto_reply_messages.foreign_keys.append("FOREIGN KEY (trigger_id) REFERENCES auto_reply_triggers(id) ON DELETE CASCADE")
        auto_reply_messages.add_index(["trigger_id"])
        auto_reply_messages.add_index(["display_order"])
        auto_reply_messages.add_index(["is_active"])
        self.schemas["auto_reply_messages"] = auto_reply_messages
        
        auto_reply_daily_stats = TableSchema("auto_reply_daily_stats")
        auto_reply_daily_stats.add_field(SchemaField("id", "INTEGER", primary_key=True))
        auto_reply_daily_stats.add_field(SchemaField("trigger_id", "INTEGER", nullable=False))
        auto_reply_daily_stats.add_field(SchemaField("stat_date", "DATE", nullable=False))
        auto_reply_daily_stats.add_field(SchemaField("trigger_count", "INTEGER", default="0"))
        auto_reply_daily_stats.add_field(SchemaField("unique_users", "INTEGER", default="0"))
        auto_reply_daily_stats.foreign_keys.append("FOREIGN KEY (trigger_id) REFERENCES auto_reply_triggers(id) ON DELETE CASCADE")
        auto_reply_daily_stats.add_index(["trigger_id", "stat_date"], unique=True)
        self.schemas["auto_reply_daily_stats"] = auto_reply_daily_stats
        
        # 地区管理表（唯一标准：城市/区县）
        cities = TableSchema("cities")
        cities.add_field(SchemaField("id", "INTEGER", primary_key=True))
        cities.add_field(SchemaField("name", "VARCHAR(100)", nullable=False, unique=True))
        cities.add_field(SchemaField("code", "VARCHAR(10)", default="''"))
        cities.add_field(SchemaField("display_order", "INTEGER", default="0"))
        cities.add_field(SchemaField("is_active", "BOOLEAN", default="TRUE"))
        cities.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        cities.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        cities.add_index(["name"], unique=True)
        cities.add_index(["display_order"])
        cities.add_index(["is_active"])
        self.schemas["cities"] = cities
        
        districts = TableSchema("districts")
        districts.add_field(SchemaField("id", "INTEGER", primary_key=True))
        districts.add_field(SchemaField("city_id", "INTEGER", nullable=False))
        districts.add_field(SchemaField("name", "VARCHAR(100)", nullable=False))
        districts.add_field(SchemaField("code", "VARCHAR(10)", default="''"))
        districts.add_field(SchemaField("display_order", "INTEGER", default="0"))
        districts.add_field(SchemaField("is_active", "BOOLEAN", default="TRUE"))
        districts.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        districts.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        districts.foreign_keys.append("FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE CASCADE")
        districts.add_index(["city_id"])
        districts.add_index(["name"])
        districts.add_index(["display_order"])
        districts.add_index(["is_active"])
        self.schemas["districts"] = districts
        
        # 关键词管理表
        keywords = TableSchema("keywords")
        keywords.add_field(SchemaField("id", "INTEGER", primary_key=True))
        keywords.add_field(SchemaField("name", "VARCHAR(255)", nullable=False, unique=True))  # 修改为name字段
        keywords.add_field(SchemaField("display_order", "INTEGER", default="0"))
        keywords.add_field(SchemaField("is_active", "BOOLEAN", default="TRUE"))
        keywords.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        keywords.add_field(SchemaField("updated_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        keywords.add_index(["name"], unique=True)
        keywords.add_index(["display_order"])
        keywords.add_index(["is_active"])
        self.schemas["keywords"] = keywords
        
        merchant_keywords = TableSchema("merchant_keywords")
        merchant_keywords.add_field(SchemaField("id", "INTEGER", primary_key=True))
        merchant_keywords.add_field(SchemaField("merchant_id", "INTEGER", nullable=False))
        merchant_keywords.add_field(SchemaField("keyword_id", "INTEGER", nullable=False))
        merchant_keywords.add_field(SchemaField("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"))
        merchant_keywords.foreign_keys.append("FOREIGN KEY (merchant_id) REFERENCES merchants(id) ON DELETE CASCADE")
        merchant_keywords.foreign_keys.append("FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE")
        merchant_keywords.add_index(["merchant_id"])
        merchant_keywords.add_index(["keyword_id"])
        merchant_keywords.add_index(["merchant_id", "keyword_id"], unique=True)
        self.schemas["merchant_keywords"] = merchant_keywords
    
    async def migrate_existing_tables(self) -> bool:
        """迁移现有表，添加缺失的字段"""
        try:
            logger.info("开始检查并迁移现有数据库表...")
            from database.db_connection import db_manager
            
            # 确保 cities/districts 具备必要字段
            try:
                await db_manager.execute_query("SELECT display_order FROM cities LIMIT 1")
            except Exception:
                logger.info("为cities表添加缺失字段...")
                await db_manager.execute_query("ALTER TABLE cities ADD COLUMN display_order INTEGER DEFAULT 0")
                await db_manager.execute_query("ALTER TABLE cities ADD COLUMN is_active BOOLEAN DEFAULT TRUE") 
                await db_manager.execute_query("ALTER TABLE cities ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                logger.info("cities表字段迁移完成")
            
            try:
                await db_manager.execute_query("SELECT display_order FROM districts LIMIT 1")
            except Exception:
                logger.info("为districts表添加缺失字段...")
                await db_manager.execute_query("ALTER TABLE districts ADD COLUMN display_order INTEGER DEFAULT 0")
                await db_manager.execute_query("ALTER TABLE districts ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
                await db_manager.execute_query("ALTER TABLE districts ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                logger.info("districts表字段迁移完成")
            
            # 检查keywords表是否需要添加字段（包括name字段）
            # 首先检查name字段
            try:
                await db_manager.execute_query("SELECT name FROM keywords LIMIT 1")
            except Exception:
                logger.info("为keywords表添加name字段...")
                await db_manager.execute_query("ALTER TABLE keywords ADD COLUMN name VARCHAR(255)")
                logger.info("keywords表name字段添加完成")
                
            # 然后检查其他字段
            try:
                await db_manager.execute_query("SELECT display_order FROM keywords LIMIT 1")
            except Exception:
                logger.info("为keywords表添加其他缺失字段...")
                await db_manager.execute_query("ALTER TABLE keywords ADD COLUMN display_order INTEGER DEFAULT 0")
                await db_manager.execute_query("ALTER TABLE keywords ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                logger.info("keywords表字段迁移完成")
            
            # 检查auto_reply_triggers表是否需要添加字段
            # 首先检查created_by字段
            try:
                await db_manager.execute_query("SELECT created_by FROM auto_reply_triggers LIMIT 1")
            except Exception:
                logger.info("为auto_reply_triggers表添加created_by字段...")
                await db_manager.execute_query("ALTER TABLE auto_reply_triggers ADD COLUMN created_by INTEGER DEFAULT 0")
                logger.info("auto_reply_triggers表created_by字段添加完成")
            
            # 检查其他缺失字段
            try:
                await db_manager.execute_query("SELECT match_type FROM auto_reply_triggers LIMIT 1")
            except Exception:
                logger.info("为auto_reply_triggers表添加match_type字段...")
                await db_manager.execute_query("ALTER TABLE auto_reply_triggers ADD COLUMN match_type VARCHAR(20) DEFAULT 'contains'")
                logger.info("auto_reply_triggers表match_type字段添加完成")
            
            try:
                await db_manager.execute_query("SELECT priority_order FROM auto_reply_triggers LIMIT 1")
            except Exception:
                logger.info("为auto_reply_triggers表添加priority_order字段...")
                await db_manager.execute_query("ALTER TABLE auto_reply_triggers ADD COLUMN priority_order INTEGER DEFAULT 0")
                logger.info("auto_reply_triggers表priority_order字段添加完成")
            
            try:
                await db_manager.execute_query("SELECT trigger_count FROM auto_reply_triggers LIMIT 1")
            except Exception:
                logger.info("为auto_reply_triggers表添加统计字段...")
                await db_manager.execute_query("ALTER TABLE auto_reply_triggers ADD COLUMN trigger_count INTEGER DEFAULT 0")
                await db_manager.execute_query("ALTER TABLE auto_reply_triggers ADD COLUMN last_triggered_at TIMESTAMP")
                logger.info("auto_reply_triggers表统计字段添加完成")
            
            # 检查auto_reply_messages表是否需要添加字段
            try:
                await db_manager.execute_query("SELECT display_order FROM auto_reply_messages LIMIT 1")
            except Exception:
                logger.info("为auto_reply_messages表添加缺失字段...")
                await db_manager.execute_query("ALTER TABLE auto_reply_messages ADD COLUMN display_order INTEGER DEFAULT 0")
                await db_manager.execute_query("ALTER TABLE auto_reply_messages ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
                logger.info("auto_reply_messages表字段迁移完成")
            
            try:
                await db_manager.execute_query("SELECT send_count FROM auto_reply_messages LIMIT 1")
            except Exception:
                logger.info("为auto_reply_messages表添加统计字段...")
                await db_manager.execute_query("ALTER TABLE auto_reply_messages ADD COLUMN send_count INTEGER DEFAULT 0")
                await db_manager.execute_query("ALTER TABLE auto_reply_messages ADD COLUMN last_sent_at TIMESTAMP")
                await db_manager.execute_query("ALTER TABLE auto_reply_messages ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                logger.info("auto_reply_messages表统计字段添加完成")
            
            # 检查orders表是否需要添加order_type字段
            try:
                await db_manager.execute_query("SELECT order_type FROM orders LIMIT 1")
            except Exception:
                logger.info("为orders表添加order_type字段...")
                await db_manager.execute_query("ALTER TABLE orders ADD COLUMN order_type VARCHAR(50)")
                logger.info("orders表order_type字段添加完成")
            
            logger.info("数据库表迁移检查完成")
            return True
            
        except Exception as e:
            logger.error(f"数据库表迁移失败: {e}")
            return False

    async def _create_indexes_safely(self, table_name: str, indexes: List[str]) -> None:
        """安全地创建索引，避免重复创建已存在的索引"""
        try:
            from database.db_connection import db_manager
            
            # 获取现有索引列表
            existing_indexes = await self._get_existing_indexes(table_name)
            
            for index_sql in indexes:
                try:
                    # 从SQL中提取索引名
                    index_name = self._extract_index_name(index_sql)
                    
                    if index_name in existing_indexes:
                        logger.debug(f"索引 {index_name} 已存在，跳过创建")
                        continue
                    
                    await db_manager.execute_query(index_sql)
                    logger.debug(f"索引 {index_name} 创建成功")
                    
                except Exception as e:
                    # 如果是索引已存在的错误，记录为debug级别
                    if "already exists" in str(e).lower():
                        logger.debug(f"索引已存在，跳过: {index_sql}")
                    else:
                        logger.warning(f"创建索引失败: {index_sql}, 错误: {e}")
                        
        except Exception as e:
            logger.error(f"安全创建索引失败: {e}")
    
    async def _get_existing_indexes(self, table_name: str) -> set:
        """获取表的现有索引列表"""
        try:
            from database.db_connection import db_manager
            
            query = """
            SELECT name FROM sqlite_master 
            WHERE type = 'index' AND tbl_name = ?
            AND name NOT LIKE 'sqlite_%'
            """
            
            results = await db_manager.fetch_all(query, (table_name,))
            return {row[0] for row in results} if results else set()
            
        except Exception as e:
            logger.warning(f"获取现有索引失败: {e}")
            return set()
    
    def _extract_index_name(self, index_sql: str) -> str:
        """从CREATE INDEX SQL语句中提取索引名"""
        try:
            import re
            # 匹配 CREATE [UNIQUE] INDEX index_name ON table_name
            match = re.search(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)\s+ON', index_sql, re.IGNORECASE)
            if match:
                return match.group(1)
            return "unknown_index"
        except Exception:
            return "unknown_index"

    async def create_tables(self) -> bool:
        """创建所有表"""
        try:
            logger.info("开始创建数据库表...")
            
            # 首先进行现有表的迁移
            await self.migrate_existing_tables()
            
            # 按依赖顺序创建表
            table_order = [
                "provinces", "regions", "merchants", "orders", "binding_codes",
                "activity_logs", "fsm_states", "system_config", "button_configs",
                "auto_reply_triggers", "auto_reply_messages", "auto_reply_daily_stats",
                "keywords", "merchant_keywords"
            ]
            
            created_count = 0
            for table_name in table_order:
                if table_name in self.schemas:
                    schema = self.schemas[table_name]
                    sql = schema.to_sql()
                    
                    if sql:
                        logger.debug(f"创建表 {table_name}: {sql}")
                        await db_manager.execute_query(sql)
                        
                        # 创建索引 - 添加存在性检查
                        await self._create_indexes_safely(table_name, schema.indexes)
                        
                        created_count += 1
                        logger.info(f"✅ 表 {table_name} 创建成功")
            
            # 创建迁移历史表
            migration_sql = """
            CREATE TABLE IF NOT EXISTS migration_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            await db_manager.execute_query(migration_sql)
            
            logger.info(f"数据库表创建完成，共创建 {created_count} 个表")
            return True
            
        except Exception as e:
            logger.error(f"创建数据库表失败: {e}")
            return False
    
    async def get_table_info(self, table_name: str) -> Optional[Dict]:
        """获取表信息"""
        try:
            result = await db_manager.fetch_all(f"PRAGMA table_info({table_name})")
            if result:
                return {
                    "columns": [{"name": row[1], "type": row[2], "nullable": not row[3]} for row in result]
                }
        except Exception as e:
            logger.debug(f"获取表 {table_name} 信息失败: {e}")
        return None

# 全局实例
auto_schema_manager = AutoSchemaManager()

async def auto_initialize_database() -> bool:
    """自动初始化数据库"""
    try:
        logger.info("🔄 使用自动架构管理器初始化数据库...")
        
        # 分析代码库
        await auto_schema_manager.analyze_codebase()
        
        # 创建表
        success = await auto_schema_manager.create_tables()
        
        if success:
            logger.info("✅ 自动数据库初始化成功")
        else:
            logger.error("❌ 自动数据库初始化失败")
        
        return success
        
    except Exception as e:
        logger.error(f"自动数据库初始化过程失败: {e}")
        return False
