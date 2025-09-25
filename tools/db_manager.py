#!/usr/bin/env python3
"""
数据库管理脚本
提供数据库初始化、迁移、备份、统计等完整功能

使用方法:
python db_manager.py init          # 初始化数据库
python db_manager.py stats         # 显示数据库统计
python db_manager.py backup        # 备份数据库
python db_manager.py cleanup       # 清理过期数据
python db_manager.py migrate       # 执行数据库迁移
python db_manager.py health        # 健康检查
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入项目模块
try:
    from dotenv import load_dotenv
    from database.db_init import db_initializer
    from database.db_connection import db_manager
    
    # 加载环境变量
    load_dotenv('.env')
    
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print("请确保已安装所需依赖: pip install -r requirements.txt")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理工具类"""
    
    def __init__(self):
        """初始化数据库管理器"""
        self.db_path = getattr(db_manager, 'db_path', 'data/database.db')
        
    async def initialize_database(self) -> bool:
        """初始化数据库"""
        print("🗄️  开始数据库初始化...")
        try:
            success = await db_initializer.initialize_database()
            
            if success:
                print("✅ 数据库初始化成功")
                
                # 显示统计信息
                await self.show_statistics()
                return True
            else:
                print("❌ 数据库初始化失败")
                return False
                
        except Exception as e:
            logger.error(f"数据库初始化异常: {e}")
            print(f"❌ 数据库初始化异常: {e}")
            return False
    
    async def show_statistics(self):
        """显示数据库统计信息"""
        print("📊 数据库统计信息:")
        print("-" * 50)
        
        try:
            stats = await db_initializer.get_database_stats()
            
            if not stats:
                print("   无统计数据")
                return
            
            # 按类别分组显示
            categories = {
                "核心业务表": ["merchants", "orders", "binding_codes"],
                "配置管理表": ["button_configs", "system_config"],
                "日志监控表": ["activity_logs", "fsm_states"],
                "自动回复表": ["auto_reply_triggers", "auto_reply_messages", "auto_reply_daily_stats"]
            }
            
            total_records = 0
            for category, tables in categories.items():
                print(f"\n📋 {category}:")
                category_total = 0
                for table in tables:
                    count = stats.get(table, 0)
                    total_records += count
                    category_total += count
                    status = "📈" if count > 0 else "📭"
                    print(f"   {status} {table}: {count:,} 条记录")
                print(f"   小计: {category_total:,} 条记录")
            
            print(f"\n🎯 总计: {total_records:,} 条记录")
            
            # 显示数据库文件信息
            if os.path.exists(self.db_path):
                file_size = os.path.getsize(self.db_path)
                size_mb = file_size / (1024 * 1024)
                print(f"💾 数据库文件大小: {size_mb:.2f} MB")
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            print(f"❌ 获取统计信息失败: {e}")
    
    async def backup_database(self, backup_path: str = None):
        """备份数据库"""
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backups/database_backup_{timestamp}.db"
        
        print(f"💾 开始备份数据库到: {backup_path}")
        
        try:
            success = await db_initializer.backup_database(backup_path)
            
            if success:
                print("✅ 数据库备份成功")
                
                # 显示备份文件信息
                if os.path.exists(backup_path):
                    file_size = os.path.getsize(backup_path)
                    size_mb = file_size / (1024 * 1024)
                    print(f"   备份文件: {backup_path}")
                    print(f"   文件大小: {size_mb:.2f} MB")
                
                return True
            else:
                print("❌ 数据库备份失败")
                return False
                
        except Exception as e:
            logger.error(f"数据库备份异常: {e}")
            print(f"❌ 数据库备份异常: {e}")
            return False
    
    async def cleanup_expired_data(self):
        """清理过期数据"""
        print("🧹 开始清理过期数据...")
        
        try:
            await db_initializer.cleanup_expired_data()
            print("✅ 过期数据清理完成")
            
            # 显示清理后的统计
            print("\n清理后的数据库状态:")
            await self.show_statistics()
            
        except Exception as e:
            logger.error(f"数据清理异常: {e}")
            print(f"❌ 数据清理异常: {e}")
    
    async def health_check(self):
        """数据库健康检查"""
        print("🏥 数据库健康检查")
        print("-" * 50)
        
        checks = []
        
        # 检查数据库文件是否存在
        if os.path.exists(self.db_path):
            print("✅ 数据库文件存在")
            checks.append(True)
        else:
            print("❌ 数据库文件不存在")
            checks.append(False)
        
        # 检查数据库连接
        try:
            result = await db_manager.fetch_one("SELECT 1")
            if result:
                print("✅ 数据库连接正常")
                checks.append(True)
            else:
                print("❌ 数据库连接异常")
                checks.append(False)
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            checks.append(False)
        
        # 检查核心表是否存在
        core_tables = ['merchants', 'orders', 'binding_codes', 'activity_logs']
        table_checks = []
        
        for table in core_tables:
            try:
                result = await db_manager.fetch_one(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                )
                if result:
                    print(f"✅ 表 {table} 存在")
                    table_checks.append(True)
                else:
                    print(f"❌ 表 {table} 不存在")
                    table_checks.append(False)
            except Exception as e:
                print(f"❌ 检查表 {table} 失败: {e}")
                table_checks.append(False)
        
        checks.extend(table_checks)
        
        # 检查架构版本
        try:
            version = await db_initializer.get_schema_version()
            if version:
                print(f"✅ 架构版本: {version}")
                checks.append(True)
            else:
                print("⚠️  未找到架构版本信息")
                checks.append(False)
        except Exception as e:
            print(f"❌ 获取架构版本失败: {e}")
            checks.append(False)
        
        # 总结
        passed = sum(checks)
        total = len(checks)
        print(f"\n📊 健康检查结果: {passed}/{total} 项通过")
        
        if passed == total:
            print("🎉 数据库状态良好")
            return True
        elif passed > total * 0.7:
            print("⚠️  数据库状态一般，建议检查")
            return False
        else:
            print("❌ 数据库状态异常，需要修复")
            return False
    
    async def migrate_database(self):
        """执行数据库迁移"""
        print("🔄 检查数据库迁移...")
        
        try:
            current_version = await db_initializer.get_schema_version()
            print(f"当前架构版本: {current_version or '未知'}")
            
            # 这里可以添加具体的迁移逻辑
            # 目前只是重新初始化数据库以确保最新结构
            
            success = await db_initializer.initialize_database()
            
            if success:
                new_version = await db_initializer.get_schema_version()
                print(f"迁移后版本: {new_version}")
                print("✅ 数据库迁移完成")
                return True
            else:
                print("❌ 数据库迁移失败")
                return False
                
        except Exception as e:
            logger.error(f"数据库迁移异常: {e}")
            print(f"❌ 数据库迁移异常: {e}")
            return False
    
    async def generate_migration(self, description: str = None):
        """生成迁移文件"""
        if not description:
            description = input("请输入迁移描述: ").strip()
            if not description:
                print("❌ 迁移描述不能为空")
                return False
        
        print(f"📝 生成迁移文件: {description}")
        
        try:
            file_path = db_initializer.generate_migration_file(description)
            print(f"✅ 迁移文件已生成: {file_path}")
            
            # 提示下一步操作
            print("\n📋 下一步操作:")
            print("1. 编辑生成的迁移文件，添加具体的SQL语句")
            print("2. 运行 'python db_manager.py migrate' 测试迁移")
            print("3. 更新代码中的版本号（如果需要）")
            
            return True
            
        except Exception as e:
            logger.error(f"生成迁移文件异常: {e}")
            print(f"❌ 生成迁移文件异常: {e}")
            return False

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Telegram商户机器人数据库管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python db_manager.py init                              # 初始化数据库
  python db_manager.py stats                             # 显示统计信息
  python db_manager.py backup                            # 备份数据库
  python db_manager.py cleanup                           # 清理过期数据
  python db_manager.py migrate                           # 执行迁移
  python db_manager.py health                            # 健康检查
  python db_manager.py generate-migration --description "添加新表"  # 生成迁移文件
        """
    )
    
    parser.add_argument(
        'command',
        choices=['init', 'stats', 'backup', 'cleanup', 'migrate', 'health', 'generate-migration'],
        help='要执行的命令'
    )
    
    parser.add_argument(
        '--backup-path',
        type=str,
        help='备份文件路径（仅用于backup命令）'
    )
    
    parser.add_argument(
        '--description',
        type=str,
        help='迁移描述（用于generate-migration命令）'
    )
    
    args = parser.parse_args()
    
    # 创建数据库管理器实例
    db_mgr = DatabaseManager()
    
    print("🚀 Telegram商户机器人 - 数据库管理工具")
    print("=" * 60)
    
    try:
        if args.command == 'init':
            success = await db_mgr.initialize_database()
            
        elif args.command == 'stats':
            await db_mgr.show_statistics()
            success = True
            
        elif args.command == 'backup':
            success = await db_mgr.backup_database(args.backup_path)
            
        elif args.command == 'cleanup':
            await db_mgr.cleanup_expired_data()
            success = True
            
        elif args.command == 'migrate':
            success = await db_mgr.migrate_database()
            
        elif args.command == 'health':
            success = await db_mgr.health_check()
            
        elif args.command == 'generate-migration':
            success = await db_mgr.generate_migration(args.description)
            
        else:
            print(f"❌ 未知命令: {args.command}")
            success = False
        
        print("=" * 60)
        if success:
            print("🎉 操作完成")
            return 0
        else:
            print("❌ 操作失败")
            return 1
            
    except KeyboardInterrupt:
        print("\n👋 操作被用户中断")
        return 0
        
    except Exception as e:
        logger.error(f"程序执行异常: {e}")
        print(f"❌ 程序执行异常: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)