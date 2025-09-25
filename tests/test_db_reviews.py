# -*- coding: utf-8 -*-
"""
评价系统V2测试脚本

测试ReviewManagerV2的完整功能流程
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_reviews import ReviewManagerV2

async def test_review_system_v2():
    """完整的评价系统功能测试"""
    print("=== OPERATION REVIEW SYSTEM 强制自验证 ===")
    
    test_merchant_id = 1
    test_customer_user_id = 123456789
    test_order_id = 1001
    
    # 测试1: 创建评价
    print("\n1. 测试create_review方法...")
    ratings = {
        'appearance': 8,
        'figure': 9,
        'service': 7,
        'attitude': 10,
        'environment': 8
    }
    text_review = "服务很好，环境舒适，下次还会来的！"
    
    review_id = await ReviewManagerV2.create_review(
        order_id=test_order_id,
        merchant_id=test_merchant_id,
        customer_user_id=test_customer_user_id,
        ratings=ratings,
        text_review=text_review
    )
    
    if review_id:
        print(f"✅ 创建评价成功，评价ID: {review_id}")
    else:
        print("❌ 创建评价失败")
        return False
    
    # 测试2: 获取评价详情
    print("\n2. 测试get_review_details方法...")
    review_details = await ReviewManagerV2.get_review_details(review_id)
    if review_details:
        print(f"✅ 获取评价详情成功: {review_details['status']}")
    else:
        print("❌ 获取评价详情失败")
        return False
    
    # 测试3: 获取商家的待确认评价
    print("\n3. 测试get_pending_reviews_for_merchant方法...")
    pending_reviews = await ReviewManagerV2.get_pending_reviews_for_merchant(test_merchant_id)
    if pending_reviews:
        print(f"✅ 获取待确认评价成功，数量: {len(pending_reviews)}")
    else:
        print("✅ 暂无待确认评价")
    
    # 测试4: 商家确认评价
    print("\n4. 测试confirm_review方法...")
    confirm_result = await ReviewManagerV2.confirm_review(review_id)
    if confirm_result:
        print("✅ 商家确认评价成功")
    else:
        print("❌ 商家确认评价失败")
        return False
    
    # 测试5: 获取商家的已确认评价
    print("\n5. 测试get_reviews_by_merchant方法...")
    merchant_reviews = await ReviewManagerV2.get_reviews_by_merchant(
        merchant_id=test_merchant_id,
        confirmed_only=True,
        limit=10
    )
    if merchant_reviews:
        print(f"✅ 获取商家评价成功，已确认评价数量: {len(merchant_reviews)}")
    else:
        print("✅ 商家暂无已确认评价")
    
    # 测试6: 计算并更新商家平均分
    print("\n6. 测试calculate_and_update_merchant_scores方法...")
    scores_updated = await ReviewManagerV2.calculate_and_update_merchant_scores(test_merchant_id)
    if scores_updated:
        print("✅ 商家平均分更新成功")
    else:
        print("❌ 商家平均分更新失败")
        return False
    
    # 测试7: 获取商家平均分
    print("\n7. 测试get_merchant_scores方法...")
    merchant_scores = await ReviewManagerV2.get_merchant_scores(test_merchant_id)
    if merchant_scores:
        print(f"✅ 获取商家平均分成功:")
        print(f"   颜值: {merchant_scores.get('avg_appearance', 'N/A')}")
        print(f"   身材: {merchant_scores.get('avg_figure', 'N/A')}")
        print(f"   服务: {merchant_scores.get('avg_service', 'N/A')}")
        print(f"   态度: {merchant_scores.get('avg_attitude', 'N/A')}")
        print(f"   环境: {merchant_scores.get('avg_environment', 'N/A')}")
        print(f"   总评价数: {merchant_scores.get('total_reviews_count', 0)}")
    else:
        print("✅ 商家暂无评分数据")
    
    # 测试8: 根据订单ID获取评价
    print("\n8. 测试get_review_by_order_id方法...")
    order_review = await ReviewManagerV2.get_review_by_order_id(test_order_id)
    if order_review:
        print(f"✅ 根据订单ID获取评价成功，状态: {order_review['status']}")
    else:
        print("❌ 根据订单ID获取评价失败")
        return False
    
    print("\n=== 评价系统V2完整流程验证通过 ✅ ===")
    return True

async def test_edge_cases():
    """边界情况测试"""
    print("\n=== 边界情况测试 ===")
    
    # 测试无效评分数据
    print("\n1. 测试无效评分数据...")
    invalid_ratings = {
        'appearance': 11,  # 超出范围
        'figure': 0,       # 超出范围
        'service': 'abc',  # 类型错误
        'attitude': 5,
        'environment': 8
    }
    
    review_id = await ReviewManagerV2.create_review(
        order_id=9999,
        merchant_id=1,
        customer_user_id=123456789,
        ratings=invalid_ratings
    )
    
    if review_id is None:
        print("✅ 正确拒绝了无效评分数据")
    else:
        print("❌ 未能正确验证评分数据")
        return False
    
    # 测试缺失评分维度
    print("\n2. 测试缺失评分维度...")
    incomplete_ratings = {
        'appearance': 8,
        'figure': 9,
        # 缺少service, attitude, environment
    }
    
    review_id = await ReviewManagerV2.create_review(
        order_id=9998,
        merchant_id=1,
        customer_user_id=123456789,
        ratings=incomplete_ratings
    )
    
    if review_id is None:
        print("✅ 正确拒绝了缺失维度的评分数据")
    else:
        print("❌ 未能正确验证评分完整性")
        return False
    
    # 测试不存在的评价确认
    print("\n3. 测试确认不存在的评价...")
    confirm_result = await ReviewManagerV2.confirm_review(99999)
    if not confirm_result:
        print("✅ 正确处理了不存在评价的确认请求")
    else:
        print("❌ 未能正确处理不存在的评价")
        return False
    
    print("✅ 边界情况测试通过")
    return True

if __name__ == "__main__":
    async def main():
        # 基础功能测试
        basic_test_passed = await test_review_system_v2()
        
        if not basic_test_passed:
            print("❌ 基础功能测试失败，终止测试")
            return
        
        # 边界情况测试
        edge_test_passed = await test_edge_cases()
        
        if basic_test_passed and edge_test_passed:
            print("\n🎉 OPERATION REVIEW SYSTEM 强制自验证 - 全部测试通过!")
        else:
            print("\n❌ 部分测试失败，需要修复")
    
    asyncio.run(main())