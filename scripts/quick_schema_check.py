#!/usr/bin/env python3
"""
快速Schema检查脚本
用于本地开发时快速验证schema一致性，不执行完整的迁移检查
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def quick_check():
    """快速Schema检查"""
    print("🔍 快速Schema一致性检查")
    print("="*50)
    
    errors = []
    warnings = []
    info = []
    
    try:
        # 1. 检查版本一致性
        print("📋 检查版本...")
        
        from database.db_init import DatabaseInitializer
        from database.db_connection import db_manager
        
        # 获取期望版本
        initializer = DatabaseInitializer()
        expected_version = initializer.current_schema_version
        
        # 获取实际版本 - 直接使用db_manager，不需要初始化
        query = "SELECT config_value FROM system_config WHERE config_key = 'schema_version'"
        result = await db_manager.fetch_one(query)
        actual_version = result['config_value'] if result else 'unknown'
        
        print(f"  期望版本: {expected_version}")
        print(f"  实际版本: {actual_version}")
        
        if expected_version == actual_version:
            print("  ✅ 版本一致")
            info.append("版本匹配")
        else:
            print("  ❌ 版本不匹配")
            errors.append(f"版本不匹配: 期望 {expected_version}, 实际 {actual_version}")
        
        # 2. 快速表检查
        print("\n📋 检查核心表...")
        
        core_tables = [
            'merchants', 'orders', 'binding_codes', 
            'auto_reply_triggers', 'auto_reply_messages',
            'cities', 'districts', 'keywords', 
            'templates', 'system_config'
        ]
        
        for table in core_tables:
            table_query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            table_result = await db_manager.fetch_one(table_query)
            
            if table_result:
                print(f"  ✅ {table}")
                info.append(f"表存在: {table}")
            else:
                print(f"  ❌ {table}")
                errors.append(f"表不存在: {table}")
        
        # 3. 关键字段检查
        print("\n📋 检查关键字段...")
        
        critical_fields = [
            ('merchants', 'city_id'),
            ('merchants', 'district_id'), 
            ('merchants', 'merchant_type'),
            ('auto_reply_triggers', 'admin_id'),
            ('cities', 'code')
        ]
        
        for table, field in critical_fields:
            field_query = f"PRAGMA table_info({table})"
            fields_result = await db_manager.fetch_all(field_query)
            
            if fields_result:
                field_names = {f['name'] for f in fields_result}
                if field in field_names:
                    print(f"  ✅ {table}.{field}")
                    info.append(f"字段存在: {table}.{field}")
                else:
                    print(f"  ❌ {table}.{field}")
                    errors.append(f"字段缺失: {table}.{field}")
            else:
                print(f"  ❓ {table}.{field} (无法检查)")
                warnings.append(f"无法检查字段: {table}.{field}")
        
    except Exception as e:
        errors.append(f"检查过程异常: {e}")
        print(f"❌ 检查异常: {e}")
    
    # 输出结果
    print("\n" + "="*50)
    print("📊 检查结果")
    print("="*50)
    
    if info:
        print(f"\n✅ 成功 ({len(info)}):")
        for item in info:
            print(f"  • {item}")
    
    if warnings:
        print(f"\n⚠️  警告 ({len(warnings)}):")
        for item in warnings:
            print(f"  • {item}")
    
    if errors:
        print(f"\n❌ 错误 ({len(errors)}):")
        for item in errors:
            print(f"  • {item}")
    
    print("\n" + "="*50)
    
    if errors:
        print("❌ Schema检查失败!")
        print("\n🔧 建议操作:")
        print("  1. 运行完整迁移: python3 db_manager.py migrate")
        print("  2. 检查数据库文件权限")
        print("  3. 运行完整检查: python3 scripts/schema_migration_check.py")
        return False
    elif warnings:
        print("⚠️  Schema检查基本通过，但有警告")
        print("\n💡 建议查看完整报告: python3 scripts/schema_migration_check.py")
        return True
    else:
        print("✅ Schema检查完全通过!")
        print("\n🎉 数据库schema与代码完全一致")
        return True


if __name__ == "__main__":
    try:
        success = asyncio.run(quick_check())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ 检查被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 检查脚本异常: {e}")
        sys.exit(1)
