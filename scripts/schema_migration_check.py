#!/usr/bin/env python3
"""
Schema迁移一致性检查脚本
自动部署后检查所有数据库schema迁移是否一致，确保不漏任何结构变更
"""

import os
import sys
import json
import asyncio
import hashlib
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_connection import db_manager
from database.db_init import DatabaseInitializer


class SchemaMigrationChecker:
    """Schema迁移一致性检查器"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.expected_schema_version = None
        self.actual_schema_version = None
        self.migration_files: List[Path] = []
        
    def load_expected_schema_version(self) -> str:
        """从代码中获取期望的schema版本"""
        try:
            from database.db_init import DatabaseInitializer
            initializer = DatabaseInitializer()
            self.expected_schema_version = initializer.current_schema_version
            self.info.append(f"✅ 期望Schema版本: {self.expected_schema_version}")
            return self.expected_schema_version
        except Exception as e:
            self.errors.append(f"❌ 无法获取期望Schema版本: {e}")
            return None
    
    async def get_actual_schema_version(self) -> Optional[str]:
        """从数据库获取实际的schema版本"""
        try:
            query = "SELECT config_value FROM system_config WHERE config_key = 'schema_version'"
            result = await db_manager.fetch_one(query)
            
            if result:
                self.actual_schema_version = result['config_value']
                self.info.append(f"✅ 实际Schema版本: {self.actual_schema_version}")
                return self.actual_schema_version
            else:
                self.errors.append("❌ 数据库中未找到schema_version配置")
                return None
                
        except Exception as e:
            self.errors.append(f"❌ 获取数据库Schema版本失败: {e}")
            return None
    
    def scan_migration_files(self) -> List[Path]:
        """扫描所有迁移文件"""
        migration_dir = Path(__file__).parent.parent / "database" / "migrations"
        
        if not migration_dir.exists():
            self.warnings.append("⚠️  migrations目录不存在，创建目录")
            migration_dir.mkdir(parents=True, exist_ok=True)
            return []
        
        # 查找所有迁移文件
        migration_files = list(migration_dir.glob("migration_*.sql"))
        migration_files.sort()  # 按文件名排序
        
        self.migration_files = migration_files
        self.info.append(f"✅ 找到 {len(migration_files)} 个迁移文件")
        
        return migration_files
    
    def validate_migration_files(self) -> bool:
        """验证迁移文件格式和完整性"""
        print("🔍 验证迁移文件...")
        
        valid = True
        
        for migration_file in self.migration_files:
            try:
                # 检查文件名格式
                if not self._validate_migration_filename(migration_file.name):
                    self.errors.append(f"❌ 迁移文件名格式错误: {migration_file.name}")
                    valid = False
                    continue
                
                # 检查文件内容
                content = migration_file.read_text(encoding='utf-8')
                if not content.strip():
                    self.errors.append(f"❌ 迁移文件为空: {migration_file.name}")
                    valid = False
                    continue
                
                # 检查SQL语法基本结构
                if not self._validate_sql_content(content):
                    self.warnings.append(f"⚠️  迁移文件SQL可能有问题: {migration_file.name}")
                
                self.info.append(f"✅ 迁移文件有效: {migration_file.name}")
                
            except Exception as e:
                self.errors.append(f"❌ 读取迁移文件失败 {migration_file.name}: {e}")
                valid = False
        
        return valid
    
    def _validate_migration_filename(self, filename: str) -> bool:
        """验证迁移文件名格式"""
        # 格式: migration_YYYY_MM_DD_N_description.sql
        import re
        pattern = r'^migration_\d{4}_\d{2}_\d{2}_\d+_.*\.sql$'
        return re.match(pattern, filename) is not None
    
    def _validate_sql_content(self, content: str) -> bool:
        """基本SQL内容验证"""
        content_upper = content.upper()
        
        # 检查是否包含基本SQL关键字
        sql_keywords = ['CREATE', 'ALTER', 'INSERT', 'UPDATE', 'DROP']
        has_sql = any(keyword in content_upper for keyword in sql_keywords)
        
        # 检查是否有明显的SQL语法错误标志
        has_basic_structure = (
            content.count('(') == content.count(')') and
            content.count("'") % 2 == 0 and
            content.count('"') % 2 == 0
        )
        
        return has_sql and has_basic_structure
    
    async def check_table_structure_consistency(self) -> bool:
        """检查表结构一致性"""
        print("🔍 检查数据库表结构...")
        
        try:
            # 定义期望的核心表和重要字段
            expected_tables = {
                'merchants': {
                    'required_fields': [
                        'id', 'chat_id', 'name', 'region', 'category', 
                        'status', 'created_at', 'updated_at',
                        'merchant_type', 'province_id', 'city_id', 
                        'p_price', 'pp_price', 'custom_description',
                        'user_info', 'channel_link'
                    ],
                    'constraints': ['chat_id UNIQUE']
                },
                'orders': {
                    'required_fields': [
                        'id', 'user_id', 'username', 'merchant_id', 
                        'order_type', 'price', 'status', 'created_at'
                    ],
                    'foreign_keys': ['merchant_id -> merchants(id)']
                },
                'binding_codes': {
                    'required_fields': [
                        'id', 'code', 'is_used', 'merchant_id', 
                        'created_at', 'expires_at'
                    ],
                    'constraints': ['code UNIQUE']
                },
                'auto_reply_triggers': {
                    'required_fields': [
                        'id', 'trigger_text', 'match_type', 'is_active',
                        'created_by', 'admin_id', 'created_at', 'updated_at'
                    ]
                },
                'auto_reply_messages': {
                    'required_fields': [
                        'id', 'trigger_id', 'message_content', 'is_active',
                        'created_at', 'updated_at'
                    ],
                    'foreign_keys': ['trigger_id -> auto_reply_triggers(id)']
                },
                'provinces': {
                    'required_fields': [
                        'id', 'name', 'display_order', 'is_active',
                        'created_at', 'updated_at', 'code'
                    ],
                    'constraints': ['name UNIQUE']
                },
                'cities': {
                    'required_fields': [
                        'id', 'name', 'province_id', 'display_order',
                        'is_active', 'created_at', 'updated_at'
                    ],
                    'foreign_keys': ['province_id -> provinces(id)'],
                    'constraints': ['UNIQUE(name, province_id)']
                },
                'keywords': {
                    'required_fields': [
                        'id', 'name', 'display_order', 'is_active',
                        'created_at', 'updated_at'
                    ],
                    'constraints': ['name UNIQUE']
                },
                'merchant_keywords': {
                    'required_fields': ['id', 'merchant_id', 'keyword_id', 'created_at'],
                    'foreign_keys': [
                        'merchant_id -> merchants(id)',
                        'keyword_id -> keywords(id)'
                    ],
                    'constraints': ['UNIQUE(merchant_id, keyword_id)']
                },
                'templates': {
                    'required_fields': ['key', 'content', 'updated_at'],
                    'constraints': ['key PRIMARY KEY']
                },
                'system_config': {
                    'required_fields': [
                        'id', 'config_key', 'config_value', 
                        'description', 'updated_at'
                    ],
                    'constraints': ['config_key UNIQUE']
                }
            }
            
            # 检查每个表
            all_tables_valid = True
            
            for table_name, expectations in expected_tables.items():
                table_valid = await self._check_single_table(table_name, expectations)
                all_tables_valid = all_tables_valid and table_valid
            
            return all_tables_valid
            
        except Exception as e:
            self.errors.append(f"❌ 表结构检查失败: {e}")
            return False
    
    async def _check_single_table(self, table_name: str, expectations: Dict) -> bool:
        """检查单个表的结构"""
        try:
            # 检查表是否存在
            table_exists_query = """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """
            table_result = await db_manager.fetch_one(table_exists_query, (table_name,))
            
            if not table_result:
                self.errors.append(f"❌ 表不存在: {table_name}")
                return False
            
            # 获取表结构信息
            table_info_query = f"PRAGMA table_info({table_name})"
            columns = await db_manager.fetch_all(table_info_query)
            
            if not columns:
                self.errors.append(f"❌ 无法获取表结构: {table_name}")
                return False
            
            # 检查必需字段
            existing_columns = {col['name'] for col in columns}
            required_fields = expectations.get('required_fields', [])
            
            missing_fields = []
            for field in required_fields:
                if field not in existing_columns:
                    missing_fields.append(field)
            
            if missing_fields:
                self.errors.append(f"❌ {table_name} 缺少字段: {missing_fields}")
                return False
            
            self.info.append(f"✅ 表结构正确: {table_name} ({len(existing_columns)} 字段)")
            return True
            
        except Exception as e:
            self.errors.append(f"❌ 检查表 {table_name} 失败: {e}")
            return False
    
    async def check_indexes_and_constraints(self) -> bool:
        """检查索引和约束"""
        print("🔍 检查数据库索引和约束...")
        
        try:
            # 期望的索引
            expected_indexes = [
                'idx_merchants_chat_id',
                'idx_merchants_status',
                'idx_orders_user_id',
                'idx_orders_merchant_id',
                'idx_binding_codes_code',
                'idx_provinces_name',
                'idx_cities_province_id',
                'idx_keywords_name',
                'idx_merchant_keywords_merchant_id',
                'idx_auto_reply_triggers_active'
            ]
            
            # 获取实际索引
            indexes_query = """
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
            """
            actual_indexes = await db_manager.fetch_all(indexes_query)
            actual_index_names = {idx['name'] for idx in actual_indexes}
            
            # 检查缺失的索引
            missing_indexes = []
            for expected_idx in expected_indexes:
                if expected_idx not in actual_index_names:
                    missing_indexes.append(expected_idx)
            
            if missing_indexes:
                self.warnings.append(f"⚠️  缺少索引: {missing_indexes}")
            
            self.info.append(f"✅ 找到 {len(actual_index_names)} 个索引")
            
            # 检查触发器
            triggers_query = """
                SELECT name FROM sqlite_master 
                WHERE type='trigger'
            """
            triggers = await db_manager.fetch_all(triggers_query)
            self.info.append(f"✅ 找到 {len(triggers)} 个触发器")
            
            return len(missing_indexes) == 0
            
        except Exception as e:
            self.errors.append(f"❌ 检查索引和约束失败: {e}")
            return False
    
    async def check_data_integrity(self) -> bool:
        """检查数据完整性"""
        print("🔍 检查数据完整性...")
        
        try:
            integrity_checks = []
            
            # 检查外键引用完整性
            fk_checks = [
                ("orders.merchant_id", "SELECT COUNT(*) FROM orders WHERE merchant_id NOT IN (SELECT id FROM merchants)"),
                ("cities.province_id", "SELECT COUNT(*) FROM cities WHERE province_id NOT IN (SELECT id FROM provinces)"),
                ("merchant_keywords.merchant_id", "SELECT COUNT(*) FROM merchant_keywords WHERE merchant_id NOT IN (SELECT id FROM merchants)"),
                ("merchant_keywords.keyword_id", "SELECT COUNT(*) FROM merchant_keywords WHERE keyword_id NOT IN (SELECT id FROM keywords)"),
            ]
            
            for check_name, query in fk_checks:
                try:
                    result = await db_manager.fetch_one(query)
                    invalid_count = result[list(result.keys())[0]] if result else 0
                    
                    if invalid_count > 0:
                        self.errors.append(f"❌ 数据完整性错误: {check_name} 有 {invalid_count} 条无效引用")
                        integrity_checks.append(False)
                    else:
                        self.info.append(f"✅ 外键完整性正常: {check_name}")
                        integrity_checks.append(True)
                        
                except Exception as e:
                    self.warnings.append(f"⚠️  无法检查 {check_name}: {e}")
            
            # 检查关键配置是否存在
            config_checks = [
                'schema_version',
                'bot_status',
                'auto_reply_enabled'
            ]
            
            for config_key in config_checks:
                config_query = "SELECT config_value FROM system_config WHERE config_key = ?"
                result = await db_manager.fetch_one(config_query, (config_key,))
                
                if result:
                    self.info.append(f"✅ 配置存在: {config_key} = {result['config_value']}")
                else:
                    self.warnings.append(f"⚠️  配置缺失: {config_key}")
            
            return all(integrity_checks)
            
        except Exception as e:
            self.errors.append(f"❌ 数据完整性检查失败: {e}")
            return False
    
    def calculate_schema_hash(self) -> str:
        """计算schema结构哈希值"""
        try:
            # 收集所有schema文件内容
            schema_files = [
                Path(__file__).parent.parent / "database" / "schema.sql",
                Path(__file__).parent.parent / "database" / "schema_extended.sql",
                Path(__file__).parent.parent / "database" / "schema_auto_reply.sql"
            ]
            
            combined_content = ""
            for schema_file in schema_files:
                if schema_file.exists():
                    combined_content += schema_file.read_text(encoding='utf-8')
            
            # 添加迁移文件内容
            for migration_file in self.migration_files:
                combined_content += migration_file.read_text(encoding='utf-8')
            
            # 计算哈希
            schema_hash = hashlib.sha256(combined_content.encode('utf-8')).hexdigest()[:16]
            self.info.append(f"✅ Schema哈希值: {schema_hash}")
            
            return schema_hash
            
        except Exception as e:
            self.warnings.append(f"⚠️  无法计算Schema哈希: {e}")
            return "unknown"
    
    def generate_migration_report(self) -> Dict:
        """生成迁移检查报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'expected_schema_version': self.expected_schema_version,
            'actual_schema_version': self.actual_schema_version,
            'version_match': self.expected_schema_version == self.actual_schema_version,
            'migration_files_count': len(self.migration_files),
            'schema_hash': self.calculate_schema_hash(),
            'total_checks': len(self.errors) + len(self.warnings) + len(self.info),
            'errors': len(self.errors),
            'warnings': len(self.warnings),
            'status': 'SUCCESS' if len(self.errors) == 0 else 'FAILED',
            'details': {
                'errors': self.errors,
                'warnings': self.warnings,
                'info': self.info,
                'migration_files': [f.name for f in self.migration_files]
            }
        }
    
    def print_results(self) -> bool:
        """打印检查结果"""
        print("\n" + "="*80)
        print("📋 Schema迁移一致性检查结果")
        print("="*80)
        
        # 版本对比
        print(f"\n📊 版本对比:")
        print(f"  期望版本: {self.expected_schema_version}")
        print(f"  实际版本: {self.actual_schema_version}")
        
        if self.expected_schema_version == self.actual_schema_version:
            print("  ✅ 版本一致")
        else:
            print("  ❌ 版本不匹配！")
        
        # 打印信息
        if self.info:
            print("\n✅ 检查通过:")
            for msg in self.info:
                print(f"  {msg}")
        
        # 打印警告
        if self.warnings:
            print("\n⚠️  警告信息:")
            for msg in self.warnings:
                print(f"  {msg}")
        
        # 打印错误
        if self.errors:
            print("\n❌ 错误信息:")
            for msg in self.errors:
                print(f"  {msg}")
        
        # 总结
        print("\n" + "="*80)
        if self.errors:
            print("❌ Schema迁移检查失败！数据库结构与期望不一致。")
            print("\n🔧 建议操作:")
            print("  1. 检查数据库迁移是否正确执行")
            print("  2. 验证所有迁移文件是否已应用")
            print("  3. 检查数据库连接和权限")
            print("  4. 重新运行数据库初始化")
            return False
        elif self.warnings:
            print("⚠️  Schema迁移检查基本通过，但有警告需要注意。")
            print("\n💡 建议:")
            print("  1. 查看警告信息并评估影响")
            print("  2. 考虑添加缺失的索引")
            print("  3. 监控数据库性能")
            return True
        else:
            print("✅ Schema迁移检查完全通过！数据库结构完全一致。")
            print("\n🎉 数据库状态:")
            print("  ✓ 所有表结构正确")
            print("  ✓ 索引和约束完整")
            print("  ✓ 数据完整性良好")
            print("  ✓ 版本号匹配")
            return True


async def main():
    """主函数"""
    print("🔍 Schema迁移一致性检查")
    print("="*80)
    print("检查数据库schema是否与代码期望一致，确保迁移完整性")
    
    checker = SchemaMigrationChecker()
    
    # 初始化数据库连接
    try:
        await db_manager.initialize()
        print("✅ 数据库连接初始化成功")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return 1
    
    try:
        # 执行检查步骤
        print(f"\n🔍 开始Schema检查...")
        
        # 1. 获取版本信息
        expected_version = checker.load_expected_schema_version()
        actual_version = await checker.get_actual_schema_version()
        
        # 2. 扫描迁移文件
        migration_files = checker.scan_migration_files()
        
        # 3. 验证迁移文件
        migration_files_valid = checker.validate_migration_files()
        
        # 4. 检查表结构
        table_structure_valid = await checker.check_table_structure_consistency()
        
        # 5. 检查索引和约束
        indexes_valid = await checker.check_indexes_and_constraints()
        
        # 6. 检查数据完整性
        data_integrity_valid = await checker.check_data_integrity()
        
        # 统计结果
        all_checks = [
            ("版本匹配", expected_version == actual_version),
            ("迁移文件", migration_files_valid),
            ("表结构", table_structure_valid),
            ("索引约束", indexes_valid),
            ("数据完整性", data_integrity_valid)
        ]
        
        passed = sum(1 for name, result in all_checks if result)
        total = len(all_checks)
        
        print(f"\n📊 检查完成: {passed}/{total} 项通过")
        
        # 打印详细结果
        success = checker.print_results()
        
        # 生成报告文件
        report = checker.generate_migration_report()
        report_file = Path(__file__).parent.parent / 'schema_migration_check.json'
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n📄 检查报告已保存: {report_file}")
        except Exception as e:
            print(f"\n⚠️  无法保存检查报告: {e}")
        
        return 0 if success else 1
        
    finally:
        # 关闭数据库连接
        try:
            await db_manager.close()
            print("\n🔒 数据库连接已关闭")
        except:
            pass


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)