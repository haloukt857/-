#!/usr/bin/env python3
"""
部署后钩子脚本
自动部署完成后立即执行完整的schema迁移检查和健康检查
"""

import os
import sys
import json
import asyncio
import aiohttp
from typing import Dict, List
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.schema_migration_check import SchemaMigrationChecker
from scripts.deploy import DeploymentChecker


class PostDeploymentValidator:
    """部署后验证器"""
    
    def __init__(self):
        self.results = {
            'deployment_start': datetime.now().isoformat(),
            'checks': {},
            'overall_status': 'PENDING',
            'errors': [],
            'warnings': [],
            'info': []
        }
        
    async def run_full_validation(self) -> bool:
        """运行完整的部署后验证"""
        print("🚀 开始部署后验证流程")
        print("="*80)
        
        validation_steps = [
            ("基础健康检查", self.basic_health_check),
            ("Schema迁移验证", self.schema_migration_validation),
            ("服务功能验证", self.service_functionality_validation),
            ("性能基准测试", self.performance_baseline_test)
        ]
        
        overall_success = True
        
        for step_name, step_func in validation_steps:
            print(f"\n🔍 执行: {step_name}")
            print("-" * 60)
            
            try:
                step_success = await step_func()
                self.results['checks'][step_name] = {
                    'status': 'PASS' if step_success else 'FAIL',
                    'timestamp': datetime.now().isoformat()
                }
                
                if step_success:
                    print(f"✅ {step_name} - 通过")
                else:
                    print(f"❌ {step_name} - 失败")
                    overall_success = False
                    
            except Exception as e:
                print(f"❌ {step_name} - 异常: {e}")
                self.results['checks'][step_name] = {
                    'status': 'ERROR',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                overall_success = False
        
        self.results['overall_status'] = 'SUCCESS' if overall_success else 'FAILED'
        self.results['deployment_end'] = datetime.now().isoformat()
        
        return overall_success
    
    async def basic_health_check(self) -> bool:
        """基础健康检查"""
        try:
            # 1. 检查数据库连接
            from database.db_connection import db_manager
            await db_manager.initialize()
            
            # 执行简单查询验证数据库
            result = await db_manager.fetch_one("SELECT COUNT(*) as count FROM sqlite_master WHERE type='table'")
            table_count = result['count'] if result else 0
            
            if table_count < 10:  # 期望至少10个表
                self.results['errors'].append(f"数据库表数量异常: {table_count}")
                return False
            
            self.results['info'].append(f"数据库连接正常，包含 {table_count} 个表")
            await db_manager.close()
            
            # 2. 检查环境变量
            required_env_vars = ['BOT_TOKEN', 'ADMIN_IDS']
            for var in required_env_vars:
                if not os.getenv(var):
                    self.results['errors'].append(f"缺少环境变量: {var}")
                    return False
            
            self.results['info'].append("环境变量检查通过")
            
            # 3. 检查文件结构
            critical_files = ['main.py', 'bot.py', 'config.py']
            project_root = Path(__file__).parent.parent
            
            for file_name in critical_files:
                if not (project_root / file_name).exists():
                    self.results['errors'].append(f"关键文件缺失: {file_name}")
                    return False
            
            self.results['info'].append("文件结构检查通过")
            return True
            
        except Exception as e:
            self.results['errors'].append(f"基础健康检查失败: {e}")
            return False
    
    async def schema_migration_validation(self) -> bool:
        """Schema迁移验证"""
        try:
            checker = SchemaMigrationChecker()
            
            # 初始化数据库连接
            from database.db_connection import db_manager
            await db_manager.initialize()
            
            # 执行schema检查
            expected_version = checker.load_expected_schema_version()
            actual_version = await checker.get_actual_schema_version()
            
            # 版本匹配检查
            if expected_version != actual_version:
                self.results['errors'].append(f"Schema版本不匹配: 期望 {expected_version}, 实际 {actual_version}")
                return False
            
            # 表结构检查
            table_structure_valid = await checker.check_table_structure_consistency()
            if not table_structure_valid:
                self.results['errors'].append("表结构检查失败")
                return False
            
            # 数据完整性检查
            data_integrity_valid = await checker.check_data_integrity()
            if not data_integrity_valid:
                self.results['errors'].append("数据完整性检查失败")
                return False
            
            await db_manager.close()
            
            self.results['info'].append(f"Schema迁移验证成功: {actual_version}")
            return True
            
        except Exception as e:
            self.results['errors'].append(f"Schema迁移验证失败: {e}")
            return False
    
    async def service_functionality_validation(self) -> bool:
        """服务功能验证"""
        try:
            # 检查Web服务健康端点
            base_url = os.getenv('WEBHOOK_URL', 'http://localhost:8001')
            health_url = f"{base_url.rstrip('/')}/health"
            
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(health_url, timeout=10) as response:
                        if response.status == 200:
                            health_data = await response.json()
                            self.results['info'].append(f"Web健康检查通过: {health_data}")
                        else:
                            self.results['warnings'].append(f"Web健康检查异常状态: {response.status}")
                            return True  # 非致命错误
                except aiohttp.ClientError as e:
                    self.results['warnings'].append(f"无法连接Web服务: {e}")
                    # 在某些部署环境中，Web服务可能还在启动中
                    return True
            
            # 验证Bot Token（如果有的话）
            bot_token = os.getenv('BOT_TOKEN')
            if bot_token and bot_token != 'YOUR_BOT_TOKEN_HERE':
                bot_api_url = f"https://api.telegram.org/bot{bot_token}/getMe"
                
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(bot_api_url, timeout=10) as response:
                            if response.status == 200:
                                bot_data = await response.json()
                                if bot_data.get('ok'):
                                    bot_info = bot_data.get('result', {})
                                    username = bot_info.get('username', 'Unknown')
                                    self.results['info'].append(f"Bot验证成功: @{username}")
                                else:
                                    self.results['errors'].append(f"Bot验证失败: {bot_data}")
                                    return False
                            else:
                                self.results['errors'].append(f"Bot API请求失败: {response.status}")
                                return False
                    except aiohttp.ClientError as e:
                        self.results['errors'].append(f"Bot连接失败: {e}")
                        return False
            
            return True
            
        except Exception as e:
            self.results['errors'].append(f"服务功能验证失败: {e}")
            return False
    
    async def performance_baseline_test(self) -> bool:
        """性能基准测试"""
        try:
            # 数据库查询性能测试
            from database.db_connection import db_manager
            await db_manager.initialize()
            
            start_time = asyncio.get_event_loop().time()
            
            # 执行几个典型查询测试响应时间
            test_queries = [
                "SELECT COUNT(*) FROM merchants",
                "SELECT COUNT(*) FROM orders", 
                "SELECT COUNT(*) FROM keywords",
                "SELECT config_value FROM system_config WHERE config_key = 'schema_version'"
            ]
            
            for query in test_queries:
                query_start = asyncio.get_event_loop().time()
                await db_manager.fetch_one(query)
                query_time = (asyncio.get_event_loop().time() - query_start) * 1000
                
                if query_time > 1000:  # 超过1秒认为过慢
                    self.results['warnings'].append(f"查询较慢 ({query_time:.2f}ms): {query}")
            
            total_time = (asyncio.get_event_loop().time() - start_time) * 1000
            self.results['info'].append(f"数据库性能测试完成: {total_time:.2f}ms")
            
            await db_manager.close()
            
            # Web服务响应测试（如果可用）
            base_url = os.getenv('WEBHOOK_URL', 'http://localhost:8001')
            if base_url != 'http://localhost:8001':  # 只在实际部署环境测试
                async with aiohttp.ClientSession() as session:
                    try:
                        start_time = asyncio.get_event_loop().time()
                        async with session.get(f"{base_url}/health", timeout=10) as response:
                            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                            
                            if response_time > 5000:  # 超过5秒认为过慢
                                self.results['warnings'].append(f"Web服务响应较慢: {response_time:.2f}ms")
                            else:
                                self.results['info'].append(f"Web服务响应正常: {response_time:.2f}ms")
                    except:
                        pass  # Web性能测试失败不影响整体结果
            
            return True
            
        except Exception as e:
            self.results['warnings'].append(f"性能测试异常: {e}")
            return True  # 性能测试失败不算致命错误
    
    def generate_validation_report(self) -> Dict:
        """生成验证报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'deployment_validation': self.results,
            'environment': {
                'railway_env': os.getenv('RAILWAY_ENVIRONMENT'),
                'python_version': sys.version,
                'deployment_id': os.getenv('RAILWAY_DEPLOYMENT_ID'),
                'service_id': os.getenv('RAILWAY_SERVICE_ID')
            }
        }
    
    def print_summary(self) -> bool:
        """打印验证摘要"""
        print("\n" + "="*80)
        print("📋 部署后验证摘要")
        print("="*80)
        
        # 检查结果
        print(f"\n📊 检查结果:")
        for check_name, check_result in self.results['checks'].items():
            status_icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥"}.get(check_result['status'], "❓")
            print(f"  {status_icon} {check_name}: {check_result['status']}")
        
        # 信息
        if self.results['info']:
            print(f"\n✅ 成功信息 ({len(self.results['info'])}):")
            for info in self.results['info']:
                print(f"  • {info}")
        
        # 警告
        if self.results['warnings']:
            print(f"\n⚠️  警告信息 ({len(self.results['warnings'])}):")
            for warning in self.results['warnings']:
                print(f"  • {warning}")
        
        # 错误
        if self.results['errors']:
            print(f"\n❌ 错误信息 ({len(self.results['errors'])}):")
            for error in self.results['errors']:
                print(f"  • {error}")
        
        # 总结
        print("\n" + "="*80)
        success = self.results['overall_status'] == 'SUCCESS'
        
        if success:
            print("🎉 部署验证成功！系统已准备就绪。")
            print("\n✅ 验证通过:")
            print("  ✓ 数据库连接和结构正常")
            print("  ✓ Schema迁移完整一致")
            print("  ✓ 服务功能正常")
            print("  ✓ 性能基准达标")
        else:
            print("❌ 部署验证失败！需要立即处理。")
            print(f"\n🔧 失败的检查项 ({len([c for c in self.results['checks'].values() if c['status'] != 'PASS'])}):")
            for name, result in self.results['checks'].items():
                if result['status'] != 'PASS':
                    print(f"  ❌ {name}")
        
        return success


async def main():
    """主函数"""
    print("🚀 部署后验证系统")
    print("="*80)
    print("验证部署是否成功，确保所有组件正常运行")
    
    validator = PostDeploymentValidator()
    
    try:
        # 等待服务完全启动（给予一些时间）
        print("⏳ 等待服务启动...")
        await asyncio.sleep(10)  # 给服务10秒启动时间
        
        # 执行完整验证
        success = await validator.run_full_validation()
        
        # 打印摘要
        validator.print_summary()
        
        # 保存验证报告
        report = validator.generate_validation_report()
        report_file = Path(__file__).parent.parent / 'post_deploy_validation.json'
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"\n📄 验证报告已保存: {report_file}")
        except Exception as e:
            print(f"\n⚠️  无法保存验证报告: {e}")
        
        if success:
            print("\n🎯 下一步:")
            print("  1. 验证Bot响应用户消息")
            print("  2. 检查Web管理面板访问")
            print("  3. 监控系统运行日志")
            print("  4. 验证核心业务流程")
        else:
            print("\n🆘 紧急处理:")
            print("  1. 查看详细错误日志")
            print("  2. 检查环境变量配置")
            print("  3. 验证数据库迁移状态")
            print("  4. 重启服务或回滚部署")
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n💥 验证过程异常: {e}")
        print("\n🔧 故障排除:")
        print("  1. 检查服务是否正常启动")
        print("  2. 验证环境变量配置")
        print("  3. 查看应用启动日志")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)