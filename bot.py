"""
Telegram商家机器人主应用
集成所有处理器、中间件和配置，支持webhook和轮询模式
"""

import logging
import asyncio
import signal
import sys
import threading
from typing import Optional
import os
import socket
import time
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiohttp.web_app import Application

# 导入项目配置和组件
from config import bot_config, ADMIN_IDS, WEB_CONFIG, RATE_LIMIT, AUTO_REPLY_CONFIG, POLLING_LOCK_ENABLED
from pathmanager import PathManager
from database.db_connection import db_manager
from database.db_logs import ActivityLogsDatabase
from handlers.user import get_user_router, init_user_handler
from handlers.admin import admin_router
from handlers.merchant import get_merchant_router, init_merchant_handler
from handlers.auto_reply import get_auto_reply_router, init_auto_reply_handler
from handlers.subscription_guard import subscription_middleware
from handlers.reviews import get_reviews_router, init_reviews_handler
# from debug_handler import get_debug_router  # 文件不存在，暂时注释
from middleware import ThrottlingMiddleware, LoggingMiddleware, ErrorHandlerMiddleware
from utils import HealthMonitor
# 移除了过度复杂的安全中间件

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PathManager.get_log_file_path("bot"), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class TelegramMerchantBot:
    """Telegram商家机器人主类"""
    
    def __init__(self):
        """初始化机器人实例"""
        # 验证必要配置
        if not bot_config.token or bot_config.token == "YOUR_BOT_TOKEN_HERE":
            raise ValueError("机器人令牌未设置！请在环境变量中设置BOT_TOKEN")
        
        if not ADMIN_IDS or ADMIN_IDS == [123456789]:
            logger.warning("管理员ID未正确设置，请在环境变量中设置ADMIN_IDS")
        
        # 创建机器人实例
        self.bot = Bot(
            token=bot_config.token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        
        # 创建调度器
        self.dp = Dispatcher(storage=MemoryStorage())
        
        # 初始化数据库组件
        self.logs_db = None
        
        # 初始化监控组件
        self.health_monitor = HealthMonitor(
            self.bot,
            check_interval=60
        )
        
        # 关闭标志
        self._shutdown_event = threading.Event()
        self._is_shutting_down = False
        self._poll_lock_owner = None
        self._poll_lock_task: Optional[asyncio.Task] = None
        
        # 设置信号处理器
        self._setup_signal_handlers()
        
        # 初始化组件
        self._setup_middleware()
        self._register_handlers()
        
        logger.info(f"机器人初始化完成，使用{'Webhook' if bot_config.use_webhook else '轮询'}模式")
    
    def _setup_signal_handlers(self):
        """设置信号处理器，实现优雅关闭"""
        def signal_handler(signum, frame):
            if self._is_shutting_down:
                return  # 避免重复处理
            
            signal_name = signal.Signals(signum).name
            logger.info(f"🛑 机器人收到信号 {signal_name}，开始优雅关闭...")
            self._is_shutting_down = True
            
            # 在新线程中执行关闭操作，避免阻塞信号处理器
            def shutdown_in_thread():
                loop = None
                try:
                    # 获取当前事件循环
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    try:
                        # 如果没有运行的循环，创建新的
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    except Exception as e:
                        logger.error(f"创建事件循环失败: {e}")
                        return
                
                if loop:
                    try:
                        # 运行关闭操作
                        loop.run_until_complete(self._on_shutdown())
                        self._shutdown_event.set()
                    except Exception as e:
                        logger.error(f"优雅关闭过程中出错: {e}")
                        self._shutdown_event.set()
                    finally:
                        try:
                            # 停止事件循环
                            if loop.is_running():
                                loop.stop()
                        except Exception as e:
                            logger.debug(f"停止事件循环时出错: {e}")
            
            # 启动关闭线程
            shutdown_thread = threading.Thread(target=shutdown_in_thread, daemon=True)
            shutdown_thread.start()
            
            # 等待关闭完成，最多等待15秒
            if self._shutdown_event.wait(timeout=15):
                logger.info("✅ 机器人优雅关闭完成")
            else:
                logger.warning("⚠️ 机器人优雅关闭超时，强制退出")
            
            # 强制退出
            import os
            os._exit(0)
        
        # 注册信号处理器
        try:
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            logger.debug("✅ 信号处理器设置完成")
        except Exception as e:
            logger.warning(f"设置信号处理器失败: {e}")
    
    def _setup_middleware(self):
        """设置中间件"""
        try:
            # 1. 错误处理中间件（最外层，优先级最高）
            error_middleware = ErrorHandlerMiddleware(
                notify_admins=True,
                max_retries=3
            )
            self.dp.message.middleware(error_middleware)
            self.dp.callback_query.middleware(error_middleware)
            logger.info("错误处理中间件设置完成")
            
            # 2. 限流中间件（防止API限制）
            throttling_middleware = ThrottlingMiddleware(
                default_rate=RATE_LIMIT["default"],
                default_burst=RATE_LIMIT["burst"],
                admin_rate=RATE_LIMIT["admin"],
                cleanup_interval=300
            )
            self.dp.message.middleware(throttling_middleware)
            self.dp.callback_query.middleware(throttling_middleware)
            logger.info("限流中间件设置完成")
            
            # 3. 订阅验证中间件（对用户路由生效）
            # 注意：这里是全局注册，但中间件内部会检查管理员豁免
            self.dp.message.middleware(subscription_middleware)
            self.dp.callback_query.middleware(subscription_middleware)
            logger.info("频道订阅验证中间件设置完成")
            
            # 4. 日志记录中间件（最内层，记录所有通过的请求）
            # 注意：logs_db会在_setup_database中初始化
            logger.info("中间件设置完成（日志中间件将在数据库初始化后启用）")
            
        except Exception as e:
            logger.error(f"中间件设置失败: {e}")
            raise
    
    def _register_handlers(self):
        """注册所有处理器"""
        try:
            # 初始化处理器（需要bot实例）
            # init_user_handler(self.bot)  # 暂时跳过，避免async问题
            init_merchant_handler(self.bot)
            
            # 初始化自动回复处理器（如果启用）
            if AUTO_REPLY_CONFIG.get("enabled", True):
                init_auto_reply_handler(self.bot)
                logger.info("自动回复处理器初始化完成")
            
            # 注册处理器路由（按优先级顺序）
            # 1. 管理员处理器（最高优先级）
            self.dp.include_router(admin_router)
            logger.info("管理员处理器注册完成")
            
            # 2. 商家处理器
            merchant_router = get_merchant_router()
            self.dp.include_router(merchant_router)
            logger.info("商家处理器注册完成")

            # 3. 用户处理器
            user_router = get_user_router()
            self.dp.include_router(user_router)
            logger.info("用户处理器注册完成")

            # 4. 评价处理器（按钮+编辑模式）
            init_reviews_handler(self.bot)
            self.dp.include_router(get_reviews_router())
            logger.info("评价处理器注册完成")
            
            # 5. 自动回复处理器（最低优先级，处理剩余消息）
            if AUTO_REPLY_CONFIG.get("enabled", True):
                auto_reply_router = get_auto_reply_router()
                self.dp.include_router(auto_reply_router)
                logger.info("自动回复处理器注册完成")
            else:
                logger.info("自动回复功能已禁用，跳过注册")
            
            logger.info("所有处理器注册完成")
            
        except Exception as e:
            logger.error(f"处理器注册失败: {e}")
            raise
    
    async def _setup_database(self):
        """初始化数据库连接"""
        try:
            # 初始化数据库表结构
            from database.db_init import init_database
            success = await init_database()
            if not success:
                raise Exception("数据库表初始化失败")
            logger.info("数据库表结构初始化完成")
            
            # 初始化日志数据库
            self.logs_db = ActivityLogsDatabase()
            
            # 设置日志记录中间件（需要数据库连接）
            logging_middleware = LoggingMiddleware(self.logs_db)
            self.dp.message.middleware(logging_middleware)
            self.dp.callback_query.middleware(logging_middleware)
            logger.info("日志记录中间件设置完成")
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    async def _cleanup_database(self):
        """清理数据库连接"""
        try:
            # await db_manager.close()  # No close method available
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.error(f"数据库清理失败: {e}")
    
    async def _on_startup(self):
        """启动时的初始化操作"""
        try:
            # 初始化数据库
            await self._setup_database()
            
            # 初始化模板管理器
            from database.db_templates import template_manager
            # 模板管理器已通过db_templates初始化完成
            logger.info("模板管理器初始化完成")
            
            # 设置机器人信息
            bot_info = await self.bot.get_me()
            logger.info(f"机器人启动成功: @{bot_info.username} ({bot_info.full_name})")
            
            # 如果使用webhook模式，设置webhook
            if bot_config.use_webhook:
                webhook_url = f"{bot_config.webhook_url}{bot_config.webhook_path}"
                await self.bot.set_webhook(webhook_url)
                logger.info(f"Webhook设置完成: {webhook_url}")
            else:
                # 轮询模式，删除现有webhook并丢弃积压更新，避免与其他实例冲突
                try:
                    await self.bot.delete_webhook(drop_pending_updates=True)
                    logger.info("轮询模式启动，已删除现有webhook并丢弃积压更新")
                except Exception as e:
                    logger.warning(f"删除webhook时出现问题（已忽略）：{e}")
            
            # 启动健康监控
            asyncio.create_task(self.health_monitor.start_monitoring())
            logger.info("健康监控已启动")

            # 启动后台任务队列workers（用于异步Telegram I/O）
            try:
                from services.task_queue import start_task_workers
                await start_task_workers(worker_count=3)
                logger.info("后台任务队列已启动（bot）")
            except Exception as e:
                logger.warning(f"启动后台任务队列失败（bot）: {e}")
            
            # 通知管理员机器人启动
            startup_message = f"🤖 机器人启动成功\n\n" \
                             f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                             f"🔧 运行模式: {'Webhook' if bot_config.use_webhook else '轮询'}\n" \
                             f"🤖 机器人: @{bot_info.username}\n" \
                             f"💚 健康监控: 已启动"
            
            for admin_id in ADMIN_IDS:
                try:
                    await self.bot.send_message(admin_id, startup_message)
                except Exception as e:
                    logger.warning(f"无法向管理员 {admin_id} 发送启动通知: {e}")
            
        except Exception as e:
            logger.error(f"启动初始化失败: {e}")
            raise
    
    async def _on_shutdown(self):
        """关闭时的清理操作"""
        try:
            # 停止健康监控
            self.health_monitor.stop_monitoring()
            logger.info("健康监控已停止")
            
            # 通知管理员机器人关闭
            shutdown_message = f"🤖 机器人正在关闭\n\n" \
                              f"📅 关闭时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                              f"❤️ 健康监控: 已停止"
            
            for admin_id in ADMIN_IDS:
                try:
                    await self.bot.send_message(admin_id, shutdown_message)
                except Exception as e:
                    logger.warning(f"无法向管理员 {admin_id} 发送关闭通知: {e}")

            # 清理资源
            # 释放轮询锁（若有）
            try:
                await self._release_polling_lock()
            except Exception:
                pass
            await self._cleanup_database()
            await self.bot.session.close()
            
            logger.info("机器人关闭完成")
            
        except Exception as e:
            logger.error(f"关闭清理失败: {e}")
    
    async def start_polling(self):
        """启动轮询模式"""
        try:
            logger.info("启动轮询模式...")
            await self._on_startup()
            # 获取轮询单实例锁（可通过环境变量关闭；生产Webhook默认不启用）
            if POLLING_LOCK_ENABLED:
                lock_ok = await self._acquire_polling_lock()
                if not lock_ok:
                    logger.error("未获取到轮询锁，本实例不再启动轮询。")
                    return
            await self.dp.start_polling(self.bot, skip_updates=True)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭...")
        except Exception as e:
            logger.error(f"轮询模式运行失败: {e}")
            raise
        finally:
            await self._on_shutdown()

    # ---------------- 轮询单实例锁（跨进程/跨主机）---------------- #
    async def _acquire_polling_lock(self, ttl_seconds: int = 120) -> bool:
        """
        尝试获取轮询锁，防止同一TOKEN多实例并发轮询。
        基于 system_config 表，value 形如：{"owner": "<hostname>:<pid>", "expires_at": <unix_ts>}。
        """
        try:
            from database.db_system_config import system_config_manager

            owner = f"{socket.gethostname()}:{os.getpid()}"
            now = int(time.time())
            lock = await system_config_manager.get_config("polling_lock", None)

            if isinstance(lock, dict):
                expires_at = int(lock.get("expires_at", 0))
                current_owner = lock.get("owner") or ""
                # 检测本机上的陈旧锁（进程已不存在）
                try:
                    host, pid_str = current_owner.split(":", 1)
                except ValueError:
                    host, pid_str = "", ""
                stale_local_lock = False
                if host and pid_str.isdigit() and host == socket.gethostname():
                    try:
                        os.kill(int(pid_str), 0)
                        # 进程仍在，本机有效锁
                    except Exception:
                        # 本机进程不存在，视为陈旧锁
                        stale_local_lock = True

                if expires_at > now and current_owner and current_owner != owner and not stale_local_lock:
                    logger.error(f"检测到其他实例正在轮询（{current_owner}），本实例将退出以避免冲突")
                    return False

            # 设置/续约锁
            new_lock = {"owner": owner, "expires_at": now + ttl_seconds}
            ok = await system_config_manager.set_config(
                "polling_lock", new_lock, "Polling single-instance lock"
            )
            if ok:
                self._poll_lock_owner = owner
                # 启动续约任务
                self._poll_lock_task = asyncio.create_task(self._renew_polling_lock(ttl_seconds))
                logger.info(f"已获取轮询锁：{owner}")
                return True
            return False
        except Exception as e:
            logger.warning(f"获取轮询锁失败（忽略并继续）：{e}")
            # 若锁机制异常，不阻断启动，但可能出现冲突日志
            return True

    async def _renew_polling_lock(self, ttl_seconds: int):
        """定期续约轮询锁，保持占有权。"""
        try:
            from database.db_system_config import system_config_manager
            owner = self._poll_lock_owner
            if not owner:
                return
            while True:
                await asyncio.sleep(max(10, ttl_seconds // 2))
                now = int(time.time())
                new_lock = {"owner": owner, "expires_at": now + ttl_seconds}
                await system_config_manager.set_config(
                    "polling_lock", new_lock, "Polling single-instance lock"
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"续约轮询锁失败：{e}")

    async def _release_polling_lock(self):
        """释放轮询锁。"""
        try:
            if self._poll_lock_task:
                self._poll_lock_task.cancel()
                self._poll_lock_task = None
            from database.db_system_config import system_config_manager
            await system_config_manager.delete_config("polling_lock")
            logger.info("已释放轮询锁")
        except Exception as e:
            logger.debug(f"释放轮询锁失败（忽略）：{e}")
    
    def create_webhook_app(self) -> Application:
        """创建webhook应用"""
        try:
            # 创建aiohttp应用
            app = web.Application()
            
            # 设置webhook处理器
            webhook_requests_handler = SimpleRequestHandler(
                dispatcher=self.dp,
                bot=self.bot
            )
            webhook_requests_handler.register(app, path=bot_config.webhook_path)
            
            # 设置应用
            setup_application(app, self.dp, bot=self.bot)
            
            # 添加启动和关闭事件处理
            app.on_startup.append(lambda app: asyncio.create_task(self._on_startup()))
            app.on_cleanup.append(lambda app: asyncio.create_task(self._on_shutdown()))
            
            logger.info("Webhook应用创建完成")
            return app
            
        except Exception as e:
            logger.error(f"Webhook应用创建失败: {e}")
            raise
    
    async def start_webhook(self):
        """启动webhook模式"""
        try:
            logger.info("启动Webhook模式...")
            app = self.create_webhook_app()
            
            # 启动web服务器
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(
                runner, 
                host="0.0.0.0", 
                port=bot_config.webhook_port
            )
            
            await site.start()
            logger.info(f"Webhook服务器启动成功，监听端口: {bot_config.webhook_port}")
            
            # 保持服务器运行
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("收到中断信号，正在关闭...")
            finally:
                await runner.cleanup()
                
        except Exception as e:
            logger.error(f"Webhook模式运行失败: {e}")
            raise

def create_combined_app() -> Application:
    """创建合并的应用（机器人webhook + web管理面板）"""
    try:
        bot_instance = TelegramMerchantBot()
        
        # 创建主应用
        app = web.Application()
        
        # 添加机器人webhook处理
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=bot_instance.dp,
            bot=bot_instance.bot
        )
        webhook_requests_handler.register(app, path=bot_config.webhook_path)
        
        # 设置机器人应用
        setup_application(app, bot_instance.dp, bot=bot_instance.bot)
        
        # 添加web管理面板路由
        from web.app import app as web_app
        app.add_subapp('/admin', web_app)
        
        # 添加健康检查端点
        async def health_check(request):
            try:
                # 获取基本健康状态
                health_summary = bot_instance.health_monitor.get_health_summary()
                
                return web.json_response({
                    "status": "healthy" if health_summary.get("consecutive_failures", 0) == 0 else "degraded",
                    "timestamp": datetime.now().isoformat(),
                    "mode": "webhook" if bot_config.use_webhook else "polling",
                    "health_monitor": health_summary
                })
            except Exception as e:
                return web.json_response({
                    "status": "error",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                }, status=500)
        
        app.router.add_get('/health', health_check)
        
        # 添加根路径重定向
        async def root_redirect(request):
            return web.Response(status=302, headers={'Location': '/admin'})
        
        app.router.add_get('/', root_redirect)
        
        # 添加启动和关闭事件
        app.on_startup.append(lambda app: asyncio.create_task(bot_instance._on_startup()))
        app.on_cleanup.append(lambda app: asyncio.create_task(bot_instance._on_shutdown()))
        
        logger.info("合并应用创建完成")
        return app
        
    except Exception as e:
        logger.error(f"合并应用创建失败: {e}")
        raise

async def main():
    """主函数"""
    try:
        # 创建机器人实例
        bot_instance = TelegramMerchantBot()
        
        if bot_config.use_webhook:
            # Webhook模式（适用于生产环境）
            await bot_instance.start_webhook()
        else:
            # 轮询模式（适用于开发环境）
            await bot_instance.start_polling()
            
    except Exception as e:
        logger.error(f"机器人运行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行失败: {e}")
        sys.exit(1)
