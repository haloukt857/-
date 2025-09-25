#!/usr/bin/env python3
"""
获取Telegram用户ID的辅助脚本
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('.env')

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def get_user_id():
    """启动机器人获取用户ID"""
    try:
        bot_token = os.getenv("BOT_TOKEN")
        
        if not bot_token or bot_token == "请填入你的机器人令牌":
            print("❌ 请先在.env文件中设置BOT_TOKEN")
            return
            
        print("🤖 机器人已启动，正在等待消息...")
        print("📱 请发送任意消息给你的机器人，我会显示你的用户ID")
        print("💡 发送 /start 或任意文字消息都可以")
        print("🛑 获取用户ID后按 Ctrl+C 停止\n")
        
        from aiogram import Bot, Dispatcher
        from aiogram.types import Message
        from aiogram.filters import Command
        
        bot = Bot(token=bot_token)
        dp = Dispatcher()
        
        @dp.message()
        async def get_id(message: Message):
            user_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name
            
            print(f"🎉 找到用户信息！")
            print(f"   用户ID: {user_id}")
            print(f"   用户名: @{username}" if username else "   用户名: 无")
            print(f"   姓名: {first_name}")
            print(f"\n✅ 请将这个用户ID复制到.env文件中：")
            print(f"   ADMIN_IDS={user_id}")
            
            # 回复用户
            await message.reply(
                f"✅ 你的用户ID是: `{user_id}`\n"
                f"请将这个ID配置为管理员！",
                parse_mode="Markdown"
            )
        
        # 启动轮询
        await dp.start_polling(bot)
        
    except KeyboardInterrupt:
        print("\n👋 已停止机器人")
    except Exception as e:
        print(f"❌ 错误: {e}")
        print("请检查BOT_TOKEN是否正确")

if __name__ == "__main__":
    asyncio.run(get_user_id())