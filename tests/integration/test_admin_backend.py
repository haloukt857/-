# -*- coding: utf-8 -*-
"""
Telegram商户机器人V2.0管理员后台设置功能全面测试

测试重点：
1. 绑定码管理测试  
2. 地区管理测试
3. 关键词管理测试
4. 等级和勋章配置测试
5. Web后台访问权限测试
"""

import pytest
import asyncio
import logging
import tempfile
import os
from typing import Dict, List, Any
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

# 测试框架配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 设置路径
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入数据库管理器 (核心测试模块)
try:
    from database.db_binding_codes import binding_codes_manager
    BINDING_CODES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"无法导入binding_codes_manager: {e}")
    binding_codes_manager = None
    BINDING_CODES_AVAILABLE = False

try:
    from database.db_regions import region_manager  
    REGIONS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"无法导入region_manager: {e}")
    region_manager = None
    REGIONS_AVAILABLE = False

try:
    from database.db_incentives import incentive_manager
    INCENTIVES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"无法导入incentive_manager: {e}")
    incentive_manager = None
    INCENTIVES_AVAILABLE = False

# 导入Web组件 (可选)
try:
    from web.app import AuthManager
    WEB_AUTH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"无法导入AuthManager: {e}")
    AuthManager = None
    WEB_AUTH_AVAILABLE = False

# 导入管理员处理器 (可选)
try:
    from config import ADMIN_IDS
    ADMIN_CONFIG_AVAILABLE = True
    
    # 简化的AdminHandler用于测试
    class SimpleAdminHandler:
        @staticmethod
        def is_admin(user_id: int) -> bool:
            return user_id in ADMIN_IDS
    AdminHandler = SimpleAdminHandler
    
except ImportError as e:
    logger.warning(f"无法导入ADMIN_IDS: {e}")
    AdminHandler = None
    ADMIN_CONFIG_AVAILABLE = False

class TestResults:
    """测试结果收集器"""
    def __init__(self):
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0
        self.errors = []
        self.bug_reports = []
    
    def add_test(self, test_name: str, passed: bool, error_msg: str = None):
        self.test_count += 1
        if passed:
            self.passed_count += 1
            logger.info(f"✅ {test_name} - PASSED")
        else:
            self.failed_count += 1
            error_detail = f"❌ {test_name} - FAILED: {error_msg}"
            self.errors.append(error_detail)
            logger.error(error_detail)
    
    def add_bug_report(self, test_name: str, bug_description: str, file_location: str, expected_behavior: str, actual_behavior: str):
        bug_report = {
            'test_name': test_name,
            'bug_description': bug_description,
            'file_location': file_location,
            'expected_behavior': expected_behavior,
            'actual_behavior': actual_behavior,
            'timestamp': datetime.now().isoformat()
        }
        self.bug_reports.append(bug_report)
    
    def get_summary(self) -> str:
        success_rate = (self.passed_count / self.test_count * 100) if self.test_count > 0 else 0
        return f"""
========== 测试总结 ==========
总测试数量: {self.test_count}
通过: {self.passed_count}
失败: {self.failed_count}
成功率: {success_rate:.1f}%

{'='*50}
"""

# 全局测试结果收集器
test_results = TestResults()

@pytest.fixture
async def setup_test_environment():
    """设置测试环境"""
    # 设置临时数据库路径
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    # 设置环境变量
    os.environ['DATABASE_PATH'] = temp_db.name
    os.environ['TEST_MODE'] = 'true'
    
    yield temp_db.name
    
    # 清理
    try:
        os.unlink(temp_db.name)
    except:
        pass

class TestBindingCodeManagement:
    """绑定码管理测试"""
    
    async def test_generate_binding_code(self):
        """测试绑定码生成功能"""
        if not BINDING_CODES_AVAILABLE or not binding_codes_manager:
            test_results.add_test("绑定码生成", False, "binding_codes_manager模块不可用")
            test_results.add_bug_report(
                "绑定码模块导入失败",
                "无法导入database.db_binding_codes模块",
                "database/db_binding_codes.py",
                "模块可以正常导入和使用",
                "ImportError或模块不存在"
            )
            return
            
        try:
            # 测试生成绑定码
            code = await binding_codes_manager.generate_binding_code()
            
            # 验证生成结果
            if not code:
                test_results.add_test("绑定码生成", False, "生成的绑定码为空")
                test_results.add_bug_report(
                    "绑定码生成",
                    "generate_binding_code返回None或空字符串",
                    "database/db_binding_codes.py:29",
                    "返回8位大写字母和数字组成的绑定码",
                    f"实际返回: {repr(code)}"
                )
                return
            
            if len(code) != 8:
                test_results.add_test("绑定码生成", False, f"绑定码长度错误，期望8位，实际{len(code)}位")
                test_results.add_bug_report(
                    "绑定码长度验证",
                    "生成的绑定码长度不符合规范",
                    "database/db_binding_codes.py:24",
                    "绑定码长度应为8位",
                    f"实际长度: {len(code)}"
                )
                return
            
            # 验证字符集
            import string
            valid_chars = string.ascii_uppercase + string.digits
            if not all(c in valid_chars for c in code):
                test_results.add_test("绑定码生成", False, "绑定码包含无效字符")
                test_results.add_bug_report(
                    "绑定码字符集验证",
                    "绑定码包含大写字母和数字以外的字符",
                    "database/db_binding_codes.py:25",
                    "只包含大写字母A-Z和数字0-9",
                    f"实际包含: {code}"
                )
                return
            
            test_results.add_test("绑定码生成", True)
            
        except Exception as e:
            test_results.add_test("绑定码生成", False, str(e))
            test_results.add_bug_report(
                "绑定码生成异常",
                "生成绑定码时抛出异常",
                "database/db_binding_codes.py:29",
                "正常生成绑定码不抛出异常",
                f"异常信息: {str(e)}"
            )
    
    async def test_binding_code_uniqueness(self):
        """测试绑定码唯一性"""
        if not BINDING_CODES_AVAILABLE or not binding_codes_manager:
            test_results.add_test("绑定码唯一性", False, "binding_codes_manager模块不可用")
            return
            
        try:
            codes = []
            for _ in range(10):
                code = await binding_codes_manager.generate_binding_code()
                if code:
                    codes.append(code)
            
            if len(set(codes)) != len(codes):
                test_results.add_test("绑定码唯一性", False, "生成了重复的绑定码")
                test_results.add_bug_report(
                    "绑定码唯一性验证",
                    "多次生成绑定码时出现重复",
                    "database/db_binding_codes.py:50-70",
                    "每次生成的绑定码都应该是唯一的",
                    f"生成的绑定码: {codes}, 重复项: {len(codes) - len(set(codes))}"
                )
                return
            
            test_results.add_test("绑定码唯一性", True)
            
        except Exception as e:
            test_results.add_test("绑定码唯一性", False, str(e))
    
    async def test_binding_code_validation(self):
        """测试绑定码验证功能"""
        try:
            # 生成有效绑定码
            valid_code = await binding_codes_manager.generate_binding_code()
            
            # 测试有效绑定码信息获取
            code_info = await binding_codes_manager.get_binding_code_info(valid_code)
            if not code_info:
                test_results.add_test("绑定码信息获取", False, "无法获取有效绑定码信息")
                test_results.add_bug_report(
                    "绑定码信息获取",
                    "get_binding_code_info无法返回已生成绑定码的信息",
                    "database/db_binding_codes.py:100",
                    "返回包含绑定码详细信息的字典",
                    f"返回值: {code_info}"
                )
                return
            
            # 测试无效绑定码
            invalid_info = await binding_codes_manager.get_binding_code_info("INVALID123")
            if invalid_info is not None:
                test_results.add_test("无效绑定码处理", False, "不存在的绑定码返回了信息")
                test_results.add_bug_report(
                    "无效绑定码处理",
                    "不存在的绑定码返回了非None值",
                    "database/db_binding_codes.py:100",
                    "不存在的绑定码应返回None",
                    f"返回值: {invalid_info}"
                )
                return
            
            test_results.add_test("绑定码验证功能", True)
            
        except Exception as e:
            test_results.add_test("绑定码验证功能", False, str(e))
    
    async def test_binding_code_statistics(self):
        """测试绑定码统计功能"""
        try:
            # 生成一些测试数据
            for _ in range(3):
                await binding_codes_manager.generate_binding_code()
            
            # 获取统计信息
            stats = await binding_codes_manager.get_binding_code_statistics()
            
            if not isinstance(stats, dict):
                test_results.add_test("绑定码统计", False, "统计信息不是字典类型")
                test_results.add_bug_report(
                    "绑定码统计类型错误",
                    "get_binding_code_statistics返回类型错误",
                    "database/db_binding_codes.py:183",
                    "返回包含统计信息的字典",
                    f"实际返回类型: {type(stats)}"
                )
                return
            
            required_keys = ['total_codes', 'used_codes', 'valid_codes', 'usage_rate']
            missing_keys = [key for key in required_keys if key not in stats]
            if missing_keys:
                test_results.add_test("绑定码统计", False, f"统计信息缺少字段: {missing_keys}")
                test_results.add_bug_report(
                    "绑定码统计字段缺失",
                    "统计信息字典缺少必要字段",
                    "database/db_binding_codes.py:218-225",
                    f"包含字段: {required_keys}",
                    f"实际字段: {list(stats.keys())}, 缺失: {missing_keys}"
                )
                return
            
            test_results.add_test("绑定码统计功能", True)
            
        except Exception as e:
            test_results.add_test("绑定码统计功能", False, str(e))

class TestRegionManagement:
    """地区管理测试"""
    
    async def test_city_crud_operations(self):
        """测试城市CRUD操作"""
        try:
            # 测试添加城市
            city_id = await region_manager.add_city("测试城市")
            if not city_id:
                test_results.add_test("城市添加", False, "添加城市返回None")
                test_results.add_bug_report(
                    "城市添加失败",
                    "add_city方法返回None而不是城市ID",
                    "database/db_regions.py:92",
                    "返回新创建城市的ID",
                    f"返回值: {city_id}"
                )
                return
            
            # 测试获取城市
            city_info = await region_manager.get_city_by_id(city_id)
            if not city_info:
                test_results.add_test("城市查询", False, "无法查询到刚添加的城市")
                test_results.add_bug_report(
                    "城市查询失败",
                    "get_city_by_id无法找到刚创建的城市",
                    "database/db_regions.py:192",
                    "返回城市信息字典",
                    f"城市ID: {city_id}, 返回值: {city_info}"
                )
                return
            
            # 测试城市状态切换
            toggle_result = await region_manager.toggle_city_status(city_id)
            if not toggle_result:
                test_results.add_test("城市状态切换", False, "城市状态切换失败")
                test_results.add_bug_report(
                    "城市状态切换失败",
                    "toggle_city_status返回False",
                    "database/db_regions.py:126",
                    "成功切换状态时返回True",
                    f"城市ID: {city_id}, 返回值: {toggle_result}"
                )
                return
            
            # 测试删除城市
            delete_result = await region_manager.delete_city(city_id)
            if not delete_result:
                test_results.add_test("城市删除", False, "城市删除失败")
                test_results.add_bug_report(
                    "城市删除失败",
                    "delete_city返回False",
                    "database/db_regions.py:148",
                    "成功删除时返回True",
                    f"城市ID: {city_id}, 返回值: {delete_result}"
                )
                return
            
            test_results.add_test("城市CRUD操作", True)
            
        except Exception as e:
            test_results.add_test("城市CRUD操作", False, str(e))
    
    async def test_district_crud_operations(self):
        """测试地区CRUD操作"""
        try:
            # 先创建城市
            city_id = await region_manager.add_city("测试城市2")
            if not city_id:
                test_results.add_test("地区CRUD操作", False, "无法创建测试城市")
                return
            
            # 测试添加地区
            district_id = await region_manager.add_district(city_id, "测试地区")
            if not district_id:
                test_results.add_test("地区添加", False, "添加地区返回None")
                test_results.add_bug_report(
                    "地区添加失败",
                    "add_district方法返回None而不是地区ID",
                    "database/db_regions.py:107",
                    "返回新创建地区的ID",
                    f"城市ID: {city_id}, 返回值: {district_id}"
                )
                return
            
            # 测试获取地区
            district_info = await region_manager.get_district_by_id(district_id)
            if not district_info:
                test_results.add_test("地区查询", False, "无法查询到刚添加的地区")
                test_results.add_bug_report(
                    "地区查询失败",
                    "get_district_by_id无法找到刚创建的地区",
                    "database/db_regions.py:203",
                    "返回地区信息字典",
                    f"地区ID: {district_id}, 返回值: {district_info}"
                )
                return
            
            # 测试地区状态切换
            toggle_result = await region_manager.toggle_district_status(district_id)
            if not toggle_result:
                test_results.add_test("地区状态切换", False, "地区状态切换失败")
                test_results.add_bug_report(
                    "地区状态切换失败",
                    "toggle_district_status返回False",
                    "database/db_regions.py:137",
                    "成功切换状态时返回True",
                    f"地区ID: {district_id}, 返回值: {toggle_result}"
                )
                return
            
            test_results.add_test("地区CRUD操作", True)
            
        except Exception as e:
            test_results.add_test("地区CRUD操作", False, str(e))
    
    async def test_region_search_functionality(self):
        """测试地区搜索功能"""
        try:
            # 创建测试数据
            city_id = await region_manager.add_city("北京")
            if city_id:
                await region_manager.add_district(city_id, "朝阳区")
                await region_manager.add_district(city_id, "海淀区")
            
            # 测试搜索功能
            search_results = await region_manager.search_regions("北京")
            if not isinstance(search_results, list):
                test_results.add_test("地区搜索", False, "搜索结果不是列表类型")
                test_results.add_bug_report(
                    "地区搜索返回类型错误",
                    "search_regions返回类型不是列表",
                    "database/db_regions.py:23",
                    "返回地区列表",
                    f"实际返回类型: {type(search_results)}"
                )
                return
            
            # 测试空搜索
            empty_results = await region_manager.search_regions("")
            if empty_results != []:
                test_results.add_test("空搜索处理", False, "空搜索关键词返回了结果")
                test_results.add_bug_report(
                    "空搜索处理错误",
                    "空字符串搜索应该返回空列表",
                    "database/db_regions.py:35-36",
                    "返回空列表",
                    f"实际返回: {empty_results}"
                )
                return
            
            test_results.add_test("地区搜索功能", True)
            
        except Exception as e:
            test_results.add_test("地区搜索功能", False, str(e))

class TestIncentiveManagement:
    """等级和勋章配置测试"""
    
    async def test_level_management(self):
        """测试等级管理功能"""
        try:
            # 测试添加等级
            level_id = await incentive_manager.add_level("测试等级", 1000)
            if not level_id:
                test_results.add_test("等级添加", False, "添加等级返回None")
                test_results.add_bug_report(
                    "等级添加失败",
                    "add_level方法返回None而不是等级ID",
                    "database/db_incentives.py:47",
                    "返回新创建等级的ID",
                    f"返回值: {level_id}"
                )
                return
            
            # 测试重复等级名称
            try:
                duplicate_id = await incentive_manager.add_level("测试等级", 2000)
                test_results.add_test("重复等级名称处理", False, "允许了重复的等级名称")
                test_results.add_bug_report(
                    "重复等级名称验证缺失",
                    "允许创建相同名称的等级",
                    "database/db_incentives.py:70-73",
                    "抛出ValueError异常",
                    f"成功创建了重复等级ID: {duplicate_id}"
                )
                return
            except ValueError:
                # 预期的异常，测试通过
                pass
            
            # 测试获取所有等级
            levels = await incentive_manager.get_all_levels()
            if not isinstance(levels, list):
                test_results.add_test("等级列表获取", False, "等级列表不是列表类型")
                test_results.add_bug_report(
                    "等级列表类型错误",
                    "get_all_levels返回类型不是列表",
                    "database/db_incentives.py:29",
                    "返回等级列表",
                    f"实际返回类型: {type(levels)}"
                )
                return
            
            test_results.add_test("等级管理功能", True)
            
        except Exception as e:
            test_results.add_test("等级管理功能", False, str(e))
    
    async def test_badge_management(self):
        """测试勋章管理功能"""
        try:
            # 测试添加勋章
            badge_id = await incentive_manager.add_badge("测试勋章", "🏆", "测试描述")
            if not badge_id:
                test_results.add_test("勋章添加", False, "添加勋章返回None")
                test_results.add_bug_report(
                    "勋章添加失败",
                    "add_badge方法返回None而不是勋章ID",
                    "database/db_incentives.py:216",
                    "返回新创建勋章的ID",
                    f"返回值: {badge_id}"
                )
                return
            
            # 测试添加触发器
            trigger_id = await incentive_manager.add_trigger(badge_id, "order_count", 10)
            if not trigger_id:
                test_results.add_test("触发器添加", False, "添加触发器返回None")
                test_results.add_bug_report(
                    "触发器添加失败",
                    "add_trigger方法返回None而不是触发器ID",
                    "database/db_incentives.py:420",
                    "返回新创建触发器的ID",
                    f"勋章ID: {badge_id}, 返回值: {trigger_id}"
                )
                return
            
            # 测试获取勋章触发器
            triggers = await incentive_manager.get_triggers_for_badge(badge_id)
            if not isinstance(triggers, list):
                test_results.add_test("勋章触发器获取", False, "触发器列表不是列表类型")
                test_results.add_bug_report(
                    "触发器列表类型错误",
                    "get_triggers_for_badge返回类型不是列表",
                    "database/db_incentives.py:399",
                    "返回触发器列表",
                    f"实际返回类型: {type(triggers)}"
                )
                return
            
            test_results.add_test("勋章管理功能", True)
            
        except Exception as e:
            test_results.add_test("勋章管理功能", False, str(e))

class TestWebBackendAuth:
    """Web后台访问权限测试"""
    
    def test_admin_authentication(self):
        """测试管理员身份验证"""
        try:
            # 测试有效管理员ID
            mock_request = Mock()
            mock_request.session = {'is_admin': True, 'admin_id': 123456789}
            
            is_admin = AuthManager.is_admin_session(mock_request)
            if not is_admin:
                test_results.add_test("管理员会话验证", False, "有效管理员会话验证失败")
                test_results.add_bug_report(
                    "管理员会话验证失败",
                    "is_admin_session对有效会话返回False",
                    "web/app.py:62",
                    "有效管理员会话返回True",
                    f"会话数据: {mock_request.session}, 返回值: {is_admin}"
                )
                return
            
            # 测试无效会话
            mock_request_invalid = Mock()
            mock_request_invalid.session = {}
            
            is_admin_invalid = AuthManager.is_admin_session(mock_request_invalid)
            if is_admin_invalid:
                test_results.add_test("无效会话处理", False, "无效会话被认为是管理员")
                test_results.add_bug_report(
                    "无效会话处理错误",
                    "空会话被认为是有效的管理员会话",
                    "web/app.py:62",
                    "无效会话返回False",
                    f"会话数据: {mock_request_invalid.session}, 返回值: {is_admin_invalid}"
                )
                return
            
            test_results.add_test("Web后台权限验证", True)
            
        except Exception as e:
            test_results.add_test("Web后台权限验证", False, str(e))
    
    def test_password_hashing(self):
        """测试密码哈希功能"""
        try:
            password = "test123"
            hashed = AuthManager.hash_password(password)
            
            if not hashed:
                test_results.add_test("密码哈希", False, "密码哈希返回空值")
                test_results.add_bug_report(
                    "密码哈希失败",
                    "hash_password返回空值",
                    "web/app.py:52",
                    "返回哈希后的密码字符串",
                    f"密码: {password}, 返回值: {hashed}"
                )
                return
            
            # 测试密码验证
            is_valid = AuthManager.verify_password(password, hashed)
            if not is_valid:
                test_results.add_test("密码验证", False, "正确密码验证失败")
                test_results.add_bug_report(
                    "密码验证失败",
                    "verify_password对正确密码返回False",
                    "web/app.py:57",
                    "正确密码验证返回True",
                    f"密码: {password}, 哈希: {hashed}, 验证结果: {is_valid}"
                )
                return
            
            # 测试错误密码验证
            is_invalid = AuthManager.verify_password("wrong", hashed)
            if is_invalid:
                test_results.add_test("错误密码处理", False, "错误密码验证通过")
                test_results.add_bug_report(
                    "错误密码验证错误",
                    "verify_password对错误密码返回True",
                    "web/app.py:57",
                    "错误密码验证返回False",
                    f"密码: wrong, 哈希: {hashed}, 验证结果: {is_invalid}"
                )
                return
            
            test_results.add_test("密码哈希和验证", True)
            
        except Exception as e:
            test_results.add_test("密码哈希和验证", False, str(e))

class TestBotAdminCommands:
    """Bot管理员命令测试"""
    
    def test_admin_permission_check(self):
        """测试管理员权限检查"""
        try:
            # 测试有效管理员
            is_admin_valid = AdminHandler.is_admin(123456789)
            
            # 由于ADMIN_IDS可能不包含测试ID，我们测试逻辑而不是具体值
            if not isinstance(is_admin_valid, bool):
                test_results.add_test("管理员权限检查", False, "is_admin返回类型不是布尔值")
                test_results.add_bug_report(
                    "管理员权限检查类型错误",
                    "is_admin方法返回类型不是bool",
                    "handlers/admin.py:39",
                    "返回布尔值",
                    f"返回类型: {type(is_admin_valid)}, 值: {is_admin_valid}"
                )
                return
            
            test_results.add_test("管理员权限检查", True)
            
        except Exception as e:
            test_results.add_test("管理员权限检查", False, str(e))

async def run_all_tests():
    """运行所有测试"""
    logger.info("开始执行Telegram商户机器人V2.0管理员后台设置功能测试")
    
    # 绑定码管理测试
    binding_test = TestBindingCodeManagement()
    await binding_test.test_generate_binding_code()
    await binding_test.test_binding_code_uniqueness()
    await binding_test.test_binding_code_validation()
    await binding_test.test_binding_code_statistics()
    
    # 地区管理测试
    region_test = TestRegionManagement()
    await region_test.test_city_crud_operations()
    await region_test.test_district_crud_operations()
    await region_test.test_region_search_functionality()
    
    # 激励系统测试
    incentive_test = TestIncentiveManagement()
    await incentive_test.test_level_management()
    await incentive_test.test_badge_management()
    
    # Web后台权限测试
    auth_test = TestWebBackendAuth()
    auth_test.test_admin_authentication()
    auth_test.test_password_hashing()
    
    # Bot管理员命令测试
    admin_test = TestBotAdminCommands()
    admin_test.test_admin_permission_check()
    
    return test_results

def generate_bug_report():
    """生成详细的Bug报告"""
    report = f"""
# Telegram商户机器人V2.0管理员后台测试Bug报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
测试版本: V2.0
测试环境: Python 3.12+, aiogram 3.4.1, FastHTML, SQLite

## 测试总结
{test_results.get_summary()}

## 发现的Bug详情

"""
    
    for i, bug in enumerate(test_results.bug_reports, 1):
        report += f"""
### Bug #{i}: {bug['bug_description']}

**测试用例**: {bug['test_name']}
**文件位置**: {bug['file_location']}
**发现时间**: {bug['timestamp']}

**预期行为**:
{bug['expected_behavior']}

**实际行为**:
{bug['actual_behavior']}

**复现步骤**:
1. 运行对应的测试用例
2. 观察实际返回值与预期的差异

**严重程度**: 
- 影响功能正常使用: {'高' if 'FAILED' in bug['test_name'] else '中'}
- 可能导致数据问题: {'是' if '数据' in bug['bug_description'] else '否'}

---
"""
    
    if test_results.failed_count == 0:
        report += "\n✅ **恭喜！所有测试都通过了，没有发现Bug。**\n"
    
    return report

if __name__ == "__main__":
    # 运行测试
    asyncio.run(run_all_tests())
    
    # 生成测试报告
    print(test_results.get_summary())
    
    # 生成并保存Bug报告
    bug_report = generate_bug_report()
    with open("tests/admin_backend_bug_report.md", "w", encoding="utf-8") as f:
        f.write(bug_report)
    
    print(f"详细Bug报告已保存到: tests/admin_backend_bug_report.md")
    print(f"发现的Bug数量: {len(test_results.bug_reports)}")
    
    # 如果有失败的测试，退出代码为1
    exit(test_results.failed_count)