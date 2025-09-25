#!/usr/bin/env python3
"""
云端数据库Schema修复脚本
专门用于修复cloud数据库中缺失的admin_id字段问题
"""

import os
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db_connection import db_manager


async def fix_cloud_schema():
    """修复云端数据库schema问题"""
    print("🔧 云端数据库Schema修复工具")
    print("="*50)
    
    try:
        # 1. 检查当前表结构
        print("📋 检查当前auto_reply_triggers表结构...")
        
        table_info = await db_manager.fetch_all("PRAGMA table_info(auto_reply_triggers)")
        current_columns = {col['name'] for col in table_info}
        
        print(f"  当前字段: {', '.join(current_columns)}")
        
        # 2. 检查是否缺少admin_id字段
        if 'admin_id' in current_columns:
            print("  ✅ admin_id字段已存在")
            return True
        
        print("  ❌ 缺少admin_id字段，开始修复...")
        
        # 3. 添加admin_id字段
        alter_query = """
            ALTER TABLE auto_reply_triggers 
            ADD COLUMN admin_id INTEGER NOT NULL DEFAULT 0
        """
        
        await db_manager.execute_query(alter_query)
        print("  ✅ admin_id字段添加成功")
        
        # 4. 验证修复结果
        table_info_after = await db_manager.fetch_all("PRAGMA table_info(auto_reply_triggers)")
        columns_after = {col['name'] for col in table_info_after}
        
        if 'admin_id' in columns_after:
            print("  ✅ 字段添加验证成功")
        else:
            print("  ❌ 字段添加验证失败")
            return False
        
        # 5. 更新schema版本
        version_update = """
            UPDATE system_config 
            SET config_value = '2025.08.30.7' 
            WHERE config_key = 'schema_version'
        """
        
        await db_manager.execute_query(version_update)
        print("  ✅ Schema版本已更新")
        
        print("\n🎉 云端数据库Schema修复完成！")
        return True
        
    except Exception as e:
        print(f"\n❌ 修复失败: {e}")
        return False


async def main():
    """主函数"""
    print("🚀 开始云端数据库Schema修复")
    
    try:
        success = await fix_cloud_schema()
        
        if success:
            print("\n✅ 修复成功！现在可以正常使用自动回复功能")
            print("\n🔍 建议接下来:")
            print("  1. 重新访问自动回复页面测试")
            print("  2. 运行schema检查验证: python3 scripts/quick_schema_check.py")
        else:
            print("\n❌ 修复失败！")
            print("\n🔧 替代方案:")
            print("  1. 删除Railway Volume重新创建")
            print("  2. 重新部署让系统自动初始化")
            
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n💥 修复过程异常: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)