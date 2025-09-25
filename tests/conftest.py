"""
Pytest配置和共享fixtures
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
from aiogram import Bot
from aiogram.types import User, Chat, Message, CallbackQuery, Update

from database.db_connection import DatabaseManager
from config import MESSAGE_TEMPLATES, BUTTON_TEMPLATES


@pytest.fixture(scope="session")
def event_loop():
    """创建会话级事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def temp_db():
    """创建临时内存数据库"""
    # 创建临时文件用于测试数据库
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    db_path = temp_file.name
    
    # 初始化数据库
    async with aiosqlite.connect(db_path) as db:
        # 创建商家表
        await db.execute('''
            CREATE TABLE merchants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                region TEXT,
                category TEXT,
                contact_info TEXT,
                profile_data JSON,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建订单表
        await db.execute('''
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                merchant_id INTEGER NOT NULL,
                order_type TEXT NOT NULL,
                price DECIMAL(10,2),
                appointment_time TIMESTAMP,
                completion_time TIMESTAMP,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (merchant_id) REFERENCES merchants(id)
            )
        ''')
        
        # 创建绑定码表
        await db.execute('''
            CREATE TABLE binding_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                used_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (used_by) REFERENCES merchants(id)
            )
        ''')
        
        # 创建按钮配置表
        await db.execute('''
            CREATE TABLE button_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                message_text TEXT,
                message_image TEXT,
                buttons JSON,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建活动日志表
        await db.execute('''
            CREATE TABLE activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT NOT NULL,
                details JSON,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建FSM状态表
        await db.execute('''
            CREATE TABLE fsm_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                data JSON,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        await db.commit()
    
    yield db_path
    
    # 清理临时文件
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
async def db_manager(temp_db):
    """创建数据库管理器实例"""
    manager = DatabaseManager(temp_db)
    await manager.initialize()
    
    yield manager
    
    await manager.close()


@pytest.fixture
def mock_bot():
    """创建模拟Bot实例"""
    bot = AsyncMock(spec=Bot)
    bot.token = "test_token"
    bot.session = AsyncMock()
    
    # 模拟get_me方法
    mock_user = MagicMock()
    mock_user.username = "test_bot"
    mock_user.full_name = "Test Bot"
    bot.get_me.return_value = mock_user
    
    return bot


@pytest.fixture
def mock_user():
    """创建模拟用户对象"""
    return User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="zh"
    )


@pytest.fixture
def mock_admin_user():
    """创建模拟管理员用户对象"""
    return User(
        id=987654321,
        is_bot=False,
        first_name="Admin",
        last_name="User",
        username="admin",
        language_code="zh"
    )


@pytest.fixture
def mock_chat():
    """创建模拟聊天对象"""
    return Chat(
        id=-1001234567890,
        type="private"
    )


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """创建模拟消息对象"""
    message = AsyncMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.text = "/start"
    message.message_id = 1
    message.date = 1234567890
    
    return message


@pytest.fixture
def mock_callback_query(mock_user, mock_message):
    """创建模拟回调查询对象"""
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = mock_user
    callback.message = mock_message
    callback.data = "test_callback"
    callback.id = "callback_123"
    
    return callback


@pytest.fixture
def sample_merchant_data():
    """示例商家数据"""
    return {
        "chat_id": 111222333,
        "name": "测试商家",
        "region": "北京",
        "category": "教育培训",
        "contact_info": "微信：test123",
        "profile_data": {
            "description": "专业教育培训服务",
            "services": ["英语培训", "数学辅导"],
            "price_range": "100-500元/小时"
        }
    }


@pytest.fixture
def sample_order_data():
    """示例订单数据"""
    return {
        "user_id": 123456789,
        "username": "@testuser",
        "merchant_id": 1,
        "order_type": "appointment",
        "price": 200.00,
        "appointment_time": "2024-12-01 10:00:00"
    }


@pytest.fixture
def sample_binding_code_data():
    """示例绑定码数据"""
    return {
        "code": "TEST123456",
        "expires_at": "2024-12-31 23:59:59"
    }


class AsyncContextManagerMock:
    """异步上下文管理器模拟"""
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_aiosqlite_connect():
    """模拟aiosqlite.connect"""
    mock_connection = AsyncMock()
    mock_cursor = AsyncMock()
    
    # 设置游标方法
    mock_connection.execute.return_value = mock_cursor
    mock_connection.executemany.return_value = mock_cursor
    mock_connection.cursor.return_value = mock_cursor
    
    # 设置fetchone和fetchall方法
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    
    return AsyncContextManagerMock(mock_connection)


@pytest.fixture
def config_override(monkeypatch):
    """覆盖配置用于测试"""
    test_config = {
        "ADMIN_IDS": [987654321],
        "BOT_TOKEN": "test_token",
        "MESSAGE_TEMPLATES": MESSAGE_TEMPLATES.copy(),
        "BUTTON_TEMPLATES": BUTTON_TEMPLATES.copy()
    }
    
    for key, value in test_config.items():
        monkeypatch.setattr(f"config.{key}", value)
    
    return test_config