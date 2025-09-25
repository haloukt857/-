# -*- coding: utf-8 -*-
"""
Telegram商户机器人V2.0管理员后台功能测试
测试实际的业务逻辑和数据库操作
"""

import os
import sys
import asyncio
import logging
import tempfile
import hashlib
from datetime import datetime
from unittest.mock import Mock

# 设置路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class FunctionalTestResult:
    def __init__(self):
        self.tests = []
        self.bugs = []
    
    def add_test(self, name, passed, error=None, details=None):
        self.tests.append({
            'name': name, 
            'passed': passed, 
            'error': error,
            'details': details
        })
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"   错误: {error}")
        if details:
            print(f"   详情: {details}")
    
    def add_bug(self, test_name, description, file_location, expected, actual, severity="中"):
        self.bugs.append({
            'test_name': test_name,
            'description': description,
            'file_location': file_location,
            'expected': expected,
            'actual': actual,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        })

result = FunctionalTestResult()

async def test_binding_code_functionality():
    """测试绑定码实际功能"""
    try:
        from database.db_binding_codes import binding_codes_manager
        
        # 测试生成绑定码
        code1 = await binding_codes_manager.generate_binding_code()
        code2 = await binding_codes_manager.generate_binding_code()
        
        if not code1 or not code2:
            result.add_test("绑定码生成功能", False, "生成绑定码为空")
            result.add_bug(
                "绑定码生成功能",
                "generate_binding_code返回空值",
                "database/db_binding_codes.py:29",
                "返回8位字符串",
                f"code1: {code1}, code2: {code2}",
                "高"
            )
            return
        
        # 测试唯一性
        if code1 == code2:
            result.add_test("绑定码唯一性", False, "生成了重复的绑定码")
            result.add_bug(
                "绑定码唯一性",
                "连续生成的绑定码相同",
                "database/db_binding_codes.py:50-70",
                "每次生成不同的绑定码",
                f"code1: {code1}, code2: {code2}",
                "高"
            )
            return
        
        result.add_test("绑定码生成和唯一性", True, details=f"生成码: {code1}, {code2}")
        
        # 测试查询功能
        code_info = await binding_codes_manager.get_binding_code_info(code1)
        if not code_info:
            result.add_test("绑定码信息查询", False, "无法查询到刚生成的绑定码")
            result.add_bug(
                "绑定码信息查询",
                "get_binding_code_info无法返回刚生成的绑定码信息",
                "database/db_binding_codes.py:100",
                "返回包含绑定码信息的字典",
                f"查询码: {code1}, 返回: {code_info}",
                "高"
            )
            return
        
        result.add_test("绑定码信息查询", True, details=f"查询到字段: {list(code_info.keys())}")
        
        # 测试统计功能
        stats = await binding_codes_manager.get_binding_code_statistics()
        if not isinstance(stats, dict):
            result.add_test("绑定码统计功能", False, "统计信息格式错误")
            result.add_bug(
                "绑定码统计功能", 
                "get_binding_code_statistics返回类型错误",
                "database/db_binding_codes.py:183",
                "返回字典类型",
                f"返回类型: {type(stats)}",
                "中"
            )
            return
        
        required_stats_keys = ['total_codes', 'used_codes', 'valid_codes', 'usage_rate']
        missing_keys = [key for key in required_stats_keys if key not in stats]
        if missing_keys:
            result.add_test("绑定码统计字段", False, f"缺少统计字段: {missing_keys}")
            result.add_bug(
                "绑定码统计字段",
                "统计信息缺少必要字段",
                "database/db_binding_codes.py:218-225",
                f"包含字段: {required_stats_keys}",
                f"实际字段: {list(stats.keys())}, 缺失: {missing_keys}",
                "中"
            )
            return
        
        result.add_test("绑定码统计功能", True, details=f"统计数据: {stats}")
        
    except Exception as e:
        result.add_test("绑定码功能测试", False, f"异常: {str(e)}")
        result.add_bug(
            "绑定码功能测试异常",
            "测试绑定码功能时抛出异常",
            "database/db_binding_codes.py",
            "正常执行不抛出异常",
            f"异常: {str(e)}",
            "高"
        )

async def test_region_functionality():
    """测试地区管理实际功能"""
    try:
        from database.db_regions import region_manager
        
        # 测试添加城市
        city_name = f"测试城市_{datetime.now().strftime('%H%M%S')}"
        city_id = await region_manager.add_city(city_name)
        
        if not city_id:
            result.add_test("地区添加城市", False, "添加城市返回None")
            result.add_bug(
                "地区添加城市",
                "add_city方法返回None而不是城市ID",
                "database/db_regions.py:92",
                "返回新创建城市的整数ID",
                f"输入: {city_name}, 返回: {city_id}",
                "高"
            )
            return
        
        result.add_test("地区添加城市", True, details=f"城市ID: {city_id}")
        
        # 测试添加地区
        district_name = f"测试地区_{datetime.now().strftime('%H%M%S')}"
        district_id = await region_manager.add_district(city_id, district_name)
        
        if not district_id:
            result.add_test("地区添加区域", False, "添加地区返回None")
            result.add_bug(
                "地区添加区域",
                "add_district方法返回None而不是地区ID",
                "database/db_regions.py:107",
                "返回新创建地区的整数ID",
                f"城市ID: {city_id}, 地区名: {district_name}, 返回: {district_id}",
                "高"
            )
            return
        
        result.add_test("地区添加区域", True, details=f"地区ID: {district_id}")
        
        # 测试查询功能
        city_info = await region_manager.get_city_by_id(city_id)
        if not city_info:
            result.add_test("地区城市查询", False, "无法查询到刚创建的城市")
            result.add_bug(
                "地区城市查询",
                "get_city_by_id无法返回刚创建的城市信息",
                "database/db_regions.py:192",
                "返回包含城市信息的字典",
                f"城市ID: {city_id}, 返回: {city_info}",
                "高"
            )
            return
        
        result.add_test("地区城市查询", True, details=f"城市信息: {city_info['name']}")
        
        # 测试搜索功能
        search_results = await region_manager.search_regions(city_name)
        if not isinstance(search_results, list):
            result.add_test("地区搜索功能", False, "搜索结果不是列表")
            result.add_bug(
                "地区搜索功能",
                "search_regions返回类型不是列表",
                "database/db_regions.py:23",
                "返回包含搜索结果的列表",
                f"搜索: {city_name}, 返回类型: {type(search_results)}",
                "中"
            )
            return
        
        result.add_test("地区搜索功能", True, details=f"搜索结果数量: {len(search_results)}")
        
    except Exception as e:
        result.add_test("地区功能测试", False, f"异常: {str(e)}")
        result.add_bug(
            "地区功能测试异常",
            "测试地区功能时抛出异常",
            "database/db_regions.py",
            "正常执行不抛出异常",
            f"异常: {str(e)}",
            "高"
        )

async def test_incentive_functionality():
    """测试激励系统实际功能"""
    try:
        from database.db_incentives import incentive_manager
        
        # 测试添加等级
        level_name = f"测试等级_{datetime.now().strftime('%H%M%S')}"
        xp_required = 1000
        level_id = await incentive_manager.add_level(level_name, xp_required)
        
        if not level_id:
            result.add_test("激励添加等级", False, "添加等级返回None")
            result.add_bug(
                "激励添加等级",
                "add_level方法返回None而不是等级ID",
                "database/db_incentives.py:47",
                "返回新创建等级的整数ID",
                f"等级名: {level_name}, XP: {xp_required}, 返回: {level_id}",
                "高"
            )
            return
        
        result.add_test("激励添加等级", True, details=f"等级ID: {level_id}")
        
        # 测试添加勋章
        badge_name = f"测试勋章_{datetime.now().strftime('%H%M%S')}"
        badge_icon = "🏆"
        description = "测试勋章描述"
        badge_id = await incentive_manager.add_badge(badge_name, badge_icon, description)
        
        if not badge_id:
            result.add_test("激励添加勋章", False, "添加勋章返回None")
            result.add_bug(
                "激励添加勋章",
                "add_badge方法返回None而不是勋章ID",
                "database/db_incentives.py:216",
                "返回新创建勋章的整数ID",
                f"勋章名: {badge_name}, 返回: {badge_id}",
                "高"
            )
            return
        
        result.add_test("激励添加勋章", True, details=f"勋章ID: {badge_id}")
        
        # 测试添加触发器
        trigger_type = "order_count"
        trigger_value = 10
        trigger_id = await incentive_manager.add_trigger(badge_id, trigger_type, trigger_value)
        
        if not trigger_id:
            result.add_test("激励添加触发器", False, "添加触发器返回None")
            result.add_bug(
                "激励添加触发器",
                "add_trigger方法返回None而不是触发器ID",
                "database/db_incentives.py:420",
                "返回新创建触发器的整数ID",
                f"勋章ID: {badge_id}, 类型: {trigger_type}, 值: {trigger_value}, 返回: {trigger_id}",
                "高"
            )
            return
        
        result.add_test("激励添加触发器", True, details=f"触发器ID: {trigger_id}")
        
        # 测试查询功能
        levels = await incentive_manager.get_all_levels()
        if not isinstance(levels, list):
            result.add_test("激励等级查询", False, "等级列表不是列表类型")
            result.add_bug(
                "激励等级查询",
                "get_all_levels返回类型不是列表",
                "database/db_incentives.py:29",
                "返回包含等级信息的列表",
                f"返回类型: {type(levels)}",
                "中"
            )
            return
        
        result.add_test("激励等级查询", True, details=f"等级数量: {len(levels)}")
        
        badges = await incentive_manager.get_all_badges()
        if not isinstance(badges, list):
            result.add_test("激励勋章查询", False, "勋章列表不是列表类型")
            result.add_bug(
                "激励勋章查询",
                "get_all_badges返回类型不是列表",
                "database/db_incentives.py:198",
                "返回包含勋章信息的列表",
                f"返回类型: {type(badges)}",
                "中"
            )
            return
        
        result.add_test("激励勋章查询", True, details=f"勋章数量: {len(badges)}")
        
    except Exception as e:
        result.add_test("激励功能测试", False, f"异常: {str(e)}")
        result.add_bug(
            "激励功能测试异常",
            "测试激励功能时抛出异常",
            "database/db_incentives.py",
            "正常执行不抛出异常",
            f"异常: {str(e)}",
            "高"
        )

def test_web_auth_functionality():
    """测试Web认证实际功能"""
    try:
        from web.app import AuthManager
        
        # 测试密码哈希
        password = "test123456"
        hashed = AuthManager.hash_password(password)
        
        if not hashed:
            result.add_test("Web密码哈希", False, "密码哈希返回空值")
            result.add_bug(
                "Web密码哈希",
                "hash_password返回空值或None",
                "web/app.py:52",
                "返回哈希后的密码字符串",
                f"输入: {password}, 返回: {hashed}",
                "高"
            )
            return
        
        # 验证哈希格式（应该是SHA256的hex格式）
        if len(hashed) != 64:
            result.add_test("Web密码哈希格式", False, "哈希长度不正确")
            result.add_bug(
                "Web密码哈希格式",
                "密码哈希长度不是64位（SHA256 hex）",
                "web/app.py:52",
                "返回64位的SHA256哈希值",
                f"实际长度: {len(hashed)}",
                "中"
            )
            return
        
        result.add_test("Web密码哈希", True, details=f"哈希长度: {len(hashed)}")
        
        # 测试密码验证
        is_valid = AuthManager.verify_password(password, hashed)
        if not is_valid:
            result.add_test("Web密码验证", False, "正确密码验证失败")
            result.add_bug(
                "Web密码验证",
                "verify_password对正确密码返回False",
                "web/app.py:57",
                "正确密码验证返回True",
                f"密码: {password}, 哈希: {hashed[:10]}..., 验证结果: {is_valid}",
                "高"
            )
            return
        
        # 测试错误密码
        is_invalid = AuthManager.verify_password("wrongpassword", hashed)
        if is_invalid:
            result.add_test("Web错误密码处理", False, "错误密码验证通过")
            result.add_bug(
                "Web错误密码处理",
                "verify_password对错误密码返回True",
                "web/app.py:57",
                "错误密码验证返回False",
                f"错误密码验证结果: {is_invalid}",
                "高"
            )
            return
        
        result.add_test("Web密码验证", True, details="正确密码通过，错误密码拒绝")
        
        # 测试会话验证
        mock_request_valid = Mock()
        mock_request_valid.session = {'is_admin': True, 'admin_id': 123456789}
        
        is_admin = AuthManager.is_admin_session(mock_request_valid)
        if not is_admin:
            result.add_test("Web会话验证", False, "有效管理员会话验证失败")
            result.add_bug(
                "Web会话验证",
                "is_admin_session对有效会话返回False",
                "web/app.py:62",
                "有效管理员会话返回True",
                f"会话: {mock_request_valid.session}, 结果: {is_admin}",
                "高"
            )
            return
        
        # 测试无效会话
        mock_request_invalid = Mock()
        mock_request_invalid.session = {}
        
        is_admin_invalid = AuthManager.is_admin_session(mock_request_invalid)
        if is_admin_invalid:
            result.add_test("Web无效会话处理", False, "无效会话被认为是管理员")
            result.add_bug(
                "Web无效会话处理",
                "is_admin_session对空会话返回True",
                "web/app.py:62",
                "无效会话返回False",
                f"空会话验证结果: {is_admin_invalid}",
                "高"
            )
            return
        
        result.add_test("Web会话验证", True, details="有效会话通过，无效会话拒绝")
        
    except Exception as e:
        result.add_test("Web认证功能测试", False, f"异常: {str(e)}")
        result.add_bug(
            "Web认证功能测试异常",
            "测试Web认证功能时抛出异常",
            "web/app.py",
            "正常执行不抛出异常",
            f"异常: {str(e)}",
            "高"
        )

def generate_functional_report():
    """生成功能测试报告"""
    total_tests = len(result.tests)
    passed_tests = sum(1 for test in result.tests if test['passed'])
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    # 按严重程度统计Bug
    high_severity_bugs = sum(1 for bug in result.bugs if bug['severity'] == '高')
    medium_severity_bugs = sum(1 for bug in result.bugs if bug['severity'] == '中')
    low_severity_bugs = sum(1 for bug in result.bugs if bug['severity'] == '低')
    
    report = f"""
# Telegram商户机器人V2.0管理员后台功能测试报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**测试类型**: 实际业务逻辑和数据库操作功能验证  
**测试环境**: Python {sys.version}

## 📊 测试总结

- **总测试数**: {total_tests}
- **通过测试**: {passed_tests} 
- **失败测试**: {failed_tests}
- **成功率**: {success_rate:.1f}%

## 🐛 Bug严重程度分布

- **高严重**: {high_severity_bugs} 个
- **中严重**: {medium_severity_bugs} 个  
- **低严重**: {low_severity_bugs} 个
- **总Bug数**: {len(result.bugs)} 个

## ✅ 测试详情

"""
    
    for test in result.tests:
        status = "✅" if test['passed'] else "❌"
        report += f"- {status} **{test['name']}**"
        if test['error']:
            report += f" - ❌ {test['error']}"
        if test['details']:
            report += f" - 💡 {test['details']}"
        report += "\n"
    
    if result.bugs:
        report += f"\n## 🐛 发现的Bug详情 ({len(result.bugs)}个)\n\n"
        for i, bug in enumerate(result.bugs, 1):
            severity_emoji = {"高": "🔴", "中": "🟡", "低": "🟢"}[bug['severity']]
            report += f"""
### Bug #{i}: {bug['description']} {severity_emoji}

**测试用例**: {bug['test_name']}  
**文件位置**: `{bug['file_location']}`  
**严重程度**: {bug['severity']}  
**发现时间**: {bug['timestamp']}

**预期行为**:  
{bug['expected']}

**实际情况**:  
{bug['actual']}

**影响评估**:  
{"可能导致核心功能失效，需要立即修复" if bug['severity'] == '高' else "功能可用但存在问题，建议尽快修复" if bug['severity'] == '中' else "轻微问题，可在后续版本中修复"}

---
"""
    else:
        report += "\n## 🎉 测试结果\n\n✅ **所有功能测试都通过了！**\n\n管理员后台的核心功能工作正常，没有发现Bug。\n"
    
    # 添加测试覆盖率说明
    report += f"""
## 📋 测试覆盖范围

本次测试覆盖了以下管理员后台核心功能：

### 1. 绑定码管理
- ✅ 绑定码生成功能
- ✅ 绑定码唯一性验证
- ✅ 绑定码信息查询
- ✅ 绑定码统计功能

### 2. 地区管理
- ✅ 城市添加功能
- ✅ 地区添加功能  
- ✅ 城市信息查询
- ✅ 地区搜索功能

### 3. 激励系统管理
- ✅ 等级添加功能
- ✅ 勋章添加功能
- ✅ 触发器添加功能
- ✅ 等级和勋章查询功能

### 4. Web后台认证
- ✅ 密码哈希功能
- ✅ 密码验证功能
- ✅ 管理员会话验证
- ✅ 无效会话处理

## 💡 测试建议

{"❌ **立即处理**: 发现了" + str(high_severity_bugs) + "个高严重度Bug，建议立即修复后再部署。" if high_severity_bugs > 0 else ""}
{"⚠️ **优先处理**: 发现了" + str(medium_severity_bugs) + "个中等严重度问题，建议在下个版本中优先修复。" if medium_severity_bugs > 0 else ""}
{"✅ **可以部署**: 所有核心功能正常工作，管理员后台可以安全部署使用。" if len(result.bugs) == 0 else ""}

## 🔄 复现步骤

所有测试都可以通过运行以下命令重现：
```bash
python3 tests/integration/test_admin_functional.py
```

---
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    return report

async def main():
    """主测试函数"""
    print("🚀 开始执行Telegram商户机器人V2.0管理员后台功能测试...\n")
    
    # 执行功能测试
    await test_binding_code_functionality()
    await test_region_functionality()
    await test_incentive_functionality()
    test_web_auth_functionality()
    
    print(f"\n🏁 测试执行完成！")
    print(f"📊 总计: {len(result.tests)} 个功能测试")
    print(f"✅ 通过: {sum(1 for test in result.tests if test['passed'])} 个")
    print(f"❌ 失败: {sum(1 for test in result.tests if not test['passed'])} 个")
    print(f"🐛 发现Bug: {len(result.bugs)} 个")
    
    if result.bugs:
        high_bugs = sum(1 for bug in result.bugs if bug['severity'] == '高')
        if high_bugs > 0:
            print(f"🔴 高严重Bug: {high_bugs} 个 - 需要立即修复！")
    
    # 生成并保存报告
    report = generate_functional_report()
    report_path = "tests/admin_backend_functional_report.md"
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n📄 详细功能测试报告已保存到: {report_path}")
    except Exception as e:
        print(f"❌ 保存报告失败: {e}")
        print("\n📄 报告内容:")
        print(report)

if __name__ == "__main__":
    asyncio.run(main())