#!/usr/bin/env python3
"""
Railway部署辅助脚本
检查配置、验证环境变量、执行部署前检查
"""

import os
import sys
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import bot_config, ADMIN_IDS, MESSAGE_TEMPLATES, BUTTON_TEMPLATES


class DeploymentChecker:
    """部署检查器 - 增强版，包含Schema迁移检查"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.schema_check_enabled = True
    
    def check_environment_variables(self) -> bool:
        """检查环境变量配置"""
        print("🔍 检查环境变量配置...")
        
        # 必需的环境变量
        required_vars = {
            'BOT_TOKEN': 'Telegram机器人Token',
            'ADMIN_IDS': '管理员用户ID列表',
            'WEB_ADMIN_PASSWORD': 'Web管理面板密码'
        }
        
        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value or value in ['YOUR_BOT_TOKEN_HERE', 'your_password_here']:
                self.errors.append(f"❌ {var} 未设置或使用默认值 ({description})")
            else:
                self.info.append(f"✅ {var} 已设置")
        
        # 检查BOT_TOKEN格式
        bot_token = os.getenv('BOT_TOKEN', '')
        if bot_token and not bot_token.count(':') == 1:
            self.errors.append(f"❌ BOT_TOKEN 格式错误，应为: 123456789:ABC...")
        
        # 检查ADMIN_IDS格式
        admin_ids = os.getenv('ADMIN_IDS', '')
        if admin_ids:
            try:
                ids = [int(id.strip()) for id in admin_ids.split(',')]
                if any(id <= 0 for id in ids):
                    self.errors.append("❌ ADMIN_IDS 包含无效的用户ID")
                else:
                    self.info.append(f"✅ 检测到 {len(ids)} 个管理员ID")
            except ValueError:
                self.errors.append("❌ ADMIN_IDS 格式错误，应为逗号分隔的数字")
        
        # 可选但推荐的环境变量
        optional_vars = {
            'WEBHOOK_URL': 'Webhook URL',
            'LOG_LEVEL': '日志级别',
            'RATE_LIMIT_DEFAULT': '默认限流速率',
            'DATABASE_URL': '数据库连接URL'
        }
        
        for var, description in optional_vars.items():
            value = os.getenv(var)
            if value:
                self.info.append(f"✅ {var} 已设置: {description}")
            else:
                self.warnings.append(f"⚠️  {var} 未设置 ({description})")
        
        return len(self.errors) == 0
    
    def check_config_integrity(self) -> bool:
        """检查配置完整性"""
        print("🔍 检查配置完整性...")
        
        try:
            # 检查机器人配置
            if hasattr(bot_config, 'token') and bot_config.token:
                self.info.append("✅ 机器人配置已加载")
            else:
                self.errors.append("❌ 机器人配置加载失败")
            
            # 检查管理员ID
            if ADMIN_IDS and len(ADMIN_IDS) > 0:
                self.info.append(f"✅ 管理员配置已加载 ({len(ADMIN_IDS)}个)")
            else:
                self.errors.append("❌ 管理员ID配置为空")
            
            # 检查消息模板
            if MESSAGE_TEMPLATES and len(MESSAGE_TEMPLATES) > 0:
                self.info.append(f"✅ 消息模板已加载 ({len(MESSAGE_TEMPLATES)}个)")
            else:
                self.warnings.append("⚠️  消息模板为空")
            
            # 检查按钮模板
            if BUTTON_TEMPLATES and len(BUTTON_TEMPLATES) > 0:
                self.info.append(f"✅ 按钮模板已加载 ({len(BUTTON_TEMPLATES)}个)")
            else:
                self.warnings.append("⚠️  按钮模板为空")
            
        except Exception as e:
            self.errors.append(f"❌ 配置加载异常: {str(e)}")
        
        return len(self.errors) == 0
    
    async def check_bot_token_validity(self) -> bool:
        """验证机器人Token有效性"""
        print("🔍 验证机器人Token...")
        
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            self.errors.append("❌ BOT_TOKEN 未设置，跳过验证")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok'):
                            bot_info = data.get('result', {})
                            username = bot_info.get('username', 'Unknown')
                            self.info.append(f"✅ 机器人Token有效: @{username}")
                            return True
                        else:
                            self.errors.append(f"❌ 机器人Token验证失败: {data.get('description')}")
                    else:
                        self.errors.append(f"❌ 机器人API请求失败: HTTP {response.status}")
        
        except asyncio.TimeoutError:
            self.errors.append("❌ 机器人Token验证超时")
        except Exception as e:
            self.errors.append(f"❌ 机器人Token验证异常: {str(e)}")
        
        return False
    
    def check_file_structure(self) -> bool:
        """检查项目文件结构"""
        print("🔍 检查项目文件结构...")
        
        required_files = [
            'main.py',
            'bot.py', 
            'config.py',
            'requirements.txt',
            'railway.toml'
        ]
        
        required_dirs = [
            'database',
            'handlers',
            'middleware',
            'states',
            'dialogs',
            'utils',
            'web',
            'scripts'  # 添加scripts目录检查
        ]
        
        # Schema文件检查
        schema_files = [
            'database/schema.sql',
            'database/schema_extended.sql', 
            'database/schema_auto_reply.sql'
        ]
        
        project_root = Path(__file__).parent.parent
        
        # 检查文件
        for file_path in required_files:
            if (project_root / file_path).exists():
                self.info.append(f"✅ {file_path} 存在")
            else:
                self.errors.append(f"❌ {file_path} 缺失")
        
        # 检查目录
        for dir_path in required_dirs:
            if (project_root / dir_path).exists():
                self.info.append(f"✅ {dir_path}/ 目录存在")
            else:
                self.errors.append(f"❌ {dir_path}/ 目录缺失")
        
        # 检查Schema文件
        for schema_path in schema_files:
            if (project_root / schema_path).exists():
                self.info.append(f"✅ {schema_path} 存在")
            else:
                self.warnings.append(f"⚠️  {schema_path} 缺失")
        
        # 检查脚本文件
        script_files = [
            'scripts/schema_migration_check.py',
            'scripts/post_deploy_hook.py',
            'scripts/quick_schema_check.py'
        ]
        
        for script_path in script_files:
            if (project_root / script_path).exists():
                self.info.append(f"✅ {script_path} 存在")
            else:
                self.warnings.append(f"⚠️  {script_path} 缺失")
        
        return len(self.errors) == 0
    
    def check_dependencies(self) -> bool:
        """检查依赖包"""
        print("🔍 检查Python依赖...")
        
        required_packages = [
            'aiogram',
            'aiosqlite', 
            'fasthtml',
            'aiohttp',
            'uvicorn'
        ]
        
        for package in required_packages:
            try:
                __import__(package)
                self.info.append(f"✅ {package} 已安装")
            except ImportError:
                self.warnings.append(f"⚠️  {package} 未安装或不可用")
        
        return True  # 依赖问题通常是警告，不阻止部署
    
    async def check_schema_consistency(self) -> bool:
        """检查Schema一致性（新增）"""
        if not self.schema_check_enabled:
            return True
            
        print("🔍 检查Schema一致性...")
        
        try:
            # 快速schema检查
            from scripts.quick_schema_check import quick_check
            schema_valid = await quick_check()
            
            if schema_valid:
                self.info.append("✅ Schema一致性检查通过")
                return True
            else:
                self.errors.append("❌ Schema一致性检查失败")
                return False
                
        except ImportError:
            self.warnings.append("⚠️  无法导入Schema检查模块")
            return True
        except Exception as e:
            self.warnings.append(f"⚠️  Schema检查异常: {e}")
            return True  # 不阻止部署，但记录警告
    
    def generate_deployment_summary(self) -> Dict:
        """生成部署摘要"""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_checks': len(self.errors) + len(self.warnings) + len(self.info),
            'errors': len(self.errors),
            'warnings': len(self.warnings),
            'status': 'READY' if len(self.errors) == 0 else 'FAILED',
            'schema_check_enabled': self.schema_check_enabled,
            'details': {
                'errors': self.errors,
                'warnings': self.warnings,
                'info': self.info
            }
        }
    
    def print_results(self):
        """打印检查结果"""
        print("\n" + "="*60)
        print("📋 部署前检查结果")
        print("="*60)
        
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
        print("\n" + "="*60)
        if self.errors:
            print("❌ 部署检查失败！请修复上述错误后重试。")
            return False
        elif self.warnings:
            print("⚠️  部署检查通过，但有警告信息请注意。")
            return True
        else:
            print("✅ 部署检查全部通过！可以开始部署。")
            return True


async def main():
    """主函数 - 增强版部署检查，包含Schema验证"""
    print("🚀 Railway部署前检查 (增强版)")
    print("="*80)
    print("包含Schema迁移一致性检查，确保部署完整性")
    
    checker = DeploymentChecker()
    
    # 检查是否需要跳过schema检查
    if '--skip-schema' in sys.argv:
        checker.schema_check_enabled = False
        print("⚠️  Schema检查已禁用")
    
    # 执行各项检查
    checks = [
        ("环境变量", checker.check_environment_variables()),
        ("配置完整性", checker.check_config_integrity()),
        ("文件结构", checker.check_file_structure()),
        ("Python依赖", checker.check_dependencies()),
        ("机器人Token", await checker.check_bot_token_validity()),
        ("Schema一致性", await checker.check_schema_consistency())
    ]
    
    # 统计结果
    passed = sum(1 for name, result in checks if result)
    total = len(checks)
    
    print(f"\n📊 检查完成: {passed}/{total} 项通过")
    
    # 打印详细结果
    checker.print_results()
    
    # 生成摘要文件
    summary = checker.generate_deployment_summary()
    summary_file = Path(__file__).parent.parent / 'deployment_check.json'
    
    try:
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n📄 检查报告已保存: {summary_file}")
    except Exception as e:
        print(f"\n⚠️  无法保存检查报告: {e}")
    
    # 返回退出码
    exit_code = 0 if len(checker.errors) == 0 else 1
    
    if exit_code == 0:
        print("\n🎉 部署检查成功！你的项目已准备好部署到Railway。")
        print("\n💡 下一步:")
        print("  1. 推送代码到GitHub仓库")
        print("  2. 在Railway中连接GitHub仓库") 
        print("  3. 配置环境变量")
        print("  4. 等待自动部署完成")
        print("  5. 验证/health端点和Schema一致性")
        
        if checker.schema_check_enabled:
            print("\n🔍 Schema检查信息:")
            print("  ✓ 部署后将自动执行完整Schema验证")
            print("  ✓ 如检测到不一致将自动报警")
            print("  ✓ 验证报告将保存为构建工件")
    else:
        print("\n⛔ 部署检查失败！请修复错误后重试。")
        print("\n🔧 常见解决方案:")
        print("  • Schema错误: 运行 python3 db_manager.py migrate")
        print("  • 环境变量: 检查 .env 文件配置")
        print("  • 文件缺失: 确保所有必需文件已提交")
        print("  • 依赖问题: 运行 pip install -r requirements.txt")
    
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)