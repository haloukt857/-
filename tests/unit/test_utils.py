"""
工具函数单元测试
测试健康监控工具组件
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from utils.health_monitor import HealthMonitor
from config import ADMIN_IDS


class TestHealthMonitor:
    """健康监控测试"""
    
    @pytest.fixture
    def mock_bot(self):
        """创建模拟机器人"""
        bot = AsyncMock()
        bot.get_me.return_value = AsyncMock()
        bot.get_me.return_value.username = "test_bot"
        return bot

    @pytest.fixture
    def health_monitor(self, mock_bot):
        """创建健康监控实例"""
        return HealthMonitor(mock_bot, check_interval=1)

    async def test_database_health_check(self, health_monitor):
        """测试数据库健康检查"""
        with patch('utils.health_monitor.db_manager') as mock_db_manager:
            mock_db_manager.execute_query.return_value = None
            
            result = await health_monitor._check_database_health()
            
            assert result["healthy"] is True
            assert "response_time" in result
            assert result["status"] == "connected"
            
            # 测试数据库连接失败
            mock_db_manager.execute_query.side_effect = Exception("Connection failed")
            result = await health_monitor._check_database_health()
            
            assert result["healthy"] is False
            assert result["status"] == "connection_failed"

    async def test_bot_api_health_check(self, health_monitor, mock_bot):
        """测试Bot API健康检查"""
        bot_info = AsyncMock()
        bot_info.username = "test_bot"
        mock_bot.get_me.return_value = bot_info
        
        result = await health_monitor._check_bot_api_health()
        
        assert result["healthy"] is True
        assert result["bot_username"] == "test_bot"
        assert result["status"] == "api_connected"

    async def test_memory_health_check(self, health_monitor):
        """测试内存健康检查"""
        # 模拟psutil可用的情况
        mock_memory = MagicMock()
        mock_memory.percent = 50.0
        mock_memory.available = 8000000000
        mock_memory.total = 16000000000
        
        with patch('utils.health_monitor.psutil') as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_memory
            
            result = await health_monitor._check_memory_health()
            
            assert result["healthy"] is True
            assert result["memory_percent"] == 50.0
            assert result["status"] == "healthy"

    async def test_response_time_health_check(self, health_monitor):
        """测试响应时间健康检查"""
        # 添加一些响应时间数据
        health_monitor.metrics["response_times"] = [0.5, 0.7, 0.9, 1.2, 0.8]
        
        result = await health_monitor._check_response_time_health()
        
        assert result["healthy"] is True
        assert "avg_response_time" in result
        assert result["samples"] == 5

    async def test_health_check_failure_handling(self, health_monitor):
        """测试健康检查失败处理"""
        # 模拟数据库检查失败
        with patch.object(health_monitor, '_check_database_health') as mock_db_check:
            mock_db_check.return_value = {"healthy": False, "error": "Connection failed"}
            
            # 执行健康检查
            await health_monitor._perform_health_check()
            
            # 验证失败计数增加
            assert health_monitor.consecutive_failures > 0

    async def test_automatic_monitoring_start_stop(self, health_monitor):
        """测试自动监控启动和停止"""
        assert not health_monitor.monitoring_active
        
        # 启动监控（使用短时间间隔进行测试）
        monitor_task = asyncio.create_task(health_monitor.start_monitoring())
        await asyncio.sleep(0.1)  # 等待监控启动
        assert health_monitor.monitoring_active
        
        # 停止监控
        health_monitor.stop_monitoring()
        await asyncio.sleep(0.1)  # 等待监控停止
        assert not health_monitor.monitoring_active
        
        # 确保任务被取消
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    def test_record_request_metric(self, health_monitor):
        """测试请求指标记录"""
        # 记录一些测试指标
        health_monitor.record_request_metric(0.5, True)
        health_monitor.record_request_metric(0.7, True)
        # 记录一个失败请求
        health_monitor.record_request_metric(1.2, False)
        
        assert len(health_monitor.metrics["response_times"]) == 3
        assert health_monitor.metrics["total_requests"] == 3
        assert health_monitor.metrics["failed_requests"] == 1
        assert health_monitor.metrics["success_rate"] == 200/3  # 约66.67%

    def test_get_health_summary(self, health_monitor):
        """测试健康状况摘要获取"""
        # 设置一些测试数据
        health_monitor.metrics["response_times"] = [0.5, 0.7, 0.9]
        health_monitor.metrics["total_requests"] = 10
        health_monitor.metrics["failed_requests"] = 1
        health_monitor.consecutive_failures = 0
        health_monitor.last_check_time = datetime.now()
        
        summary = health_monitor.get_health_summary()
        
        assert "monitoring_active" in summary
        assert "metrics" in summary
        assert summary["metrics"]["success_rate"] == 90.0
        assert summary["consecutive_failures"] == 0

    def test_system_stability_check(self, health_monitor):
        """测试系统稳定性检查"""
        # 设置稳定的系统状态
        health_monitor.metrics["success_rate"] = 98.0
        health_monitor.metrics["response_times"] = [0.3, 0.4, 0.5, 0.6, 0.4]
        health_monitor.consecutive_failures = 0
        
        assert health_monitor._is_system_stable() is True
        
        # 测试不稳定的系统（成功率低）
        health_monitor.metrics["success_rate"] = 85.0  # 低于警告阈值
        assert health_monitor._is_system_stable() is False
        
        # 测试不稳定的系统（响应时间高）
        health_monitor.metrics["success_rate"] = 98.0
        health_monitor.metrics["response_times"] = [3.0, 3.5, 4.0, 3.8, 3.2]  # 高响应时间
        assert health_monitor._is_system_stable() is False


class TestConfigurationValidation:
    """配置验证测试"""
    
    def test_admin_ids_configuration(self):
        """测试管理员ID配置"""
        assert isinstance(ADMIN_IDS, list)
        assert len(ADMIN_IDS) > 0
        for admin_id in ADMIN_IDS:
            assert isinstance(admin_id, int)
            assert admin_id > 0