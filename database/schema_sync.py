"""
精简的动态数据库Schema同步系统
"""

import logging
import os
import re
from .db_connection import db_manager

logger = logging.getLogger(__name__)

class SchemaSynchronizer:
    """精简的Schema同步器"""
    
    def __init__(self):
        self.schema_files = [
            'database/schema.sql',
            'database/schema_extended.sql', 
            'database/schema_auto_reply.sql'
        ]
    
    async def get_expected_columns(self) -> dict:
        """从所有schema文件中提取期望的表列结构"""
        expected = {}
        
        for schema_file in self.schema_files:
            path = os.path.join(os.getcwd(), schema_file)
            if not os.path.exists(path):
                continue
                
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 ALTER TABLE ADD COLUMN 语句
            # 支持有分号和无分号的两种格式
            alter_pattern = r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+(\w+)\s+([^;\n]+)(?:;|\n|$)'
            for match in re.finditer(alter_pattern, content, re.IGNORECASE | re.MULTILINE):
                table_name = match.group(1)
                column_name = match.group(2)
                column_def = match.group(3).strip()
                
                if table_name not in expected:
                    expected[table_name] = {}
                expected[table_name][column_name] = column_def
        
        return expected
    
    async def get_actual_columns(self) -> dict:
        """获取实际数据库中的表列结构"""
        actual = {}
        
        # 获取所有表名
        tables = await db_manager.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        
        for table_row in tables:
            table_name = table_row['name']
            
            # 获取表的列信息
            columns = await db_manager.fetch_all(f"PRAGMA table_info({table_name})")
            
            actual[table_name] = set(col['name'] for col in columns)
        
        return actual
    
    async def synchronize_schema(self) -> bool:
        """执行Schema同步"""
        try:
            logger.info("🔍 检查数据库Schema差异...")
            
            expected = await self.get_expected_columns()
            actual = await self.get_actual_columns()
            
            if not expected:
                logger.info("✅ 无需同步的Schema差异")
                return True
            
            success_count = 0
            skip_count = 0
            
            # 检查每个期望的表和列
            for table_name, columns in expected.items():
                if table_name not in actual:
                    logger.warning(f"表 {table_name} 不存在，跳过")
                    continue
                
                actual_columns = actual[table_name]
                
                for column_name, column_def in columns.items():
                    if column_name not in actual_columns:
                        # 需要添加此列
                        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
                        
                        try:
                            await db_manager.execute_query(alter_sql)
                            logger.info(f"✅ 添加列: {table_name}.{column_name}")
                            success_count += 1
                        except Exception as e:
                            if 'duplicate column name' in str(e).lower():
                                logger.info(f"⚠️ 列已存在: {table_name}.{column_name}")
                                skip_count += 1
                            else:
                                logger.error(f"❌ 添加列失败: {table_name}.{column_name} - {e}")
                                return False
                    else:
                        skip_count += 1
            
            logger.info(f"🎉 Schema同步完成: 新增={success_count}, 跳过={skip_count}")
            return True
            
        except Exception as e:
            logger.error(f"Schema同步失败: {e}")
            return False

# 全局实例
schema_sync = SchemaSynchronizer()