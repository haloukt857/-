# -*- coding: utf-8 -*-
"""
RegionManagerV2 输入验证测试
专门测试边界条件和输入验证逻辑
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.db_regions import RegionManagerV2


async def test_input_validation():
    """测试输入验证功能"""
    print("=== 测试输入验证功能 ===\n")
    
    # 1. 测试城市名称验证
    print("1. 测试城市名称验证...")
    
    # 空字符串
    result = await RegionManagerV2.add_city('')
    assert result is None, f"空字符串应该返回None，实际返回{result}"
    print("  ✅ 空字符串验证通过")
    
    # 只有空格的字符串
    result = await RegionManagerV2.add_city('   ')
    assert result is None, f"只有空格的字符串应该返回None，实际返回{result}"
    print("  ✅ 纯空格字符串验证通过")
    
    # None值
    try:
        result = await RegionManagerV2.add_city(None)
        assert result is None, f"None值应该返回None，实际返回{result}"
        print("  ✅ None值验证通过")
    except TypeError:
        print("  ✅ None值类型检查通过（抛出TypeError）")
    
    print("✅ 城市名称验证测试完成")
    
    # 2. 测试地区名称验证
    print("\n2. 测试地区名称验证...")
    
    # 空字符串
    result = await RegionManagerV2.add_district(1, '')
    assert result is None, f"空地区名应该返回None，实际返回{result}"
    print("  ✅ 空地区名验证通过")
    
    # 只有空格的字符串
    result = await RegionManagerV2.add_district(1, '   ')
    assert result is None, f"只有空格的地区名应该返回None，实际返回{result}"
    print("  ✅ 纯空格地区名验证通过")
    
    # 无效的城市ID
    result = await RegionManagerV2.add_district(0, '测试区')
    assert result is None, f"城市ID为0应该返回None，实际返回{result}"
    print("  ✅ 无效城市ID(0)验证通过")
    
    result = await RegionManagerV2.add_district(-1, '测试区')
    assert result is None, f"城市ID为负数应该返回None，实际返回{result}"
    print("  ✅ 无效城市ID(负数)验证通过")
    
    # None的地区名
    try:
        result = await RegionManagerV2.add_district(1, None)
        assert result is None, f"None地区名应该返回None，实际返回{result}"
        print("  ✅ None地区名验证通过")
    except TypeError:
        print("  ✅ None地区名类型检查通过（抛出TypeError）")
    
    print("✅ 地区名称验证测试完成")
    

async def test_string_processing():
    """测试字符串处理功能"""
    print("\n=== 测试字符串处理功能 ===\n")
    
    from unittest.mock import patch
    from database.db_connection import db_manager
    
    # 1. 测试前后空格trimming
    print("1. 测试前后空格处理...")
    
    with patch.object(db_manager, 'get_last_insert_id', return_value=100) as mock_insert:
        # 测试城市名称trim
        result = await RegionManagerV2.add_city('  北京  ')
        assert result == 100, f"带空格的城市名应该正常处理，实际返回{result}"
        
        # 验证实际传给数据库的是trimmed的名称
        args = mock_insert.call_args[0]
        assert args[1][0] == '北京', f"应该传递trimmed的名称'北京'，实际传递'{args[1][0]}'"
        print("  ✅ 城市名称trim处理通过")
        
        # 测试地区名称trim
        result = await RegionManagerV2.add_district(1, '  朝阳区  ')
        assert result == 100, f"带空格的地区名应该正常处理，实际返回{result}"
        
        args = mock_insert.call_args[0]
        assert args[1][1] == '朝阳区', f"应该传递trimmed的地区名'朝阳区'，实际传递'{args[1][1]}'"
        print("  ✅ 地区名称trim处理通过")
    
    print("✅ 字符串处理测试完成")


async def test_extreme_inputs():
    """测试极端输入情况"""
    print("\n=== 测试极端输入情况 ===\n")
    
    from unittest.mock import patch
    from database.db_connection import db_manager
    
    # 1. 测试超长字符串
    print("1. 测试超长字符串...")
    
    with patch.object(db_manager, 'get_last_insert_id', return_value=100):
        # 1000字符的城市名
        long_city_name = 'A' * 1000
        result = await RegionManagerV2.add_city(long_city_name)
        # 应该能正常处理（数据库层面可能有长度限制）
        print(f"  超长城市名(1000字符)处理结果: {result}")
        
        # 1000字符的地区名
        long_district_name = 'B' * 1000
        result = await RegionManagerV2.add_district(1, long_district_name)
        print(f"  超长地区名(1000字符)处理结果: {result}")
    
    print("  ✅ 超长字符串测试完成")
    
    # 2. 测试特殊Unicode字符
    print("2. 测试特殊Unicode字符...")
    
    special_unicode = [
        '🏙️北京市',  # 表情符号
        '北京\n市',   # 换行符
        '北京\t市',   # 制表符
        '北\x00京',   # null字符
        '上海™市',    # 商标符号
        '深圳®市',    # 注册商标
        'test\u200btest',  # 零宽度空格
    ]
    
    with patch.object(db_manager, 'get_last_insert_id', return_value=100):
        for name in special_unicode:
            try:
                result = await RegionManagerV2.add_city(name)
                print(f"  特殊Unicode字符 '{repr(name)}': 处理结果 {result}")
            except Exception as e:
                print(f"  特殊Unicode字符 '{repr(name)}': 异常 {e}")
    
    print("  ✅ 特殊Unicode字符测试完成")
    
    # 3. 测试SQL注入尝试
    print("3. 测试SQL注入防护...")
    
    sql_injection_attempts = [
        "'; DROP TABLE cities; --",
        "' OR '1'='1",
        "北京'; INSERT INTO cities (name) VALUES ('黑客'); --",
        "' UNION SELECT * FROM cities --"
    ]
    
    with patch.object(db_manager, 'get_last_insert_id', return_value=100):
        for attempt in sql_injection_attempts:
            try:
                result = await RegionManagerV2.add_city(attempt)
                print(f"  SQL注入尝试 '{attempt[:20]}...': 处理结果 {result}")
            except Exception as e:
                print(f"  SQL注入尝试 '{attempt[:20]}...': 异常 {e}")
    
    print("  ✅ SQL注入防护测试完成")


async def test_concurrent_validation():
    """测试并发验证情况"""
    print("\n=== 测试并发验证 ===\n")
    
    # 并发测试无效输入
    print("1. 测试并发无效输入...")
    
    tasks = []
    invalid_inputs = ['', '   ', None, '  ', '\n', '\t']
    
    for invalid_input in invalid_inputs:
        try:
            if invalid_input is not None:
                task = RegionManagerV2.add_city(invalid_input)
                tasks.append(task)
        except TypeError:
            # None可能导致TypeError，这是正常的
            continue
    
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"  并发测试 {i}: 异常 {result}")
            else:
                assert result is None, f"无效输入应该返回None，实际返回{result}"
                print(f"  并发测试 {i}: 正确返回None")
    
    print("  ✅ 并发无效输入测试通过")


async def run_validation_tests():
    """运行所有验证测试"""
    print("🔍 开始运行RegionManagerV2输入验证测试...\n")
    
    try:
        # 输入验证测试
        await test_input_validation()
        
        # 字符串处理测试
        await test_string_processing()
        
        # 极端输入测试
        await test_extreme_inputs()
        
        # 并发验证测试
        await test_concurrent_validation()
        
        print("\n🎉 所有输入验证测试完成！")
        print("✅ RegionManagerV2的输入验证功能工作正常")
        
    except Exception as e:
        print(f"\n💥 验证测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(run_validation_tests())