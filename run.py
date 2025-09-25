#!/usr/bin/env python3
"""
统一启动脚本 - 根据环境变量自动选择运行模式
支持本地开发和生产环境的统一管理

使用方法:
RUN_MODE=dev python run.py      # 本地开发模式（轮询+Web根路径）
RUN_MODE=prod python run.py     # 生产环境模式（Webhook+Web子路径）
RUN_MODE=bot python run.py      # 仅机器人模式
RUN_MODE=web python run.py      # 仅Web面板模式
"""

import os
from pathlib import Path
import sys
import time
import signal
import asyncio
import logging
import subprocess
import threading
from enum import Enum
from typing import Optional
from dotenv import load_dotenv
from pathmanager import PathManager
import socket

# 可选依赖：psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# 加载环境变量
load_dotenv(PathManager.get_env_file_path())

# 导入数据库初始化模块
try:
    from database.db_init import db_initializer
    DATABASE_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"数据库模块导入失败，将跳过数据库初始化: {e}")
    DATABASE_AVAILABLE = False

# 设置基础日志 - 支持环境变量控制日志级别
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RunMode(Enum):
    """运行模式枚举"""
    DEVELOPMENT = "dev"      # 本地开发：机器人轮询 + Web根路径
    PRODUCTION = "prod"      # 生产环境：机器人Webhook + Web子路径  
    BOT_ONLY = "bot"        # 仅机器人
    WEB_ONLY = "web"        # 仅Web面板
    

class SystemManager:
    """统一系统管理器"""
    
    def __init__(self):
        self.bot_process = None
        self.web_process = None
        self.scheduler_process = None
        self.running = True
        self.run_mode = self._detect_run_mode()
        self._shutdown_initiated = False
        self.web_restart_enabled = True
        self._web_port_in_use = False
        self.process_group_id = None
        
        # 配置运行环境
        self._configure_environment()
        # 读取重启策略
        self._configure_restart_policy()
        # 清理启动前的残留进程
        self._cleanup_existing_processes()
        
    def _detect_run_mode(self) -> RunMode:
        """检测运行模式"""
        mode_str = os.getenv("RUN_MODE", "dev").lower()
        
        # 只在真正的云端环境才自动切换，PORT不算云端环境标识
        railway_env = os.getenv("RAILWAY_ENVIRONMENT")
        heroku_env = os.getenv("DYNO")
        vercel_env = os.getenv("VERCEL_ENV")
        
        if railway_env or heroku_env or vercel_env:
            if mode_str == "dev":
                logger.info(f"检测到云端环境({railway_env or heroku_env or vercel_env})，自动切换到生产模式")
                mode_str = "prod"
        
        try:
            return RunMode(mode_str)
        except ValueError:
            logger.warning(f"未知的运行模式: {mode_str}，默认使用开发模式")
            return RunMode.DEVELOPMENT
    
    def _configure_environment(self):
        """配置环境变量"""
        if self.run_mode == RunMode.DEVELOPMENT:
            # 开发模式配置
            os.environ["USE_WEBHOOK"] = "false"
            os.environ["WEB_BASE_PATH"] = ""
            os.environ["DEBUG"] = "true"
            os.environ.setdefault("WEB_RELOAD", "true")  # 开发期默认热重载

            # 开发环境代理（仅本地调试预览用，不影响生产）
            # 优先级：DEV_PROXY_URL > 已显式设置的 HTTP(S)_PROXY/TG_PROXY > 默认本地7897
            dev_proxy = os.getenv("DEV_PROXY_URL")
            http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
            https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
            tg_proxy = os.getenv("TG_PROXY")

            # 若用户提供 DEV_PROXY_URL，则覆盖到三处代理变量
            if dev_proxy:
                os.environ.setdefault("HTTP_PROXY", dev_proxy)
                os.environ.setdefault("HTTPS_PROXY", dev_proxy)
                os.environ.setdefault("TG_PROXY", dev_proxy)
            else:
                # 未显式提供且未设置任何代理时，使用 Clash 常见端口 7897 作为本地默认
                if not (http_proxy or https_proxy or tg_proxy):
                    default_proxy = "http://127.0.0.1:7897"
                    os.environ.setdefault("HTTP_PROXY", default_proxy)
                    os.environ.setdefault("HTTPS_PROXY", default_proxy)
                    os.environ.setdefault("TG_PROXY", default_proxy)
            # 避免本地回环地址走代理
            os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
            logger.info(
                f"开发态代理: HTTP_PROXY={os.getenv('HTTP_PROXY')} | HTTPS_PROXY={os.getenv('HTTPS_PROXY')} | TG_PROXY={os.getenv('TG_PROXY')}"
            )
            
        elif self.run_mode == RunMode.PRODUCTION:
            # 生产模式配置
            os.environ["USE_WEBHOOK"] = "true"
            os.environ["WEB_BASE_PATH"] = "/admin"
            os.environ["DEBUG"] = "false"
            os.environ.setdefault("WEB_RELOAD", "false")
            
        logger.info(f"运行模式: {self.run_mode.value}")
        logger.info(f"Webhook模式: {os.getenv('USE_WEBHOOK')}")
        logger.info(f"Web基础路径: {os.getenv('WEB_BASE_PATH', '/')}")

    def _configure_restart_policy(self):
        """读取Web重启策略相关环境变量"""
        def _to_bool(v: Optional[str], default: bool = True) -> bool:
            if v is None:
                return default
            return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

        # 是否在Web子进程异常退出时自动重启（默认开启）
        self.web_restart_enabled = _to_bool(os.getenv("WEB_RESTART_ON_FAILURE"), True)
        # 是否在检测到端口被占用时直接放弃启动（默认开启，且会禁用后续重启）
        self.abort_on_port_in_use = _to_bool(os.getenv("WEB_ABORT_ON_PORT_IN_USE"), True)
        # 最大重启次数（保留原行为，可通过环境变量覆盖）
        try:
            self.web_max_restarts = int(os.getenv("WEB_MAX_RESTARTS", "3"))
        except ValueError:
            self.web_max_restarts = 3

    @staticmethod
    def _is_port_in_use(host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((host, port)) == 0
    
    def _cleanup_existing_processes(self):
        """清理启动前的残留进程"""
        print("🧹 清理残留进程...")
        
        # 1. 清理可能占用端口的进程
        ports_to_check = [8001, 8002, 8011]
        for port in ports_to_check:
            self._kill_processes_by_port(port)
        
        # 2. 清理相关的Python进程
        patterns = ['run.py', 'main.py', 'uvicorn', 'asgi_app', 'get_user_id']
        self._kill_processes_by_pattern(patterns)
        
        time.sleep(1)  # 等待进程清理完成
        print("✅ 残留进程清理完成")

    # ---------------- Bot 单实例锁 ---------------- #
    def _bot_lock_file(self) -> Path:
        return Path(PathManager.get_root_directory()) / 'data' / 'bot.pid'

    def _is_pid_alive(self, pid: int) -> bool:
        try:
            if pid <= 0:
                return False
            if PSUTIL_AVAILABLE:
                import psutil as _ps
                return _ps.pid_exists(pid)
            # POSIX: 向进程发送 0 信号测试
            if os.name != 'nt':
                os.kill(pid, 0)
                return True
            # Windows 简单探测
            return True
        except Exception:
            return False

    def _acquire_bot_lock(self) -> bool:
        """若已存在并存活的 bot 轮询实例，则拒绝再次启动。"""
        try:
            lock = self._bot_lock_file()
            if lock.exists():
                try:
                    pid = int(lock.read_text().strip())
                except Exception:
                    pid = -1
                if self._is_pid_alive(pid):
                    print(f"⚠️  检测到已有轮询实例(PID={pid})在运行，跳过启动Bot以避免冲突。")
                    return False
            return True
        except Exception:
            return True

    def _write_bot_lock(self, pid: int):
        try:
            lock = self._bot_lock_file()
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text(str(pid))
        except Exception:
            pass

    def _release_bot_lock(self):
        try:
            lock = self._bot_lock_file()
            if lock.exists():
                lock.unlink()
        except Exception:
            pass
    
    def _kill_processes_by_port(self, port):
        """根据端口杀死进程"""
        try:
            # 使用lsof查找占用端口的进程
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid_str in pids:
                    if pid_str:
                        try:
                            pid = int(pid_str)
                            os.kill(pid, signal.SIGKILL)
                            print(f"   ✅ 清理端口{port}占用进程: {pid}")
                        except (ValueError, ProcessLookupError):
                            pass
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # lsof不存在或超时，尝试其他方法
            pass
    
    def _kill_processes_by_pattern(self, patterns):
        """根据进程名模式杀死进程"""
        if not PSUTIL_AVAILABLE:
            # 使用简单的pkill方法
            for pattern in patterns:
                try:
                    subprocess.run(['pkill', '-f', pattern], 
                                 capture_output=True, timeout=5)
                    print(f"   ✅ 清理进程模式: {pattern}")
                except:
                    pass
            return
            
        try:
            current_pid = os.getpid()
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.pid == current_pid:
                        continue  # 跳过自己
                    
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    for pattern in patterns:
                        if pattern in cmdline and 'lanyangyang' in cmdline:
                            proc.kill()
                            print(f"   ✅ 清理进程: {proc.pid} - {pattern}")
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.debug(f"清理进程模式时出错: {e}")
    
    def _kill_process_tree(self, process):
        """彻底杀死进程树"""
        if not process:
            return
            
        try:
            if PSUTIL_AVAILABLE:
                # 使用psutil精确清理进程树
                try:
                    parent = psutil.Process(process.pid)
                    children = parent.children(recursive=True)
                    
                    # 先杀子进程
                    for child in children:
                        try:
                            child.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    # 再杀父进程
                    parent.kill()
                    
                    # 等待所有进程退出
                    gone, alive = psutil.wait_procs([parent] + children, timeout=3)
                    
                    # 强制杀死仍存活的进程
                    for proc in alive:
                        try:
                            proc.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                            
                except psutil.NoSuchProcess:
                    pass  # 进程已经结束
            else:
                # 没有psutil，使用基本方法
                try:
                    # 先尝试优雅终止
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # 超时则强制杀死
                    process.kill()
                    process.wait(timeout=2)
                
        except Exception as e:
            logger.debug(f"清理进程树时出错: {e}")
            # 最后的保险：直接kill
            try:
                process.kill()
            except:
                pass
    
    async def _initialize_database(self) -> bool:
        """初始化数据库"""
        if not DATABASE_AVAILABLE:
            print("⚠️  数据库模块不可用，跳过数据库初始化")
            return True
            
        print("🗄️  检查数据库状态...")
        try:
            # 可选：启动前强制重置数据库（开发/排障用）
            if os.getenv("DB_RESET", "").lower() in {"1", "true", "yes"}:
                from database.db_connection import db_manager as _dbm
                db_path = _dbm.db_path
                print("🧨 检测到 DB_RESET=true，执行硬重置数据库…")
                try:
                    await _dbm.close_all_connections()
                except Exception:
                    pass
                for p in (db_path, f"{db_path}-wal", f"{db_path}-shm"):
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                            print(f"   • 已删除 {p}")
                    except Exception as e:
                        print(f"   • 删除失败 {p}: {e}")

            # 执行数据库初始化
            success = await db_initializer.initialize_database()
            
            if success:
                print("✅ 数据库初始化成功")
                
                # 显示数据库统计信息
                try:
                    stats = await db_initializer.get_database_stats()
                    if stats:
                        print("📊 数据库统计:")
                        for table, count in stats.items():
                            if count > 0:
                                print(f"   - {table}: {count} 条记录")
                except Exception as e:
                    logger.warning(f"获取数据库统计失败: {e}")
                
                return True
            else:
                print("❌ 数据库初始化失败")
                return False
                
        except Exception as e:
            logger.error(f"数据库初始化异常: {e}")
            print(f"❌ 数据库初始化异常: {e}")
            return False
    
    def _validate_config(self) -> bool:
        """验证必需的配置"""
        bot_token = os.getenv("BOT_TOKEN")
        admin_ids = os.getenv("ADMIN_IDS")
        
        if not bot_token or bot_token in ["你的机器人令牌在这里", "请填入你的机器人令牌", "YOUR_BOT_TOKEN_HERE"]:
            print("❌ BOT_TOKEN未设置，请检查.env文件")
            print("   1. 从 @BotFather 获取机器人令牌")
            print("   2. 设置 BOT_TOKEN=你的令牌")
            return False
            
        if not admin_ids or admin_ids in ["你的用户ID在这里", "请填入你的用户ID", "123456789"]:
            print("⚠️  ADMIN_IDS未设置，管理员功能将被限制")  
            print("   💡 获取用户ID方法：")
            print("      1. 启动机器人：python run.py")
            print("      2. 发送 /start 给机器人")
            print("      3. 查看日志中的用户ID")
            print("      4. 设置 ADMIN_IDS=你的用户ID")
            print("   ✅ 系统将继续启动，但管理功能受限...")
            
        return True
    
    def _check_python_version(self) -> bool:
        """检查Python版本"""
        if self.run_mode in [RunMode.DEVELOPMENT, RunMode.PRODUCTION, RunMode.WEB_ONLY]:
            if sys.version_info < (3, 12):
                print("❌ Web管理面板需要Python 3.12+")
                print(f"   当前版本: {sys.version}")
                if self.run_mode != RunMode.BOT_ONLY:
                    print("   建议: 设置 RUN_MODE=bot 仅使用机器人功能")
                    return False
        return True
    
    def start_bot(self):
        """启动机器人"""
        if self.run_mode == RunMode.WEB_ONLY:
            return
            
        print("🤖 启动Telegram机器人...")
        try:
            if self.run_mode == RunMode.PRODUCTION:
                # 生产环境使用main.py
                cmd = [sys.executable, "main.py"]
                print("   模式: 生产环境 (Webhook)")
            else:
                # 开发环境直接启动机器人  
                # 单实例保护：仅轮询模式需要
                if not self._acquire_bot_lock():
                    return
                cmd = [sys.executable, "-c", """
import asyncio
import os
import logging
from dotenv import load_dotenv
from pathmanager import PathManager
load_dotenv(PathManager.get_env_file_path())

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    try:
        from bot import TelegramMerchantBot
        from config import bot_config
        bot = TelegramMerchantBot()
        
        print(f'机器人启动模式: {"Webhook" if bot_config.use_webhook else "Polling"}')
        
        if bot_config.use_webhook:
            await bot.start_webhook()
        else:
            await bot.start_polling()
    except Exception as e:
        print(f'机器人启动失败: {e}')
        import traceback
        traceback.print_exc()
        
asyncio.run(main())
"""]
                print("   模式: 本地开发 (轮询)")
            
            popen_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                # 创建新进程组，便于整体清理
                start_new_session=True if os.name != 'nt' else False
            )
            
            if os.name == 'nt':
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            
            self.bot_process = subprocess.Popen(cmd, **popen_kwargs)
            # 写入锁文件（记录子进程PID）
            try:
                self._write_bot_lock(self.bot_process.pid)
            except Exception:
                pass
            
            # 记录进程组ID
            if not self.process_group_id and os.name != 'nt':
                try:
                    self.process_group_id = os.getpgid(self.bot_process.pid)
                except:
                    pass
            
            # 在单独线程中读取输出
            def read_bot_output():
                for line in iter(self.bot_process.stdout.readline, ''):
                    if line.strip():
                        print(f"[BOT] {line.strip()}")
                        
            threading.Thread(target=read_bot_output, daemon=True).start()
            print("✅ Telegram机器人启动中...")

            # 在后台监控子进程退出时清理锁
            def watch_bot():
                if not self.bot_process:
                    return
                self.bot_process.wait()
                self._release_bot_lock()
            threading.Thread(target=watch_bot, daemon=True).start()
            
        except Exception as e:
            print(f"❌ 机器人启动失败: {e}")
    
    def start_scheduler(self):
        """可选：启动APScheduler Worker(定时发布)。
        设置环境变量 `START_SCHEDULER=true` 即可在本地与开发态一并启动。
        """
        try:
            flag = os.getenv("START_SCHEDULER", "false").strip().lower() in {"1", "true", "yes", "y", "on"}
            if not flag:
                return
            if self.scheduler_process and self.scheduler_process.poll() is None:
                return
            print("⏲️  启动调度器Worker (scheduler.py)...")
            popen_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                start_new_session=True if os.name != 'nt' else False
            )
            if os.name == 'nt':
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            self.scheduler_process = subprocess.Popen([sys.executable, "scheduler.py"], **popen_kwargs)

            def read_sched_output():
                for line in iter(self.scheduler_process.stdout.readline, ''):
                    if line.strip():
                        print(f"[SCHED] {line.strip()}")
            threading.Thread(target=read_sched_output, daemon=True).start()
            print("✅ 调度器已启动（每分钟检查并发布到频道）")
        except Exception as e:
            print(f"⚠️  调度器启动失败: {e}")

    def start_web(self):
        """启动Web管理面板"""
        if self.run_mode == RunMode.BOT_ONLY:
            return
            
        print("🌐 启动Web管理面板...")
        try:
            # 智能端口分配
            base_port = int(os.getenv("PORT", "8001"))
            if self.run_mode in [RunMode.DEVELOPMENT, RunMode.PRODUCTION]:
                # 完整模式：Web使用基础端口，机器人使用基础端口+1
                web_port = base_port
                # 设置机器人端口（用于健康检查等）
                os.environ["BOT_PORT"] = str(base_port + 1)
            else:
                # 仅Web模式：直接使用基础端口
                web_port = base_port
            
            # 设置Web端口环境变量
            os.environ["WEB_PORT"] = str(web_port)
            
            # 等待一下让机器人先启动（如果在完整模式）
            if self.run_mode in [RunMode.DEVELOPMENT, RunMode.PRODUCTION]:
                time.sleep(3)

            # 父进程先检查端口占用，必要时直接放弃启动，避免进入重启风暴
            host = "0.0.0.0"
            if self._is_port_in_use(host, web_port):
                self._web_port_in_use = True
                msg = f"端口 {web_port} 已被占用"
                print(f"[WEB] ERROR: {msg}")
                logger.error(msg)
                if self.abort_on_port_in_use:
                    print("[WEB] 已启用端口占用即放弃启动策略 (WEB_ABORT_ON_PORT_IN_USE=true)")
                    # 禁用后续重启尝试
                    self.web_restart_enabled = False
                    self.web_process = None
                    return
            
            popen_kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                # 创建新进程组，便于整体清理
                start_new_session=True if os.name != 'nt' else False
            )
            
            if os.name == 'nt':
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            enable_reload = (os.getenv("WEB_RELOAD", "false").lower() == "true") or (os.getenv("DEBUG", "false").lower() == "true")

            if enable_reload:
                # 开发期使用uvicorn CLI的 --reload（仅监听代码目录，排除 data/logs 等频繁写入目录）
                reload_dirs = [
                    'web', 'handlers', 'database', 'utils', 'services', 'asgi_app.py'
                ]
                reload_excludes = ['data/*', 'data/**', 'logs/*', 'scheduler.log', 'data/logs/*']
                cmd = [
                    sys.executable, "-m", "uvicorn",
                    "asgi_app:create_final_asgi_app", "--factory",
                    "--host", host, "--port", str(web_port),
                    "--reload", "--log-level", "warning", "--no-access-log",
                ]
                for d in reload_dirs:
                    cmd.extend(["--reload-dir", d])
                for ex in reload_excludes:
                    cmd.extend(["--reload-exclude", ex])
                self.web_process = subprocess.Popen(cmd, **popen_kwargs)
            else:
                self.web_process = subprocess.Popen([
                sys.executable, "-c", """
import os
import sys
import logging
from dotenv import load_dotenv
from pathmanager import PathManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[WEB] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv(PathManager.get_env_file_path())

def main():
    try:
        logger.info("正在启动Web管理面板...")
        
        # 导入应用模块 - 使用完整的ASGI应用（包含业务路由）
        from asgi_app import create_final_asgi_app
        logger.info("Web应用模块导入成功")
        
        import uvicorn
        logger.info("Uvicorn导入成功")
        
        # 获取配置
        web_port = int(os.getenv("WEB_PORT", "8001"))
        host = "0.0.0.0"
        
        # 再次检查端口（双保险，正常不会走到这里，因为父进程已检查）
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((host, web_port))
        sock.close()
        if result == 0:
            logger.error(f"端口 {web_port} 已被占用（子进程检测）")
            sys.exit(1)
        
        # 创建应用 - 使用完整的ASGI应用（包含业务路由）
        logger.info("创建Web应用...")
        app = create_final_asgi_app()
        logger.info("Web应用创建成功")
        
        print(f'Web面板启动在端口: {web_port}')
        
        # 启动服务器
        logger.info(f"启动Uvicorn服务器 {host}:{web_port}")
        # 是否启用热重载（开发期）
        enable_reload = (os.getenv("WEB_RELOAD", "false").lower() == "true") or (os.getenv("DEBUG", "false").lower() == "true")
        reload_kwargs = {}
        if enable_reload:
            try:
                from pathmanager import PathManager as _PM
                reload_kwargs = {
                    'reload': True,
                    'reload_dirs': [_PM.get_root_directory()],
                    'reload_delay': 0.25,
                }
            except Exception:
                reload_kwargs = {'reload': True}

        uvicorn.run(
            app,
            host=host,
            port=web_port,
            log_level="warning",  # 减少uvicorn日志噪音
            access_log=False,      # 关闭访问日志
            **reload_kwargs
        )
    except Exception as e:
        logger.error(f'Web面板启动失败: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
if __name__ == '__main__':
    main()
"""], **popen_kwargs)
            
            # 在单独线程中读取输出
            def read_web_output():
                for line in iter(self.web_process.stdout.readline, ''):
                    if line.strip() and "WARNING" not in line:
                        print(f"[WEB] {line.strip()}")
                        
            threading.Thread(target=read_web_output, daemon=True).start()
            print(f"✅ Web管理面板启动中... (端口: {web_port})")
            
        except Exception as e:
            print(f"❌ Web管理面板启动失败: {e}")
    
    def stop_all(self):
        """快速停止所有服务"""
        if self._shutdown_initiated:
            return
        
        self._shutdown_initiated = True
        print("🛑 快速停止所有服务...")
        self.running = False
        
        # 直接杀死进程，不等待
        processes_to_kill = []
        if self.bot_process:
            processes_to_kill.append(self.bot_process)
        if self.web_process:
            processes_to_kill.append(self.web_process)
        if self.scheduler_process:
            processes_to_kill.append(self.scheduler_process)
        
        for proc in processes_to_kill:
            try:
                proc.kill()  # 直接kill，不等待
            except:
                pass
        # 释放锁
        self._release_bot_lock()
        
        # 按端口强制清理，3秒超时
        try:
            for port in [8001, 8002, 8011]:
                subprocess.run(['lsof', '-ti', f':{port}'], 
                             capture_output=True, timeout=1)
                subprocess.run(['pkill', '-f', 'uvicorn'], 
                             capture_output=True, timeout=1)
        except:
            pass
        
        print("✅ 强制清理完成")
    
    def run(self):
        """运行系统"""
        def signal_handler(signum, frame):
            # 第二次按Ctrl+C直接强制退出
            if self._shutdown_initiated:
                print("\n🔥 强制退出...")
                os._exit(1)

            self._shutdown_initiated = True
            print(f"\n🛑 正在关闭系统（优雅退出）...")
            self.running = False

            def _graceful_stop(proc: subprocess.Popen | None, name: str, seconds: float = 10.0):
                if not proc:
                    return
                try:
                    if os.name != 'nt':
                        # 向进程组发送SIGINT（子进程已用 start_new_session）
                        try:
                            os.killpg(proc.pid, signal.SIGINT)
                        except Exception:
                            proc.send_signal(signal.SIGINT)
                    else:
                        # Windows: 发送CTRL_BREAK_EVENT（子进程已用CREATE_NEW_PROCESS_GROUP）
                        try:
                            proc.send_signal(signal.CTRL_BREAK_EVENT)
                        except Exception:
                            proc.terminate()
                    # 等待优雅退出
                    proc.wait(timeout=seconds)
                except subprocess.TimeoutExpired:
                    try:
                        if os.name != 'nt':
                            os.killpg(proc.pid, signal.SIGTERM)
                        else:
                            proc.terminate()
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        # 最后保险：强杀
                        try:
                            if os.name != 'nt':
                                os.killpg(proc.pid, signal.SIGKILL)
                            else:
                                proc.kill()
                        except Exception:
                            pass
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

            # 1) 优雅停止Bot与Web子进程
            _graceful_stop(self.bot_process, 'bot', seconds=10.0)
            _graceful_stop(self.web_process, 'web', seconds=8.0)
            _graceful_stop(self.scheduler_process, 'scheduler', seconds=6.0)

            # 2) 双保险：清理端口与进程残留（非致命）
            try:
                subprocess.run(['pkill', '-f', 'uvicorn'], timeout=1, capture_output=True)
            except Exception:
                pass

            # 3) 释放本地锁文件
            self._release_bot_lock()

            # 4) 释放数据库轮询锁（若仍残留且属于本机上次子进程）
            try:
                import socket as _socket
                owner = f"{_socket.gethostname()}:{self.bot_process.pid if self.bot_process else 0}"
                async def _force_release_polling_lock(expected_owner: str):
                    try:
                        from database.db_system_config import system_config_manager
                        lock = await system_config_manager.get_config('polling_lock')
                        if isinstance(lock, dict):
                            current_owner = lock.get('owner')
                            if current_owner == expected_owner:
                                await system_config_manager.delete_config('polling_lock')
                    except Exception:
                        pass
                asyncio.run(_force_release_polling_lock(owner))
            except Exception:
                pass

            print("✅ 清理完成")
            os._exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        print("🚀 启动Telegram商户机器人系统")
        print("=" * 50)
        
        # 验证配置
        if not self._validate_config():
            return
            
        # 检查Python版本
        if not self._check_python_version():
            return
        
        # 初始化数据库
        try:
            database_success = asyncio.run(self._initialize_database())
            if not database_success:
                print("❌ 数据库初始化失败，系统无法启动")
                return
        except Exception as e:
            logger.error(f"数据库初始化异常: {e}")
            print(f"❌ 数据库初始化异常: {e}")
            return
        
        # 显示配置信息
        self._show_config_info()
        
        # 启动服务
        if self.run_mode in [RunMode.DEVELOPMENT, RunMode.PRODUCTION, RunMode.BOT_ONLY]:
            self.start_bot()
            
        if self.run_mode in [RunMode.DEVELOPMENT, RunMode.WEB_ONLY]:
            self.start_web()
        
        # 可选：启动调度器（通过 START_SCHEDULER=true 控制）
        self.start_scheduler()
        
        # 等待启动完成
        if self.run_mode in [RunMode.DEVELOPMENT, RunMode.PRODUCTION]:
            print("⏳ 等待服务启动...")
            time.sleep(5)
        
        print(f"\n🎉 {self.run_mode.value}模式启动完成！")
        print("=" * 50)
        
        # 显示访问信息
        self._show_access_info()
        
        print("按 Ctrl+C 停止所有服务")
        print("=" * 50)
        
        # 保持运行
        try:
            self._keep_running()
        except KeyboardInterrupt:
            # 在这里处理是为了兼容，但主要由信号处理器处理
            if not self._shutdown_initiated:
                self.stop_all()
        finally:
            print("🏁 系统关闭完成")
    
    def _show_config_info(self):
        """显示配置信息"""
        bot_token = os.getenv("BOT_TOKEN", "")
        admin_ids = os.getenv("ADMIN_IDS", "")
        port = os.getenv("PORT", "8001")
        
        print(f"📋 配置信息:")
        print(f"   🤖 机器人令牌: {bot_token[:10]}...")
        print(f"   👤 管理员ID: {admin_ids}")
        print(f"   🌐 Web端口: {port}")
        print(f"   🎯 运行模式: {self.run_mode.value}")
        print("")
    
    def _show_access_info(self):
        """显示访问信息"""
        base_port = int(os.getenv("PORT", "8001"))
        
        if self.run_mode != RunMode.WEB_ONLY:
            print("📱 Telegram机器人:")
            if self.run_mode in [RunMode.DEVELOPMENT, RunMode.PRODUCTION]:
                bot_port = base_port + 1
                print(f"   - 机器人Webhook: http://localhost:{bot_port}/bot")
                print(f"   - 健康检查: http://localhost:{bot_port}/health")
            print("   - 发送 /start 测试基本功能")
            print("   - 发送 '上榜流程' 测试商家注册")
            print("")
        
        if self.run_mode != RunMode.BOT_ONLY:
            # 获取实际的Web端口
            web_port = os.getenv("WEB_PORT", str(base_port))
            print("🌐 Web管理面板:")
            print(f"   - 仪表板: http://localhost:{web_port}/")
            print(f"   - 商户管理: http://localhost:{web_port}/merchants")
            print(f"   - 订单管理: http://localhost:{web_port}/orders")
            print(f"   - 绑定码管理: http://localhost:{web_port}/binding-codes")
            print(f"   - 自动回复: http://localhost:{web_port}/auto-reply")
            print(f"   - 系统配置: http://localhost:{web_port}/config")
            print(f"   - 管理员密码: {os.getenv('WEB_ADMIN_PASSWORD', 'admin123')}")
            print("")
        
        # 显示端口分配说明
        if self.run_mode in [RunMode.DEVELOPMENT, RunMode.PRODUCTION]:
            print("🔧 端口分配:")
            print(f"   - Web管理面板: {os.getenv('WEB_PORT', str(base_port))}")
            print(f"   - 机器人服务: {base_port + 1}")
            print("")
    
    def _keep_running(self):
        """保持运行状态"""
        try:
            web_restart_count = 0
            max_restarts = getattr(self, "web_max_restarts", 3)
            
            while self.running:
                time.sleep(5)  # 减少检查频率，避免过度资源消耗
                
                # 检查机器人进程状态
                if self.bot_process and self.bot_process.poll() is not None:
                    print("⚠️  机器人进程意外停止")
                    if self.run_mode != RunMode.WEB_ONLY:
                        logger.error("机器人进程异常终止")
                        
                # 检查Web进程状态，并尝试重启
                if self.web_process and self.web_process.poll() is not None:
                    exit_code = self.web_process.returncode
                    print(f"⚠️  Web管理面板进程停止 (退出码: {exit_code})")
                    
                    if not self.web_restart_enabled:
                        print("⛔ 已禁用Web重启策略 (WEB_RESTART_ON_FAILURE=false)，不再尝试重启")
                        continue

                    if self.run_mode != RunMode.BOT_ONLY and web_restart_count < max_restarts:
                        print(f"🔄 尝试重启Web进程 ({web_restart_count + 1}/{max_restarts})")
                        web_restart_count += 1
                        time.sleep(2)  # 等待2秒再重启
                        self.start_web()  # 重新启动Web进程
                    else:
                        logger.error(f"Web面板进程异常终止，退出码: {exit_code}")
                        if web_restart_count >= max_restarts:
                            print(f"❌ Web进程重启次数超限({max_restarts}次)，停止重启")
                else:
                    # Web进程正常运行，重置重启计数器
                    if web_restart_count > 0:
                        web_restart_count = 0
                        
        except KeyboardInterrupt:
            # 由信号处理器处理，这里不再重复处理
            pass


def show_usage():
    """显示使用说明"""
    print("🚀 Telegram商户机器人系统 - 统一启动脚本")
    print("=" * 50)
    print("使用方法:")
    print("  RUN_MODE=dev python run.py      # 本地开发模式")
    print("  RUN_MODE=prod python run.py     # 生产环境模式")  
    print("  RUN_MODE=bot python run.py      # 仅机器人模式")
    print("  RUN_MODE=web python run.py      # 仅Web面板模式")
    print("")
    print("环境变量:")
    print("  RUN_MODE     运行模式 (dev|prod|bot|web)")
    print("  BOT_TOKEN    机器人令牌")
    print("  ADMIN_IDS    管理员ID列表")
    print("  PORT         Web服务端口")
    print("")


async def main_async():
    """异步主函数（用于生产环境）"""
    try:
        # 生产环境直接运行main.py的逻辑
        from main import main as main_main
        await main_main()
    except Exception as e:
        logger.error(f"生产环境启动失败: {e}")


def main():
    """主函数"""
    # 检查是否显示帮助
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        show_usage()
        return
    
    try:
        manager = SystemManager()
        
        # 生产环境直接使用异步模式
        if manager.run_mode == RunMode.PRODUCTION and os.getenv("RAILWAY_ENVIRONMENT"):
            asyncio.run(main_async())
        else:
            manager.run()
            
    except KeyboardInterrupt:
        print("\n👋 已停止系统")
    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        print(f"❌ 启动失败: {e}")


if __name__ == "__main__":
    main()
