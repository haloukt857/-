"""
生产环境入口文件 - ASGI统一架构
用于Railway等云平台部署，使用ASGI服务器整合机器人webhook和FastHTML管理面板
"""

import os
import signal
import logging
import asyncio
import uvicorn
import threading
from typing import Optional

# 设置生产环境日志 - 支持环境变量控制日志级别
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入数据库初始化器
from database.db_init import DatabaseInitializer

async def initialize_database():
    """初始化数据库 - 执行必要的schema迁移"""
    try:
        logger.info("🔧 生产环境数据库初始化...")
        
        db_initializer = DatabaseInitializer()
        success = await db_initializer.initialize_database()
        
        if success:
            logger.info("✅ 数据库初始化成功")
            return True
        else:
            logger.error("❌ 数据库初始化失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ 数据库初始化异常: {e}")
        return False

# 全局服务器引用，用于优雅关闭
_server: Optional[uvicorn.Server] = None
_shutdown_event = threading.Event()

def setup_signal_handlers():
    """设置信号处理器，实现优雅关闭"""
    def signal_handler(signum, frame):
        signal_name = signal.Signals(signum).name
        logger.info(f"🛑 收到信号 {signal_name}，开始优雅关闭...")
        
        if _server:
            logger.info("📱 正在关闭ASGI服务器...")
            _shutdown_event.set()
            # 通知服务器关闭
            _server.should_exit = True
            if hasattr(_server, 'force_exit'):
                # 等待一段时间后强制退出
                def force_exit_later():
                    import time
                    time.sleep(10)  # 给10秒时间优雅关闭
                    if not _shutdown_event.is_set():
                        logger.warning("⚠️ 优雅关闭超时，强制退出")
                        _server.force_exit = True
                
                threading.Thread(target=force_exit_later, daemon=True).start()
        else:
            logger.info("🔥 直接退出进程")
            os._exit(0)
    
    # 注册信号处理器
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # 如果支持，也处理其他信号
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)

async def graceful_shutdown():
    """优雅关闭处理"""
    logger.info("🧹 执行清理操作...")
    try:
        # 清理数据库连接
        from database.db_connection import db_manager
        if hasattr(db_manager, 'close'):
            await db_manager.close()
            logger.info("✅ 数据库连接已关闭")
    except Exception as e:
        logger.error(f"❌ 清理过程中出错: {e}")
    finally:
        _shutdown_event.set()
        logger.info("✅ 优雅关闭完成")

def main():
    """主函数 - 先初始化数据库，再启动ASGI服务器"""
    global _server
    
    # 设置信号处理器
    setup_signal_handlers()
    
    try:
        # 先执行数据库初始化（包含自动schema迁移）
        logger.info("🚀 生产环境启动序列...")
        
        # 执行数据库初始化
        database_success = asyncio.run(initialize_database())
        if not database_success:
            logger.error("❌ 数据库初始化失败，停止启动")
            raise RuntimeError("Database initialization failed")
        
        # 数据库初始化成功后，再导入ASGI应用
        logger.info("📱 导入ASGI应用...")
        from asgi_app import app
        
        # 获取端口号（Railway会设置PORT环境变量）
        port = int(os.getenv("PORT", 8080))
        host = os.getenv("HOST", "0.0.0.0")
        
        logger.info("✅ 启动ASGI统一架构服务器...", extra={
            "environment": os.getenv("RAILWAY_ENVIRONMENT", "unknown"),
            "host": host,
            "port": port,
            "server": "uvicorn",
            "database_initialized": True
        })
        
        # 创建Uvicorn服务器配置
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=log_level_str.lower(),
            access_log=True,
            # 优雅关闭配置
            timeout_keep_alive=5,
            timeout_graceful_shutdown=30
        )
        
        # 创建服务器实例
        _server = uvicorn.Server(config)
        
        # 注册关闭处理器
        async def lifespan_wrapper():
            try:
                await _server.serve()
            finally:
                await graceful_shutdown()
        
        # 启动服务器
        asyncio.run(lifespan_wrapper())
        
    except KeyboardInterrupt:
        logger.info("🛑 收到键盘中断，正在关闭...")
    except Exception as e:
        logger.error(f"❌ ASGI服务器启动失败: {e}")
        raise
    finally:
        logger.info("🏁 服务器已完全关闭")

if __name__ == "__main__":
    main()