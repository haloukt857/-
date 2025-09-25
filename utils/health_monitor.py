"""
健康监控器
定期检查系统状态并触发自动恢复
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
import json

from aiogram import Bot

logger = logging.getLogger(__name__)

class HealthMonitor:
    """
    系统健康监控器
    
    特性:
    - 定期健康检查
    - 自动故障检测
    - 性能指标监控
    - 预警系统
    """
    
    def __init__(
        self, 
        bot: Bot, 
        check_interval: int = 60
    ):
        """
        初始化健康监控器
        
        Args:
            bot: Telegram Bot实例
            check_interval: 检查间隔（秒）
        """
        self.bot = bot
        self.check_interval = check_interval
        
        # 监控状态
        self.monitoring_active = False
        self.last_check_time = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        
        # 性能指标
        self.metrics = {
            "response_times": [],
            "success_rate": 100.0,
            "total_requests": 0,
            "failed_requests": 0,
            "uptime_start": datetime.now()
        }
        
        # 健康检查项目
        self.health_checks = {
            "database": self._check_database_health,
            "bot_api": self._check_bot_api_health,
            "memory": self._check_memory_health,
            "response_time": self._check_response_time_health
        }
        
        # 警告阈值
        self.thresholds = {
            "response_time_warning": 2.0,  # 响应时间警告阈值（秒）
            "response_time_critical": 5.0,  # 响应时间严重阈值（秒）
            "success_rate_warning": 95.0,  # 成功率警告阈值（%）
            "success_rate_critical": 90.0,  # 成功率严重阈值（%）
            "memory_warning": 80.0,  # 内存使用警告阈值（%）
            "memory_critical": 90.0   # 内存使用严重阈值（%）
        }
        
        logger.info(f"健康监控器初始化完成 - 检查间隔: {check_interval}秒")
    
    async def start_monitoring(self):
        """开始健康监控"""
        if self.monitoring_active:
            logger.warning("健康监控已在运行")
            return
        
        self.monitoring_active = True
        self.metrics["uptime_start"] = datetime.now()
        
        logger.info("开始健康监控")
        
        try:
            while self.monitoring_active:
                await self._perform_health_check()
                await asyncio.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"健康监控运行错误: {e}")
            self.monitoring_active = False
    
    def stop_monitoring(self):
        """停止健康监控"""
        self.monitoring_active = False
        logger.info("健康监控已停止")
    
    async def _perform_health_check(self):
        """执行健康检查"""
        try:
            check_start = datetime.now()
            health_results = {}
            overall_healthy = True
            
            # 执行各项健康检查
            for check_name, check_func in self.health_checks.items():
                try:
                    result = await check_func()
                    health_results[check_name] = result
                    
                    if not result.get("healthy", False):
                        overall_healthy = False
                        
                except Exception as e:
                    logger.error(f"健康检查 {check_name} 失败: {e}")
                    health_results[check_name] = {
                        "healthy": False,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                    overall_healthy = False
            
            # 计算检查耗时
            check_duration = (datetime.now() - check_start).total_seconds()
            
            # 更新指标
            self._update_health_metrics(health_results, check_duration, overall_healthy)
            
            # 处理检查结果
            await self._handle_health_results(health_results, overall_healthy)
            
            self.last_check_time = datetime.now()
            
        except Exception as e:
            logger.error(f"执行健康检查失败: {e}")
            self.consecutive_failures += 1
            await self._handle_monitoring_failure()
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """检查数据库健康状态"""
        try:
            from database.db_connection import db_manager
            
            check_start = datetime.now()
            
            # 执行简单查询测试连接
            await db_manager.execute_query("SELECT 1")
            
            response_time = (datetime.now() - check_start).total_seconds()
            
            return {
                "healthy": True,
                "response_time": response_time,
                "status": "connected",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "status": "connection_failed",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _check_bot_api_health(self) -> Dict[str, Any]:
        """检查Bot API健康状态"""
        try:
            check_start = datetime.now()
            
            # 测试Bot API连接
            bot_info = await self.bot.get_me()
            
            response_time = (datetime.now() - check_start).total_seconds()
            
            return {
                "healthy": True,
                "response_time": response_time,
                "bot_username": bot_info.username,
                "status": "api_connected",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "status": "api_failed",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _check_memory_health(self) -> Dict[str, Any]:
        """检查内存使用情况"""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 判断内存状态
            if memory_percent > self.thresholds["memory_critical"]:
                status = "critical"
                healthy = False
            elif memory_percent > self.thresholds["memory_warning"]:
                status = "warning"
                healthy = True
            else:
                status = "healthy"
                healthy = True
            
            return {
                "healthy": healthy,
                "memory_percent": memory_percent,
                "memory_available": memory.available,
                "memory_total": memory.total,
                "status": status,
                "timestamp": datetime.now().isoformat()
            }
            
        except ImportError:
            return {
                "healthy": True,
                "status": "unavailable",
                "message": "psutil not available",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "status": "check_failed",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _check_response_time_health(self) -> Dict[str, Any]:
        """检查平均响应时间"""
        try:
            if not self.metrics["response_times"]:
                return {
                    "healthy": True,
                    "status": "no_data",
                    "timestamp": datetime.now().isoformat()
                }
            
            # 计算最近10次的平均响应时间
            recent_times = self.metrics["response_times"][-10:]
            avg_response_time = sum(recent_times) / len(recent_times)
            
            # 判断响应时间状态
            if avg_response_time > self.thresholds["response_time_critical"]:
                status = "critical"
                healthy = False
            elif avg_response_time > self.thresholds["response_time_warning"]:
                status = "warning"
                healthy = True
            else:
                status = "healthy"
                healthy = True
            
            return {
                "healthy": healthy,
                "avg_response_time": avg_response_time,
                "status": status,
                "samples": len(recent_times),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "status": "check_failed",
                "timestamp": datetime.now().isoformat()
            }
    
    def _update_health_metrics(
        self, 
        health_results: Dict[str, Any], 
        check_duration: float, 
        overall_healthy: bool
    ):
        """更新健康指标"""
        try:
            # 更新响应时间
            self.metrics["response_times"].append(check_duration)
            
            # 保留最近100次的响应时间
            if len(self.metrics["response_times"]) > 100:
                self.metrics["response_times"] = self.metrics["response_times"][-100:]
            
            # 更新请求统计
            self.metrics["total_requests"] += 1
            
            if not overall_healthy:
                self.metrics["failed_requests"] += 1
            
            # 计算成功率
            if self.metrics["total_requests"] > 0:
                self.metrics["success_rate"] = (
                    (self.metrics["total_requests"] - self.metrics["failed_requests"]) /
                    self.metrics["total_requests"] * 100
                )
            
        except Exception as e:
            logger.error(f"更新健康指标失败: {e}")
    
    async def _handle_health_results(self, health_results: Dict[str, Any], overall_healthy: bool):
        """处理健康检查结果"""
        try:
            if overall_healthy:
                self.consecutive_failures = 0
                logger.debug("健康检查通过")
                
            else:
                self.consecutive_failures += 1
                logger.warning(f"健康检查失败，连续失败次数: {self.consecutive_failures}")
                
                # 记录失败的检查项目
                failed_checks = [
                    name for name, result in health_results.items()
                    if not result.get("healthy", False)
                ]
                logger.warning(f"失败的检查项目: {failed_checks}")
            
        except Exception as e:
            logger.error(f"处理健康检查结果失败: {e}")
    
    def _is_system_stable(self) -> bool:
        """检查系统是否稳定"""
        try:
            # 检查成功率
            if self.metrics["success_rate"] < self.thresholds["success_rate_warning"]:
                return False
            
            # 检查响应时间
            if self.metrics["response_times"]:
                recent_avg = sum(self.metrics["response_times"][-5:]) / min(5, len(self.metrics["response_times"]))
                if recent_avg > self.thresholds["response_time_warning"]:
                    return False
            
            # 检查连续失败次数
            if self.consecutive_failures > 0:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"系统稳定性检查失败: {e}")
            return False
    
    async def _handle_monitoring_failure(self):
        """处理监控失败"""
        try:
            if self.consecutive_failures >= self.max_consecutive_failures * 2:
                logger.critical("健康监控连续失败，停止监控")
                self.stop_monitoring()
            
        except Exception as e:
            logger.error(f"处理监控失败异常: {e}")
    
    def record_request_metric(self, response_time: float, success: bool):
        """
        记录请求指标
        
        Args:
            response_time: 响应时间（秒）
            success: 是否成功
        """
        try:
            self.metrics["response_times"].append(response_time)
            self.metrics["total_requests"] += 1
            
            if not success:
                self.metrics["failed_requests"] += 1
            
            # 保留最近的指标
            if len(self.metrics["response_times"]) > 1000:
                self.metrics["response_times"] = self.metrics["response_times"][-1000:]
            
            # 更新成功率
            if self.metrics["total_requests"] > 0:
                self.metrics["success_rate"] = (
                    (self.metrics["total_requests"] - self.metrics["failed_requests"]) /
                    self.metrics["total_requests"] * 100
                )
            
        except Exception as e:
            logger.error(f"记录请求指标失败: {e}")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        获取健康状况摘要
        
        Returns:
            健康状况摘要
        """
        try:
            uptime = datetime.now() - self.metrics["uptime_start"]
            
            # 计算平均响应时间
            avg_response_time = 0.0
            if self.metrics["response_times"]:
                avg_response_time = sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
            
            return {
                "monitoring_active": self.monitoring_active,
                "last_check": self.last_check_time.isoformat() if self.last_check_time else None,
                "consecutive_failures": self.consecutive_failures,
                "uptime_hours": uptime.total_seconds() / 3600,
                "metrics": {
                    "success_rate": self.metrics["success_rate"],
                    "total_requests": self.metrics["total_requests"],
                    "failed_requests": self.metrics["failed_requests"],
                    "avg_response_time": avg_response_time
                },
                "thresholds": self.thresholds.copy(),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取健康摘要失败: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }