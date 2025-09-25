#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
频道订阅验证配置初始化脚本
为系统初始化默认的订阅验证配置
"""

import asyncio
import json
import logging
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_system_config import system_config_manager

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_SUBSCRIPTION_CONFIG = {
    "enabled": False,  # 默认禁用，管理员可以在Web界面启用
    "required_subscriptions": [
        # 示例配置，实际使用时需要替换为真实频道
        # {
        #     "chat_id": "@your_channel",
        #     "display_name": "官方频道", 
        #     "join_link": "https://t.me/your_channel"
        # }
    ],
    "verification_mode": "strict",  # strict: 必须订阅所有频道, flexible: 订阅任意频道即可
    "reminder_template": "❌ 您需要先关注以下频道才能使用机器人功能：",
    "cache_duration": 30,  # 用户订阅状态缓存时间（分钟）
}

async def initialize_subscription_config():
    """初始化频道订阅验证配置"""
    try:
        logger.info("开始初始化频道订阅验证配置...")
        
        # 检查是否已存在配置
        existing_config = await system_config_manager.get_config(
            'subscription_verification_config',
            None
        )
        
        if existing_config is not None:
            logger.info("频道订阅验证配置已存在，跳过初始化")
            print("✅ 频道订阅验证配置已存在")
            return
        
        # 设置默认配置
        await system_config_manager.set_config(
            'subscription_verification_config',
            DEFAULT_SUBSCRIPTION_CONFIG,
            '频道订阅验证配置 - 控制频道订阅验证功能的开关和参数'
        )
        
        logger.info("频道订阅验证配置初始化完成")
        print("✅ 频道订阅验证配置初始化成功")
        print(f"   - 状态: {'启用' if DEFAULT_SUBSCRIPTION_CONFIG['enabled'] else '禁用'}")
        print(f"   - 配置频道数: {len(DEFAULT_SUBSCRIPTION_CONFIG['required_subscriptions'])}")
        print(f"   - 验证模式: {DEFAULT_SUBSCRIPTION_CONFIG['verification_mode']}")
        
        return True
        
    except Exception as e:
        logger.error(f"初始化频道订阅验证配置失败: {e}")
        print(f"❌ 配置初始化失败: {e}")
        return False

async def update_subscription_config(enabled: bool = None, channels: list = None):
    """更新频道订阅验证配置"""
    try:
        logger.info("更新频道订阅验证配置...")
        
        # 获取当前配置
        config = await system_config_manager.get_config(
            'subscription_verification_config',
            DEFAULT_SUBSCRIPTION_CONFIG
        )
        
        # 更新配置
        if enabled is not None:
            config['enabled'] = enabled
            
        if channels is not None:
            config['required_subscriptions'] = channels
        
        # 保存配置
        await system_config_manager.set_config(
            'subscription_verification_config',
            config,
            '频道订阅验证配置'
        )
        
        logger.info("频道订阅验证配置更新完成")
        print("✅ 频道订阅验证配置更新成功")
        print(f"   - 状态: {'启用' if config['enabled'] else '禁用'}")
        print(f"   - 配置频道数: {len(config['required_subscriptions'])}")
        
        return True
        
    except Exception as e:
        logger.error(f"更新频道订阅验证配置失败: {e}")
        print(f"❌ 配置更新失败: {e}")
        return False

async def show_current_config():
    """显示当前配置"""
    try:
        config = await system_config_manager.get_config(
            'subscription_verification_config',
            None
        )
        
        if config is None:
            print("❌ 频道订阅验证配置不存在")
            return
            
        print("📺 当前频道订阅验证配置:")
        print(f"   状态: {'✅ 启用' if config.get('enabled') else '❌ 禁用'}")
        print(f"   验证模式: {config.get('verification_mode', 'strict')}")
        print(f"   缓存时间: {config.get('cache_duration', 30)} 分钟")
        
        subscriptions = config.get('required_subscriptions', [])
        if subscriptions:
            print(f"   配置频道 ({len(subscriptions)} 个):")
            for i, sub in enumerate(subscriptions, 1):
                print(f"     {i}. {sub.get('display_name', '未命名')} ({sub.get('chat_id', 'N/A')})")
        else:
            print("   配置频道: 无")
            
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        print(f"❌ 获取配置失败: {e}")

async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python initialize_subscription_config.py init          - 初始化配置")
        print("  python initialize_subscription_config.py show          - 显示当前配置")
        print("  python initialize_subscription_config.py enable        - 启用验证")
        print("  python initialize_subscription_config.py disable       - 禁用验证")
        return
    
    command = sys.argv[1].lower()
    
    if command == "init":
        await initialize_subscription_config()
    elif command == "show":
        await show_current_config()
    elif command == "enable":
        await update_subscription_config(enabled=True)
    elif command == "disable":
        await update_subscription_config(enabled=False)
    else:
        print(f"❌ 未知命令: {command}")

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行主函数
    asyncio.run(main())