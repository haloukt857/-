#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时发布系统测试
测试APScheduler配置和定时任务功能
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

def test_scheduler_dependencies():
    """测试定时任务相关依赖"""
    print("📋 测试定时发布系统依赖和配置")
    
    results = {
        "apscheduler_available": False,
        "config_exists": False,
        "scheduler_logic": False,
        "recommendations": []
    }
    
    # 1. 检查APScheduler是否可用
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        results["apscheduler_available"] = True
        print("✅ APScheduler依赖可用")
    except ImportError as e:
        print(f"❌ APScheduler依赖缺失: {e}")
        results["recommendations"].append("安装APScheduler: pip install APScheduler")
    
    # 2. 检查配置文件中的定时任务设置
    try:
        from config import BINDING_FLOW_CONFIG
        if BINDING_FLOW_CONFIG:
            results["config_exists"] = True
            print("✅ 项目配置文件存在")
    except Exception as e:
        print(f"⚠️ 配置文件检查: {e}")
    
    # 3. 检查是否有定时发布相关的逻辑文件
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scheduler_files = [
        "scheduler.py",
        "services/scheduler.py", 
        "background/scheduler.py",
        "tasks/scheduler.py",
        "workers/scheduler.py"
    ]
    
    found_scheduler = False
    for file_path in scheduler_files:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print(f"✅ 找到定时任务文件: {file_path}")
            found_scheduler = True
            break
    
    if not found_scheduler:
        print("⚠️ 未找到专门的定时任务文件")
        results["recommendations"].append("创建定时任务模块 (如 services/scheduler.py)")
    
    results["scheduler_logic"] = found_scheduler
    
    # 4. 检查merchants表中是否有发布时间相关字段
    try:
        from database.db_connection import db_manager
        import asyncio
        
        async def check_time_fields():
            fields = await db_manager.fetch_all("PRAGMA table_info(merchants)")
            field_names = [field['name'] for field in fields]
            
            time_fields = ['publish_time', 'expiration_time', 'scheduled_time']
            found_fields = [f for f in time_fields if f in field_names]
            
            if found_fields:
                print(f"✅ 发现时间相关字段: {found_fields}")
                return True
            else:
                print("⚠️ merchants表缺少时间相关字段")
                results["recommendations"].append("在merchants表中添加 publish_time 和 expiration_time 字段")
                return False
        
        has_time_fields = asyncio.run(check_time_fields())
        
    except Exception as e:
        print(f"❌ 数据库字段检查失败: {e}")
        has_time_fields = False
    
    # 5. 生成定时发布系统设计建议
    print("\n📊 定时发布系统测试总结:")
    print("="*50)
    
    if results["apscheduler_available"]:
        print("✅ APScheduler依赖就绪")
    else:
        print("❌ 需要安装APScheduler")
    
    if results["config_exists"]:
        print("✅ 项目配置结构正常")
    else:
        print("❌ 配置文件需要完善")
    
    if results["scheduler_logic"]:
        print("✅ 发现定时任务相关文件")
    else:
        print("⚠️ 缺少定时任务实现")
    
    if has_time_fields:
        print("✅ 数据库时间字段支持")
    else:
        print("⚠️ 数据库结构需要完善")
    
    print("\n🚀 建议实现的定时发布功能:")
    print("1. 自动扫描 status='approved' 且到达 publish_time 的商户")
    print("2. 将这些商户的状态更新为 'published'")
    print("3. 发送到频道/群组")
    print("4. 定期检查 expiration_time 并更新过期状态")
    print("5. 错误重试机制和日志记录")
    
    if results["recommendations"]:
        print("\n📝 实施建议:")
        for i, rec in enumerate(results["recommendations"], 1):
            print(f"{i}. {rec}")
    
    return results

if __name__ == "__main__":
    test_scheduler_dependencies()