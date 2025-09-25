# -*- coding: utf-8 -*-
"""
RegionManagerV2 全面功能测试
OPERATION REGION V2 重构后的完整性验证
"""

import asyncio
import logging
import sqlite3
import sys
import os
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 导入待测试的模块
from database.db_regions import RegionManagerV2
from database.db_connection import db_manager
from path_manager import PathManager

# 配置测试日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/Users/kikk/Documents/lanyangyang/tests/region_test_report.log')
    ]
)

logger = logging.getLogger(__name__)

class RegionManagerV2ComprehensiveTest:
    """RegionManagerV2 全面测试套件"""
    
    def __init__(self):
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'errors': [],
            'test_details': []
        }
        self.start_time = datetime.now()
    
    async def run_all_tests(self):
        """运行所有测试模块"""
        logger.info("=== RegionManagerV2 全面功能测试开始 ===")
        
        # 1. 环境准备和数据库状态检查
        await self._test_environment_setup()
        
        # 2. RegionManagerV2类功能验证
        await self._test_class_methods_existence()
        
        # 3. 数据库字段兼容性测试
        await self._test_database_schema()
        
        # 4. 基础CRUD操作测试
        await self._test_basic_crud_operations()
        
        # 5. 高级功能测试
        await self._test_advanced_features()
        
        # 6. 异常场景和错误处理
        await self._test_error_handling()
        
        # 7. 性能和数据一致性
        await self._test_performance_consistency()
        
        # 生成最终报告
        await self._generate_final_report()
    
    async def _test_environment_setup(self):
        """测试环境准备和数据库状态检查"""
        logger.info("--- 1. 环境准备和数据库状态检查 ---")
        
        # 检查数据库连接
        try:
            health_check = await db_manager.health_check()
            await self._log_test_result(
                "数据库连接健康检查", 
                health_check, 
                f"数据库连接状态: {'正常' if health_check else '异常'}"
            )
        except Exception as e:
            await self._log_test_result("数据库连接健康检查", False, f"连接失败: {e}")
        
        # 检查表结构
        try:
            # 检查cities表
            cities_schema = await db_manager.fetch_all("PRAGMA table_info(cities)")
            expected_cities_fields = {'id', 'name', 'is_active', 'display_order', 'created_at'}
            actual_cities_fields = {row['name'] for row in cities_schema}
            
            cities_schema_ok = expected_cities_fields.issubset(actual_cities_fields)
            await self._log_test_result(
                "Cities表结构验证", 
                cities_schema_ok,
                f"期望字段: {expected_cities_fields}, 实际字段: {actual_cities_fields}"
            )
            
            # 检查districts表
            districts_schema = await db_manager.fetch_all("PRAGMA table_info(districts)")
            expected_districts_fields = {'id', 'city_id', 'name', 'is_active', 'display_order', 'created_at', 'updated_at'}
            actual_districts_fields = {row['name'] for row in districts_schema}
            
            districts_schema_ok = expected_districts_fields.issubset(actual_districts_fields)
            await self._log_test_result(
                "Districts表结构验证", 
                districts_schema_ok,
                f"期望字段: {expected_districts_fields}, 实际字段: {actual_districts_fields}"
            )
            
            # 检查外键约束
            districts_foreign_keys = await db_manager.fetch_all("PRAGMA foreign_key_list(districts)")
            has_city_fk = any(fk['table'] == 'cities' for fk in districts_foreign_keys)
            await self._log_test_result(
                "外键约束验证", 
                has_city_fk,
                f"Districts表外键设置: {'正确' if has_city_fk else '缺失'}"
            )
            
        except Exception as e:
            await self._log_test_result("表结构检查", False, f"检查失败: {e}")
    
    async def _test_class_methods_existence(self):
        """测试RegionManagerV2类的14个方法存在性"""
        logger.info("--- 2. RegionManagerV2类功能验证 ---")
        
        expected_methods = [
            'get_all_cities_with_districts',
            'add_city',
            'add_district', 
            'toggle_city_status',
            'toggle_district_status',
            'delete_city',
            'delete_district',
            'get_districts_by_city',
            'get_all_cities',
            'get_city_by_id',
            'get_district_by_id',
            'update_city_display_order',
            'update_district_display_order',
            'update_city_name',
            'update_district_name',
            'get_active_cities_with_districts'
        ]
        
        missing_methods = []
        for method_name in expected_methods:
            has_method = hasattr(RegionManagerV2, method_name)
            if has_method:
                is_callable = callable(getattr(RegionManagerV2, method_name))
                await self._log_test_result(
                    f"方法存在性检查: {method_name}",
                    is_callable,
                    f"方法{'可调用' if is_callable else '不可调用'}"
                )
                if not is_callable:
                    missing_methods.append(method_name)
            else:
                missing_methods.append(method_name)
                await self._log_test_result(
                    f"方法存在性检查: {method_name}",
                    False,
                    "方法不存在"
                )
        
        await self._log_test_result(
            "RegionManagerV2方法完整性",
            len(missing_methods) == 0,
            f"缺失方法: {missing_methods}" if missing_methods else "所有方法都存在"
        )
    
    async def _test_database_schema(self):
        """测试数据库字段兼容性"""
        logger.info("--- 3. 数据库字段兼容性测试 ---")
        
        try:
            # 测试display_order字段默认值
            test_city_id = await RegionManagerV2.add_city("测试排序城市")
            if test_city_id:
                city_info = await RegionManagerV2.get_city_by_id(test_city_id)
                has_display_order = 'display_order' in city_info and city_info['display_order'] == 0
                await self._log_test_result(
                    "display_order字段默认值测试",
                    has_display_order,
                    f"display_order值: {city_info.get('display_order', 'NOT_FOUND')}"
                )
                
                # 清理测试数据
                await RegionManagerV2.delete_city(test_city_id)
            
            # 测试created_at字段自动设置
            test_city_id2 = await RegionManagerV2.add_city("测试时间城市")
            if test_city_id2:
                city_info = await RegionManagerV2.get_city_by_id(test_city_id2)
                has_created_at = 'created_at' in city_info and city_info['created_at'] is not None
                await self._log_test_result(
                    "created_at字段自动设置测试",
                    has_created_at,
                    f"created_at值: {city_info.get('created_at', 'NOT_FOUND')}"
                )
                
                # 测试updated_at在districts中的自动更新
                district_id = await RegionManagerV2.add_district(test_city_id2, "测试区域")
                if district_id:
                    # 更新district名称来触发updated_at更新
                    update_success = await RegionManagerV2.update_district_name(district_id, "更新后区域")
                    district_info = await RegionManagerV2.get_district_by_id(district_id)
                    has_updated_at = 'updated_at' in district_info and district_info['updated_at'] is not None
                    await self._log_test_result(
                        "updated_at字段自动更新测试",
                        has_updated_at and update_success,
                        f"updated_at值: {district_info.get('updated_at', 'NOT_FOUND')}"
                    )
                
                # 清理测试数据
                await RegionManagerV2.delete_city(test_city_id2)
            
        except Exception as e:
            await self._log_test_result("数据库字段兼容性测试", False, f"测试失败: {e}")
    
    async def _test_basic_crud_operations(self):
        """测试基础CRUD操作"""
        logger.info("--- 4. 基础CRUD操作测试 ---")
        
        # 测试添加城市
        try:
            city_id = await RegionManagerV2.add_city("测试城市CRUD")
            await self._log_test_result(
                "添加城市操作",
                city_id is not None and city_id > 0,
                f"返回城市ID: {city_id}"
            )
            
            if city_id:
                # 测试添加地区
                district_id = await RegionManagerV2.add_district(city_id, "测试区域CRUD")
                await self._log_test_result(
                    "添加地区操作",
                    district_id is not None and district_id > 0,
                    f"返回地区ID: {district_id}"
                )
                
                # 测试查询操作
                city_info = await RegionManagerV2.get_city_by_id(city_id)
                await self._log_test_result(
                    "按ID查询城市",
                    city_info is not None and city_info['name'] == "测试城市CRUD",
                    f"查询结果: {city_info}"
                )
                
                district_info = await RegionManagerV2.get_district_by_id(district_id)
                await self._log_test_result(
                    "按ID查询地区",
                    district_info is not None and district_info['name'] == "测试区域CRUD",
                    f"查询结果: {district_info}"
                )
                
                # 测试按城市查询地区
                districts = await RegionManagerV2.get_districts_by_city(city_id)
                await self._log_test_result(
                    "按城市查询地区",
                    len(districts) > 0 and districts[0]['name'] == "测试区域CRUD",
                    f"查询到 {len(districts)} 个地区"
                )
                
                # 测试状态切换
                toggle_result = await RegionManagerV2.toggle_city_status(city_id)
                await self._log_test_result(
                    "切换城市状态",
                    toggle_result,
                    f"切换结果: {toggle_result}"
                )
                
                # 测试更新操作
                update_name_result = await RegionManagerV2.update_city_name(city_id, "更新后测试城市")
                await self._log_test_result(
                    "更新城市名称",
                    update_name_result,
                    f"更新结果: {update_name_result}"
                )
                
                # 验证更新结果
                updated_city = await RegionManagerV2.get_city_by_id(city_id)
                await self._log_test_result(
                    "验证城市名称更新",
                    updated_city['name'] == "更新后测试城市",
                    f"更新后名称: {updated_city['name']}"
                )
                
                # 测试删除操作
                delete_result = await RegionManagerV2.delete_city(city_id)
                await self._log_test_result(
                    "删除城市操作",
                    delete_result,
                    f"删除结果: {delete_result}"
                )
                
                # 验证级联删除
                deleted_city = await RegionManagerV2.get_city_by_id(city_id)
                deleted_district = await RegionManagerV2.get_district_by_id(district_id)
                await self._log_test_result(
                    "验证级联删除",
                    deleted_city is None and deleted_district is None,
                    f"城市删除后状态: {deleted_city}, 地区删除后状态: {deleted_district}"
                )
                
        except Exception as e:
            await self._log_test_result("基础CRUD操作测试", False, f"测试失败: {e}")
    
    async def _test_advanced_features(self):
        """测试高级功能"""
        logger.info("--- 5. 高级功能测试 ---")
        
        try:
            # 准备测试数据
            city1_id = await RegionManagerV2.add_city("高级测试城市1")
            city2_id = await RegionManagerV2.add_city("高级测试城市2")
            
            if city1_id and city2_id:
                # 添加地区
                district1_id = await RegionManagerV2.add_district(city1_id, "地区A")
                district2_id = await RegionManagerV2.add_district(city1_id, "地区B")
                district3_id = await RegionManagerV2.add_district(city2_id, "地区C")
                
                # 测试get_active_cities_with_districts层级结构
                active_cities = await RegionManagerV2.get_active_cities_with_districts()
                await self._log_test_result(
                    "获取活跃城市及地区层级结构",
                    len(active_cities) >= 2,
                    f"获取到 {len(active_cities)} 个活跃城市"
                )
                
                # 验证层级结构的正确性
                city1_data = next((c for c in active_cities if c['id'] == city1_id), None)
                if city1_data:
                    await self._log_test_result(
                        "城市1层级结构验证",
                        len(city1_data['districts']) == 2,
                        f"城市1包含 {len(city1_data['districts'])} 个地区"
                    )
                
                # 测试显示顺序管理
                update_order_result = await RegionManagerV2.update_city_display_order(city1_id, 100)
                await self._log_test_result(
                    "更新城市显示顺序",
                    update_order_result,
                    f"更新结果: {update_order_result}"
                )
                
                # 测试地区显示顺序管理
                district_order_result = await RegionManagerV2.update_district_display_order(district1_id, 50)
                await self._log_test_result(
                    "更新地区显示顺序",
                    district_order_result,
                    f"更新结果: {district_order_result}"
                )
                
                # 测试get_all_cities_with_districts完整功能
                all_cities = await RegionManagerV2.get_all_cities_with_districts()
                await self._log_test_result(
                    "获取所有城市及地区",
                    len(all_cities) >= 2,
                    f"获取到 {len(all_cities)} 个城市"
                )
                
                # 清理测试数据
                await RegionManagerV2.delete_city(city1_id)
                await RegionManagerV2.delete_city(city2_id)
                
        except Exception as e:
            await self._log_test_result("高级功能测试", False, f"测试失败: {e}")
    
    async def _test_error_handling(self):
        """测试异常场景和错误处理"""
        logger.info("--- 6. 异常场景和错误处理测试 ---")
        
        # 测试无效输入处理
        invalid_city_result = await RegionManagerV2.add_city("")
        await self._log_test_result(
            "空城市名称处理",
            invalid_city_result is None,
            f"空城市名称返回: {invalid_city_result}"
        )
        
        invalid_city_result2 = await RegionManagerV2.add_city(None)
        await self._log_test_result(
            "None城市名称处理",
            invalid_city_result2 is None,
            f"None城市名称返回: {invalid_city_result2}"
        )
        
        # 测试无效地区添加
        invalid_district_result = await RegionManagerV2.add_district(99999, "不存在城市的地区")
        await self._log_test_result(
            "为不存在城市添加地区",
            invalid_district_result is None,
            f"无效城市ID返回: {invalid_district_result}"
        )
        
        # 测试不存在记录的查询
        nonexistent_city = await RegionManagerV2.get_city_by_id(99999)
        await self._log_test_result(
            "查询不存在的城市",
            nonexistent_city is None,
            f"不存在城市查询结果: {nonexistent_city}"
        )
        
        nonexistent_district = await RegionManagerV2.get_district_by_id(99999)
        await self._log_test_result(
            "查询不存在的地区",
            nonexistent_district is None,
            f"不存在地区查询结果: {nonexistent_district}"
        )
        
        # 测试重复添加
        try:
            city_id = await RegionManagerV2.add_city("重复测试城市")
            if city_id:
                duplicate_city_result = await RegionManagerV2.add_city("重复测试城市")
                await self._log_test_result(
                    "重复城市名称处理",
                    duplicate_city_result is None,
                    f"重复城市添加返回: {duplicate_city_result}"
                )
                
                # 测试重复地区
                district_id = await RegionManagerV2.add_district(city_id, "重复地区")
                if district_id:
                    duplicate_district_result = await RegionManagerV2.add_district(city_id, "重复地区")
                    await self._log_test_result(
                        "重复地区名称处理",
                        duplicate_district_result is None,
                        f"重复地区添加返回: {duplicate_district_result}"
                    )
                
                # 清理
                await RegionManagerV2.delete_city(city_id)
        except Exception as e:
            await self._log_test_result("重复数据测试", False, f"测试失败: {e}")
    
    async def _test_performance_consistency(self):
        """测试性能和数据一致性"""
        logger.info("--- 7. 性能和数据一致性测试 ---")
        
        try:
            # 批量操作性能测试
            start_time = datetime.now()
            city_ids = []
            
            # 批量添加城市
            for i in range(10):
                city_id = await RegionManagerV2.add_city(f"性能测试城市{i}")
                if city_id:
                    city_ids.append(city_id)
                    
                    # 为每个城市添加地区
                    for j in range(5):
                        await RegionManagerV2.add_district(city_id, f"性能测试地区{i}-{j}")
            
            batch_time = datetime.now() - start_time
            await self._log_test_result(
                "批量操作性能测试",
                len(city_ids) == 10,
                f"添加10个城市和50个地区耗时: {batch_time.total_seconds()}秒"
            )
            
            # 测试大量数据查询性能
            query_start_time = datetime.now()
            all_cities = await RegionManagerV2.get_all_cities_with_districts()
            query_time = datetime.now() - query_start_time
            
            await self._log_test_result(
                "大量数据查询性能",
                len(all_cities) >= 10,
                f"查询{len(all_cities)}个城市及地区耗时: {query_time.total_seconds()}秒"
            )
            
            # 测试事务一致性 - 同时删除多个城市
            deletion_start_time = datetime.now()
            deletion_results = []
            for city_id in city_ids:
                result = await RegionManagerV2.delete_city(city_id)
                deletion_results.append(result)
            
            deletion_time = datetime.now() - deletion_start_time
            all_successful = all(deletion_results)
            
            await self._log_test_result(
                "批量删除操作一致性",
                all_successful,
                f"删除10个城市耗时: {deletion_time.total_seconds()}秒, 成功率: {deletion_results.count(True)}/10"
            )
            
            # 验证级联删除的完整性
            remaining_cities = await db_manager.fetch_all(
                "SELECT COUNT(*) as count FROM cities WHERE name LIKE 'performance测试城市%'"
            )
            remaining_districts = await db_manager.fetch_all(
                "SELECT COUNT(*) as count FROM districts WHERE name LIKE 'performance测试地区%'"
            )
            
            await self._log_test_result(
                "级联删除完整性验证",
                remaining_cities[0]['count'] == 0 and remaining_districts[0]['count'] == 0,
                f"剩余城市: {remaining_cities[0]['count']}, 剩余地区: {remaining_districts[0]['count']}"
            )
            
        except Exception as e:
            await self._log_test_result("性能和数据一致性测试", False, f"测试失败: {e}")
    
    async def _log_test_result(self, test_name: str, passed: bool, details: str):
        """记录测试结果"""
        if passed:
            self.test_results['passed'] += 1
            status = "✅ PASS"
            logger.info(f"{status} {test_name}: {details}")
        else:
            self.test_results['failed'] += 1
            status = "❌ FAIL"
            logger.error(f"{status} {test_name}: {details}")
            self.test_results['errors'].append(f"{test_name}: {details}")
        
        self.test_results['test_details'].append({
            'name': test_name,
            'status': status,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    async def _generate_final_report(self):
        """生成最终测试报告"""
        end_time = datetime.now()
        total_time = end_time - self.start_time
        total_tests = self.test_results['passed'] + self.test_results['failed']
        pass_rate = (self.test_results['passed'] / total_tests * 100) if total_tests > 0 else 0
        
        report = f"""
=== RegionManagerV2 全面功能测试报告 ===
测试开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
测试结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
总测试时间: {total_time.total_seconds():.2f} 秒

=== 测试统计 ===
总测试数量: {total_tests}
通过测试: {self.test_results['passed']}
失败测试: {self.test_results['failed']}
通过率: {pass_rate:.1f}%

=== 功能完整性评估 ===
"""
        
        if self.test_results['failed'] == 0:
            report += "🎉 所有测试通过！RegionManager功能完全符合OPERATION REGION V2的预期。\n"
        else:
            report += f"⚠️  发现 {self.test_results['failed']} 个问题需要修复：\n"
            for error in self.test_results['errors']:
                report += f"  - {error}\n"
        
        report += f"""
=== 与OPERATION REGION V2对比验证 ===
根据OPERATION REGION V2声称的14个方法，验证结果如下：
- 方法存在性: {'✅ 完整' if 'get_all_cities_with_districts' in [d['name'] for d in self.test_results['test_details'] if d['name'].startswith('方法存在性检查')] else '❌ 不完整'}
- 数据库字段: {'✅ 兼容' if any(d['status'] == '✅ PASS' for d in self.test_results['test_details'] if 'display_order' in d['name']) else '❌ 不兼容'}
- CRUD功能: {'✅ 正常' if any(d['status'] == '✅ PASS' for d in self.test_results['test_details'] if 'CRUD' in d['name']) else '❌ 异常'}
- 高级功能: {'✅ 可用' if any(d['status'] == '✅ PASS' for d in self.test_results['test_details'] if '层级结构' in d['name']) else '❌ 不可用'}

=== 详细测试记录 ===
"""
        
        for detail in self.test_results['test_details']:
            report += f"{detail['status']} {detail['name']}: {detail['details']}\n"
        
        logger.info(report)
        
        # 保存报告到文件
        report_path = "/Users/kikk/Documents/lanyangyang/tests/region_manager_v2_test_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"详细测试报告已保存到: {report_path}")

async def main():
    """主测试函数"""
    tester = RegionManagerV2ComprehensiveTest()
    await tester.run_all_tests()

if __name__ == '__main__':
    asyncio.run(main())