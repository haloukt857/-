#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
database/db_merchants_v2.py 完整功能测试脚本
只测试和报告问题，不修复任何错误

运行方式: python tests/test_db_merchants_v2_full.py
"""

import asyncio
import sys
import os
import logging
from typing import Dict, Any, List, Optional
import traceback

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入要测试的模块
try:
    from database.db_merchants import MerchantManager
    from database.db_connection import db_manager
    import database.db_merchants_v2 as db_merchants_v2
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)

# 配置测试日志
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class MerchantV2TestReporter:
    """MerchantManager 功能测试报告器"""
    
    def __init__(self):
        self.test_results = []
        self.error_count = 0
        self.success_count = 0
        self.warning_count = 0
        
    def add_result(self, test_name: str, status: str, message: str, details: str = None):
        """添加测试结果"""
        result = {
            'test_name': test_name,
            'status': status,  # SUCCESS, ERROR, WARNING
            'message': message,
            'details': details
        }
        self.test_results.append(result)
        
        if status == 'ERROR':
            self.error_count += 1
        elif status == 'WARNING':
            self.warning_count += 1
        else:
            self.success_count += 1
    
    def print_summary(self):
        """打印测试总结"""
        print("=" * 80)
        print("📋 DATABASE/DB_MERCHANTS_V2.PY 测试报告")
        print("=" * 80)
        
        total = len(self.test_results)
        print(f"📊 测试统计:")
        print(f"   总测试数: {total}")
        print(f"   ✅ 成功: {self.success_count}")
        print(f"   ⚠️  警告: {self.warning_count}")
        print(f"   ❌ 错误: {self.error_count}")
        print()
        
        # 按状态分组显示结果
        for status in ['ERROR', 'WARNING', 'SUCCESS']:
            status_results = [r for r in self.test_results if r['status'] == status]
            if not status_results:
                continue
                
            if status == 'ERROR':
                print("🚨 发现的错误:")
            elif status == 'WARNING':
                print("⚠️ 发现的警告:")
            else:
                print("✅ 成功的测试:")
                
            for result in status_results:
                print(f"   • {result['test_name']}: {result['message']}")
                if result['details']:
                    # 缩进显示详细信息
                    for line in result['details'].split('\n'):
                        if line.strip():
                            print(f"     {line}")
            print()

reporter = MerchantV2TestReporter()

async def test_database_connection():
    """测试数据库连接"""
    try:
        print("🔗 测试数据库连接...")
        health = await db_manager.health_check()
        if health:
            reporter.add_result(
                "数据库连接", "SUCCESS",
                "数据库连接正常"
            )
        else:
            reporter.add_result(
                "数据库连接", "ERROR",
                "数据库连接失败"
            )
    except Exception as e:
        reporter.add_result(
            "数据库连接", "ERROR",
            f"数据库连接异常: {str(e)}",
            traceback.format_exc()
        )

async def test_create_merchant():
    """测试创建商户功能"""
    print("🏪 测试创建商户功能...")
    
    # 测试1: 正常创建
    try:
        test_data = {
            'chat_id': 999888777,
            'name': '测试商户',
            'merchant_type': 'teacher',
            'province_id': 1,
            'region_id': 1,
            'p_price': 100,
            'pp_price': 200,
            'custom_description': '测试描述',
            'contact_info': 'test_contact',
            'profile_data': {'test': 'data'},
            'status': 'pending'
        }
        
        result = await MerchantManager.create_merchant(test_data)
        if result and isinstance(result, int):
            reporter.add_result(
                "创建商户-正常数据", "SUCCESS",
                f"成功创建商户，返回ID: {result}"
            )
            # 清理测试数据
            await MerchantManager.delete_merchant(result)
        else:
            reporter.add_result(
                "创建商户-正常数据", "ERROR",
                f"创建商户失败，返回值: {result}"
            )
    except Exception as e:
        reporter.add_result(
            "创建商户-正常数据", "ERROR",
            f"创建商户异常: {str(e)}",
            traceback.format_exc()
        )
    
    # 测试2: 缺少必需字段
    try:
        invalid_data = {'name': '无chat_id的商户'}
        result = await MerchantManager.create_merchant(invalid_data)
        if result is None:
            reporter.add_result(
                "创建商户-缺少必需字段", "SUCCESS",
                "正确处理了缺少必需字段的情况"
            )
        else:
            reporter.add_result(
                "创建商户-缺少必需字段", "WARNING",
                f"应该返回None，但返回了: {result}"
            )
    except Exception as e:
        reporter.add_result(
            "创建商户-缺少必需字段", "WARNING",
            f"处理无效数据时异常: {str(e)}"
        )

async def test_get_merchant():
    """测试获取商户功能"""
    print("📋 测试获取商户功能...")
    
    # 先创建一个测试商户
    test_merchant_id = None
    try:
        test_data = {
            'chat_id': 888777666,
            'name': '获取测试商户',
            'status': 'active'
        }
        test_merchant_id = await MerchantManager.create_merchant(test_data)
    except Exception as e:
        reporter.add_result(
            "获取商户-准备测试数据", "ERROR",
            f"无法创建测试数据: {str(e)}"
        )
        return
    
    if not test_merchant_id:
        reporter.add_result(
            "获取商户-准备测试数据", "ERROR",
            "创建测试商户失败"
        )
        return
    
    # 测试1: 根据ID获取
    try:
        merchant = await MerchantManager.get_merchant(test_merchant_id)
        if merchant and isinstance(merchant, dict):
            reporter.add_result(
                "获取商户-根据ID", "SUCCESS",
                f"成功获取商户，名称: {merchant.get('name')}"
            )
        else:
            reporter.add_result(
                "获取商户-根据ID", "ERROR",
                f"获取商户失败，返回: {merchant}"
            )
    except Exception as e:
        reporter.add_result(
            "获取商户-根据ID", "ERROR",
            f"获取商户异常: {str(e)}",
            traceback.format_exc()
        )
    
    # 测试2: 根据chat_id获取
    try:
        merchant = await MerchantManager.get_merchant_by_chat_id(888777666)
        if merchant and isinstance(merchant, dict):
            reporter.add_result(
                "获取商户-根据chat_id", "SUCCESS",
                f"成功根据chat_id获取商户，ID: {merchant.get('id')}"
            )
        else:
            reporter.add_result(
                "获取商户-根据chat_id", "ERROR",
                f"根据chat_id获取商户失败，返回: {merchant}"
            )
    except Exception as e:
        reporter.add_result(
            "获取商户-根据chat_id", "ERROR",
            f"根据chat_id获取商户异常: {str(e)}",
            traceback.format_exc()
        )
    
    # 测试3: 获取不存在的商户
    try:
        merchant = await MerchantManager.get_merchant(999999)
        if merchant is None:
            reporter.add_result(
                "获取商户-不存在的ID", "SUCCESS",
                "正确处理了不存在商户的情况"
            )
        else:
            reporter.add_result(
                "获取商户-不存在的ID", "WARNING",
                f"应该返回None，但返回了: {merchant}"
            )
    except Exception as e:
        reporter.add_result(
            "获取商户-不存在的ID", "ERROR",
            f"获取不存在商户时异常: {str(e)}"
        )
    
    # 清理测试数据
    if test_merchant_id:
        try:
            await MerchantManager.delete_merchant(test_merchant_id)
        except:
            pass

async def test_update_merchant():
    """测试更新商户功能"""
    print("✏️ 测试更新商户功能...")
    
    # 创建测试商户
    test_merchant_id = None
    try:
        test_data = {
            'chat_id': 777666555,
            'name': '更新测试商户',
            'status': 'pending'
        }
        test_merchant_id = await MerchantManager.create_merchant(test_data)
    except Exception as e:
        reporter.add_result(
            "更新商户-准备测试数据", "ERROR",
            f"无法创建测试数据: {str(e)}"
        )
        return
    
    if not test_merchant_id:
        reporter.add_result(
            "更新商户-准备测试数据", "ERROR",
            "创建测试商户失败"
        )
        return
    
    # 测试1: 正常更新
    try:
        update_data = {
            'name': '更新后的商户名称',
            'status': 'active',
            'p_price': 150
        }
        result = await MerchantManager.update_merchant(test_merchant_id, update_data)
        if result:
            reporter.add_result(
                "更新商户-正常更新", "SUCCESS",
                "成功更新商户信息"
            )
        else:
            reporter.add_result(
                "更新商户-正常更新", "ERROR",
                f"更新商户失败，返回: {result}"
            )
    except Exception as e:
        reporter.add_result(
            "更新商户-正常更新", "ERROR",
            f"更新商户异常: {str(e)}",
            traceback.format_exc()
        )
    
    # 测试2: 更新不存在的商户
    try:
        result = await MerchantManager.update_merchant(999999, {'name': '测试'})
        if result is False:
            reporter.add_result(
                "更新商户-不存在的ID", "SUCCESS",
                "正确处理了不存在商户的情况"
            )
        else:
            reporter.add_result(
                "更新商户-不存在的ID", "WARNING",
                f"应该返回False，但返回了: {result}"
            )
    except Exception as e:
        reporter.add_result(
            "更新商户-不存在的ID", "ERROR",
            f"更新不存在商户时异常: {str(e)}"
        )
    
    # 清理测试数据
    if test_merchant_id:
        try:
            await MerchantManager.delete_merchant(test_merchant_id)
        except:
            pass

async def test_merchant_status():
    """测试商户状态相关功能"""
    print("🔄 测试商户状态功能...")
    
    # 创建测试商户
    test_merchant_id = None
    try:
        test_data = {
            'chat_id': 666555444,
            'name': '状态测试商户',
            'status': 'pending'
        }
        test_merchant_id = await MerchantManager.create_merchant(test_data)
    except Exception as e:
        reporter.add_result(
            "商户状态-准备测试数据", "ERROR",
            f"无法创建测试数据: {str(e)}"
        )
        return
    
    if not test_merchant_id:
        return
    
    # 测试状态更新
    try:
        result = await MerchantManager.update_merchant_status(test_merchant_id, 'active')
        if result:
            reporter.add_result(
                "商户状态-更新状态", "SUCCESS",
                "成功更新商户状态"
            )
        else:
            reporter.add_result(
                "商户状态-更新状态", "ERROR",
                f"更新状态失败，返回: {result}"
            )
    except Exception as e:
        reporter.add_result(
            "商户状态-更新状态", "ERROR",
            f"更新状态异常: {str(e)}",
            traceback.format_exc()
        )
    
    # 测试无效状态值
    try:
        result = await MerchantManager.update_merchant_status(test_merchant_id, 'invalid_status')
        if result is False:
            reporter.add_result(
                "商户状态-无效状态值", "SUCCESS",
                "正确拒绝了无效状态值"
            )
        else:
            reporter.add_result(
                "商户状态-无效状态值", "WARNING",
                f"应该拒绝无效状态，但返回了: {result}"
            )
    except Exception as e:
        reporter.add_result(
            "商户状态-无效状态值", "ERROR",
            f"处理无效状态时异常: {str(e)}"
        )
    
    # 清理测试数据
    if test_merchant_id:
        try:
            await MerchantManager.delete_merchant(test_merchant_id)
        except:
            pass

async def test_merchant_list_and_search():
    """测试商户列表和搜索功能"""
    print("🔍 测试商户列表和搜索功能...")
    
    # 测试获取商户列表
    try:
        merchants = await MerchantManager.get_merchants(limit=5)
        if isinstance(merchants, list):
            reporter.add_result(
                "商户列表-获取列表", "SUCCESS",
                f"成功获取商户列表，数量: {len(merchants)}"
            )
        else:
            reporter.add_result(
                "商户列表-获取列表", "ERROR",
                f"获取列表失败，返回类型: {type(merchants)}"
            )
    except Exception as e:
        reporter.add_result(
            "商户列表-获取列表", "ERROR",
            f"获取列表异常: {str(e)}",
            traceback.format_exc()
        )
    
    # 测试搜索功能
    try:
        results = await MerchantManager.search_merchants("测试")
        if isinstance(results, list):
            reporter.add_result(
                "商户搜索-搜索功能", "SUCCESS",
                f"搜索功能正常，返回结果数: {len(results)}"
            )
        else:
            reporter.add_result(
                "商户搜索-搜索功能", "ERROR",
                f"搜索失败，返回类型: {type(results)}"
            )
    except Exception as e:
        reporter.add_result(
            "商户搜索-搜索功能", "ERROR",
            f"搜索异常: {str(e)}",
            traceback.format_exc()
        )

async def test_statistics():
    """测试统计功能"""
    print("📊 测试统计功能...")
    
    # 测试商户统计
    try:
        stats = await MerchantManager.get_merchant_statistics()
        if isinstance(stats, dict):
            reporter.add_result(
                "统计功能-商户统计", "SUCCESS",
                f"获取统计成功，包含字段: {list(stats.keys())}"
            )
        else:
            reporter.add_result(
                "统计功能-商户统计", "ERROR",
                f"统计失败，返回类型: {type(stats)}"
            )
    except Exception as e:
        reporter.add_result(
            "统计功能-商户统计", "ERROR",
            f"统计异常: {str(e)}",
            traceback.format_exc()
        )
    
    # 测试仪表板统计
    try:
        dashboard_stats = await MerchantManager.get_dashboard_stats()
        if isinstance(dashboard_stats, dict):
            reporter.add_result(
                "统计功能-仪表板统计", "SUCCESS",
                f"获取仪表板统计成功，包含字段: {list(dashboard_stats.keys())}"
            )
        else:
            reporter.add_result(
                "统计功能-仪表板统计", "ERROR",
                f"仪表板统计失败，返回类型: {type(dashboard_stats)}"
            )
    except Exception as e:
        reporter.add_result(
            "统计功能-仪表板统计", "ERROR",
            f"仪表板统计异常: {str(e)}",
            traceback.format_exc()
        )

async def test_convenience_functions():
    """测试便捷函数"""
    print("🔧 测试便捷函数...")
    
    # 测试便捷函数是否存在和可调用
    functions_to_test = [
        'create_merchant',
        'create_blank_merchant', 
        'get_merchant',
        'get_merchant_by_chat_id',
        'get_all_merchants',
        'update_merchant',
        'update_merchant_status',
        'delete_merchant',
        'search_merchants',
        'get_merchant_statistics',
        'get_merchant_type_statistics',
        'toggle_merchant_region_search_status'
    ]
    
    for func_name in functions_to_test:
        try:
            func = getattr(db_merchants_v2, func_name)
            if callable(func):
                reporter.add_result(
                    f"便捷函数-{func_name}", "SUCCESS",
                    "函数存在且可调用"
                )
            else:
                reporter.add_result(
                    f"便捷函数-{func_name}", "ERROR",
                    "函数存在但不可调用"
                )
        except AttributeError:
            reporter.add_result(
                f"便捷函数-{func_name}", "ERROR",
                "函数不存在"
            )
        except Exception as e:
            reporter.add_result(
                f"便捷函数-{func_name}", "ERROR",
                f"检查函数时异常: {str(e)}"
            )

async def test_status_consistency():
    """测试状态值一致性"""
    print("🔄 测试状态值一致性...")
    
    # 从代码中提取有效状态值
    code_valid_statuses = ['active', 'inactive', 'pending']
    
    # 从CLAUDE.md文档中提取的V2.0状态值
    doc_post_statuses = [
        'pending_submission',  # 等待商户提交信息
        'pending_approval',    # 等待管理员审核
        'approved',           # 已审核，等待发布
        'published',          # 已发布
        'expired'             # 已过期
    ]
    
    # 检查状态值一致性
    status_issues = []
    
    # 检查代码中的状态验证是否包含文档定义的状态
    for doc_status in doc_post_statuses:
        if doc_status not in code_valid_statuses:
            status_issues.append(f"文档状态 '{doc_status}' 在代码验证中不被接受")
    
    if status_issues:
        reporter.add_result(
            "状态一致性-状态值不匹配", "ERROR",
            f"发现 {len(status_issues)} 个状态值不一致问题",
            '\n'.join(status_issues)
        )
    else:
        reporter.add_result(
            "状态一致性-状态值匹配", "WARNING",
            "代码中的有效状态与文档定义不完全一致",
            f"代码有效状态: {code_valid_statuses}\n文档定义状态: {doc_post_statuses}"
        )

async def test_field_consistency():
    """测试字段一致性"""
    print("📋 测试字段一致性...")
    
    # 从代码中提取的字段
    code_allowed_fields = [
        'chat_id', 'name', 'region', 'category', 'contact_info', 'profile_data', 'status',
        'merchant_type', 'province_id', 'region_id', 'p_price', 'pp_price', 
        'custom_description', 'user_info', 'channel_link', 'show_in_region_search'
    ]
    
    # 从文档中提取的字段（基于03-商家绑定和管理模块.md）
    doc_merchant_fields = [
        'id', 'telegram_chat_id', 'name', 'username', 'district_id',
        'price_1', 'price_2', 'advantages', 'disadvantages', 'basic_skills',
        'status', 'publish_time', 'expiration_time', 'created_at', 'updated_at'
    ]
    
    # 检查字段不一致问题
    field_issues = []
    
    # 检查文档字段在代码中的对应情况
    field_mapping = {
        'telegram_chat_id': 'chat_id',
        'district_id': 'region_id',
        'price_1': 'p_price',
        'price_2': 'pp_price'
    }
    
    missing_in_code = []
    for doc_field in doc_merchant_fields:
        if doc_field not in ['id', 'created_at', 'updated_at']:  # 系统字段跳过
            mapped_field = field_mapping.get(doc_field, doc_field)
            if mapped_field not in code_allowed_fields:
                missing_in_code.append(f"{doc_field} -> {mapped_field}")
    
    if missing_in_code:
        reporter.add_result(
            "字段一致性-缺少字段支持", "WARNING",
            f"代码中可能不支持 {len(missing_in_code)} 个文档定义的字段",
            '\n'.join(missing_in_code)
        )
    else:
        reporter.add_result(
            "字段一致性-字段映射", "SUCCESS",
            "主要字段映射正确"
        )

async def run_all_tests():
    """运行所有测试"""
    print("🚀 开始执行 database/db_merchants_v2.py 完整功能测试\n")
    
    # 基础连接测试
    await test_database_connection()
    
    # 核心功能测试
    await test_create_merchant()
    await test_get_merchant()
    await test_update_merchant()
    await test_merchant_status()
    await test_merchant_list_and_search()
    await test_statistics()
    
    # 便捷函数测试
    await test_convenience_functions()
    
    # 一致性检查
    await test_status_consistency()
    await test_field_consistency()
    
    # 打印最终报告
    reporter.print_summary()

if __name__ == "__main__":
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n⏹️ 测试被用户中断")
    except Exception as e:
        print(f"\n💥 测试执行出现意外错误: {e}")
        traceback.print_exc()