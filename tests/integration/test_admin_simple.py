# -*- coding: utf-8 -*-
"""
Telegram商户机器人V2.0管理员后台简化测试
避免复杂导入问题，专注于核心功能测试
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# 设置路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class TestResult:
    def __init__(self):
        self.tests = []
        self.bugs = []
    
    def add_test(self, name, passed, error=None):
        self.tests.append({'name': name, 'passed': passed, 'error': error})
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"   错误: {error}")
    
    def add_bug(self, test_name, description, file_location, expected, actual):
        self.bugs.append({
            'test_name': test_name,
            'description': description,
            'file_location': file_location,
            'expected': expected,
            'actual': actual
        })

result = TestResult()

async def test_basic_imports():
    """测试基础模块导入"""
    try:
        from database.db_connection import db_manager
        result.add_test("数据库连接模块导入", True)
    except Exception as e:
        result.add_test("数据库连接模块导入", False, str(e))
        result.add_bug(
            "数据库连接模块导入",
            "无法导入数据库连接模块",
            "database/db_connection.py",
            "模块正常导入",
            f"导入错误: {str(e)}"
        )

async def test_binding_codes():
    """测试绑定码功能"""
    try:
        from database.db_binding_codes import binding_codes_manager
        
        # 测试模块导入
        result.add_test("绑定码模块导入", True)
        
        # 测试生成方法存在
        if hasattr(binding_codes_manager, 'generate_binding_code'):
            result.add_test("绑定码生成方法存在", True)
        else:
            result.add_test("绑定码生成方法存在", False, "缺少generate_binding_code方法")
            result.add_bug(
                "绑定码生成方法",
                "BindingCodesManager缺少generate_binding_code方法",
                "database/db_binding_codes.py",
                "存在generate_binding_code方法",
                "方法不存在或不可访问"
            )
        
        # 测试统计方法存在
        if hasattr(binding_codes_manager, 'get_binding_code_statistics'):
            result.add_test("绑定码统计方法存在", True)
        else:
            result.add_test("绑定码统计方法存在", False, "缺少get_binding_code_statistics方法")
            result.add_bug(
                "绑定码统计方法",
                "BindingCodesManager缺少get_binding_code_statistics方法",
                "database/db_binding_codes.py",
                "存在get_binding_code_statistics方法",
                "方法不存在或不可访问"
            )
            
    except ImportError as e:
        result.add_test("绑定码模块导入", False, str(e))
        result.add_bug(
            "绑定码模块导入失败",
            "无法导入绑定码管理模块",
            "database/db_binding_codes.py",
            "模块正常导入",
            f"ImportError: {str(e)}"
        )

async def test_regions():
    """测试地区管理功能"""
    try:
        from database.db_regions import region_manager
        
        result.add_test("地区模块导入", True)
        
        # 检查关键方法
        methods = ['add_city', 'add_district', 'get_all_cities_with_districts', 'search_regions']
        for method in methods:
            if hasattr(region_manager, method):
                result.add_test(f"地区{method}方法存在", True)
            else:
                result.add_test(f"地区{method}方法存在", False, f"缺少{method}方法")
                result.add_bug(
                    f"地区{method}方法",
                    f"RegionManager缺少{method}方法",
                    "database/db_regions.py",
                    f"存在{method}方法",
                    "方法不存在或不可访问"
                )
                
    except ImportError as e:
        result.add_test("地区模块导入", False, str(e))
        result.add_bug(
            "地区模块导入失败",
            "无法导入地区管理模块",
            "database/db_regions.py",
            "模块正常导入",
            f"ImportError: {str(e)}"
        )

async def test_incentives():
    """测试激励系统功能"""
    try:
        from database.db_incentives import incentive_manager
        
        result.add_test("激励系统模块导入", True)
        
        # 检查关键方法
        methods = ['add_level', 'add_badge', 'add_trigger', 'get_all_levels', 'get_all_badges']
        for method in methods:
            if hasattr(incentive_manager, method):
                result.add_test(f"激励{method}方法存在", True)
            else:
                result.add_test(f"激励{method}方法存在", False, f"缺少{method}方法")
                result.add_bug(
                    f"激励{method}方法",
                    f"IncentiveManager缺少{method}方法",
                    "database/db_incentives.py",
                    f"存在{method}方法",
                    "方法不存在或不可访问"
                )
                
    except ImportError as e:
        result.add_test("激励系统模块导入", False, str(e))
        result.add_bug(
            "激励系统模块导入失败",
            "无法导入激励系统管理模块",
            "database/db_incentives.py",
            "模块正常导入",
            f"ImportError: {str(e)}"
        )

async def test_web_auth():
    """测试Web后台认证"""
    try:
        from web.app import AuthManager
        
        result.add_test("Web认证模块导入", True)
        
        # 检查认证方法
        methods = ['hash_password', 'verify_password', 'is_admin_session']
        for method in methods:
            if hasattr(AuthManager, method):
                result.add_test(f"认证{method}方法存在", True)
            else:
                result.add_test(f"认证{method}方法存在", False, f"缺少{method}方法")
                result.add_bug(
                    f"认证{method}方法",
                    f"AuthManager缺少{method}方法",
                    "web/app.py",
                    f"存在{method}方法",
                    "方法不存在或不可访问"
                )
                
    except ImportError as e:
        result.add_test("Web认证模块导入", False, str(e))
        result.add_bug(
            "Web认证模块导入失败",
            "无法导入Web认证模块",
            "web/app.py",
            "模块正常导入",
            f"ImportError: {str(e)}"
        )

def test_admin_config():
    """测试管理员配置"""
    try:
        from config import ADMIN_IDS
        
        result.add_test("管理员配置导入", True)
        
        if isinstance(ADMIN_IDS, (list, tuple)):
            result.add_test("管理员ID配置类型正确", True)
        else:
            result.add_test("管理员ID配置类型正确", False, f"ADMIN_IDS类型错误: {type(ADMIN_IDS)}")
            result.add_bug(
                "管理员ID配置类型",
                "ADMIN_IDS不是列表或元组类型",
                "config.py",
                "ADMIN_IDS应该是列表或元组",
                f"实际类型: {type(ADMIN_IDS)}"
            )
            
    except ImportError as e:
        result.add_test("管理员配置导入", False, str(e))
        result.add_bug(
            "管理员配置导入失败",
            "无法导入管理员配置",
            "config.py",
            "配置正常导入",
            f"ImportError: {str(e)}"
        )

async def test_web_routes():
    """测试Web路由"""
    try:
        # 测试商户路由
        from web.routes.merchants import merchants_routes
        result.add_test("商户路由模块导入", True)
        
        # 测试地区路由
        from web.routes.regions import regions_routes
        result.add_test("地区路由模块导入", True)
        
        # 测试激励路由
        from web.routes.incentives import incentives_routes
        result.add_test("激励路由模块导入", True)
        
    except ImportError as e:
        result.add_test("Web路由模块导入", False, str(e))
        result.add_bug(
            "Web路由模块导入失败",
            "无法导入Web路由模块",
            "web/routes/",
            "路由模块正常导入",
            f"ImportError: {str(e)}"
        )

def generate_report():
    """生成测试报告"""
    total_tests = len(result.tests)
    passed_tests = sum(1 for test in result.tests if test['passed'])
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    report = f"""
# Telegram商户机器人V2.0管理员后台简化测试报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试类型**: 模块导入和方法存在性验证
**测试环境**: Python {sys.version}

## 测试总结

- **总测试数**: {total_tests}
- **通过测试**: {passed_tests}
- **失败测试**: {failed_tests}
- **成功率**: {success_rate:.1f}%

## 测试详情

"""
    
    for test in result.tests:
        status = "✅" if test['passed'] else "❌"
        report += f"- {status} **{test['name']}**"
        if test['error']:
            report += f" - 错误: {test['error']}"
        report += "\n"
    
    if result.bugs:
        report += f"\n## 发现的问题 ({len(result.bugs)}个)\n\n"
        for i, bug in enumerate(result.bugs, 1):
            report += f"""
### 问题 #{i}: {bug['description']}

**测试用例**: {bug['test_name']}
**文件位置**: {bug['file_location']}
**预期行为**: {bug['expected']}
**实际情况**: {bug['actual']}

---
"""
    else:
        report += "\n## ✅ 没有发现问题\n\n所有测试都通过了！\n"
    
    return report

async def main():
    """主测试函数"""
    print("开始执行Telegram商户机器人V2.0管理员后台简化测试...\n")
    
    # 执行测试
    await test_basic_imports()
    await test_binding_codes()
    await test_regions()
    await test_incentives()
    await test_web_auth()
    test_admin_config()
    await test_web_routes()
    
    print(f"\n测试完成！")
    print(f"总计: {len(result.tests)} 个测试")
    print(f"通过: {sum(1 for test in result.tests if test['passed'])} 个")
    print(f"失败: {sum(1 for test in result.tests if not test['passed'])} 个")
    print(f"发现问题: {len(result.bugs)} 个")
    
    # 生成报告
    report = generate_report()
    
    # 保存报告
    report_path = "tests/admin_backend_simple_report.md"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n详细报告已保存到: {report_path}")
    except Exception as e:
        print(f"保存报告失败: {e}")
        print("\n报告内容:")
        print(report)

if __name__ == "__main__":
    asyncio.run(main())