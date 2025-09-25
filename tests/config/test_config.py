# -*- coding: utf-8 -*-
"""
测试配置管理系统

提供统一的测试配置管理，支持不同环境和场景的测试配置
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional


class TestEnvironment(Enum):
    """测试环境类型"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION_SIMULATION = "production_simulation"


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    url: str = "sqlite:///data/test_marketing_bot.db"
    backup_url: str = "sqlite:///data/backup_marketing_bot.db"
    enable_wal_mode: bool = True
    timeout: int = 30
    pool_size: int = 5
    max_retries: int = 3


@dataclass
class TelegramConfig:
    """Telegram配置"""
    bot_token: str = "TEST_BOT_TOKEN"
    test_user_ids: List[int] = field(default_factory=lambda: [12345678, 87654321])
    test_chat_id: int = -1001234567890
    api_timeout: int = 30
    mock_api_calls: bool = True


@dataclass
class PerformanceConfig:
    """性能测试配置"""
    concurrent_users: int = 10
    max_requests_per_second: int = 100
    memory_limit_mb: int = 512
    cpu_limit_percent: int = 80
    enable_profiling: bool = False


@dataclass
class ReportConfig:
    """报告生成配置"""
    output_dir: str = "tests/reports"
    include_screenshots: bool = False
    generate_html: bool = True
    generate_json: bool = True
    generate_xml: bool = False
    include_performance_metrics: bool = True


@dataclass
class TestConfig:
    """主测试配置类"""
    
    # 基础配置
    test_environment: TestEnvironment = TestEnvironment.TESTING
    log_level: LogLevel = LogLevel.INFO
    debug_mode: bool = False
    verbose_output: bool = True
    
    # 超时配置
    test_timeout: int = 300  # 单个测试超时（秒）
    module_timeout: int = 1800  # 模块超时（秒）
    suite_timeout: int = 7200  # 套件超时（秒）
    
    # 执行配置
    max_workers: int = 4
    retry_attempts: int = 2
    stop_on_failure: bool = False
    continue_on_error: bool = True
    
    # 并发配置
    enable_parallel_execution: bool = True
    max_parallel_modules: int = 3
    module_isolation: bool = True
    
    # 数据管理
    cleanup_after_tests: bool = True
    preserve_test_data: bool = False
    reset_database: bool = True
    
    # 功能开关
    enable_performance_monitoring: bool = True
    enable_memory_profiling: bool = False
    enable_network_monitoring: bool = True
    enable_error_screenshots: bool = False
    
    # 模块控制
    disabled_modules: List[str] = field(default_factory=list)
    priority_modules: List[str] = field(default_factory=list)
    
    # 子配置
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    reporting: ReportConfig = field(default_factory=ReportConfig)
    
    # 自定义配置
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'TestConfig':
        """从文件加载配置"""
        if not config_path:
            # 尝试从环境变量获取
            config_path = os.getenv('TEST_CONFIG_PATH')
            
            # 默认配置文件位置
            if not config_path:
                project_root = Path(__file__).parent.parent.parent
                default_config = project_root / "tests" / "config" / "test_config.json"
                if default_config.exists():
                    config_path = str(default_config)
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                return cls._from_dict(config_data)
            except Exception as e:
                print(f"警告: 无法加载配置文件 {config_path}: {e}")
                print("使用默认配置")
        
        return cls()
    
    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'TestConfig':
        """从字典创建配置对象"""
        config = cls()
        
        # 基础配置
        if 'test_environment' in data:
            config.test_environment = TestEnvironment(data['test_environment'])
        if 'log_level' in data:
            config.log_level = LogLevel(data['log_level'])
        
        # 简单字段
        simple_fields = [
            'debug_mode', 'verbose_output', 'test_timeout', 'module_timeout',
            'suite_timeout', 'max_workers', 'retry_attempts', 'stop_on_failure',
            'continue_on_error', 'enable_parallel_execution', 'max_parallel_modules',
            'module_isolation', 'cleanup_after_tests', 'preserve_test_data',
            'reset_database', 'enable_performance_monitoring', 'enable_memory_profiling',
            'enable_network_monitoring', 'enable_error_screenshots'
        ]
        
        for field_name in simple_fields:
            if field_name in data:
                setattr(config, field_name, data[field_name])
        
        # 列表字段
        if 'disabled_modules' in data:
            config.disabled_modules = data['disabled_modules']
        if 'priority_modules' in data:
            config.priority_modules = data['priority_modules']
        
        # 子配置
        if 'database' in data:
            config.database = DatabaseConfig(**data['database'])
        if 'telegram' in data:
            config.telegram = TelegramConfig(**data['telegram'])
        if 'performance' in data:
            config.performance = PerformanceConfig(**data['performance'])
        if 'reporting' in data:
            config.reporting = ReportConfig(**data['reporting'])
        
        # 自定义设置
        if 'custom_settings' in data:
            config.custom_settings = data['custom_settings']
        
        return config
    
    def save(self, config_path: str):
        """保存配置到文件"""
        config_data = self._to_dict()
        
        # 确保目录存在
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    
    def _to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'test_environment': self.test_environment.value,
            'log_level': self.log_level.value,
            'debug_mode': self.debug_mode,
            'verbose_output': self.verbose_output,
            'test_timeout': self.test_timeout,
            'module_timeout': self.module_timeout,
            'suite_timeout': self.suite_timeout,
            'max_workers': self.max_workers,
            'retry_attempts': self.retry_attempts,
            'stop_on_failure': self.stop_on_failure,
            'continue_on_error': self.continue_on_error,
            'enable_parallel_execution': self.enable_parallel_execution,
            'max_parallel_modules': self.max_parallel_modules,
            'module_isolation': self.module_isolation,
            'cleanup_after_tests': self.cleanup_after_tests,
            'preserve_test_data': self.preserve_test_data,
            'reset_database': self.reset_database,
            'enable_performance_monitoring': self.enable_performance_monitoring,
            'enable_memory_profiling': self.enable_memory_profiling,
            'enable_network_monitoring': self.enable_network_monitoring,
            'enable_error_screenshots': self.enable_error_screenshots,
            'disabled_modules': self.disabled_modules,
            'priority_modules': self.priority_modules,
            'database': {
                'url': self.database.url,
                'backup_url': self.database.backup_url,
                'enable_wal_mode': self.database.enable_wal_mode,
                'timeout': self.database.timeout,
                'pool_size': self.database.pool_size,
                'max_retries': self.database.max_retries
            },
            'telegram': {
                'bot_token': self.telegram.bot_token,
                'test_user_ids': self.telegram.test_user_ids,
                'test_chat_id': self.telegram.test_chat_id,
                'api_timeout': self.telegram.api_timeout,
                'mock_api_calls': self.telegram.mock_api_calls
            },
            'performance': {
                'concurrent_users': self.performance.concurrent_users,
                'max_requests_per_second': self.performance.max_requests_per_second,
                'memory_limit_mb': self.performance.memory_limit_mb,
                'cpu_limit_percent': self.performance.cpu_limit_percent,
                'enable_profiling': self.performance.enable_profiling
            },
            'reporting': {
                'output_dir': self.reporting.output_dir,
                'include_screenshots': self.reporting.include_screenshots,
                'generate_html': self.reporting.generate_html,
                'generate_json': self.reporting.generate_json,
                'generate_xml': self.reporting.generate_xml,
                'include_performance_metrics': self.reporting.include_performance_metrics
            },
            'custom_settings': self.custom_settings
        }
    
    def get_environment_specific_config(self) -> Dict[str, Any]:
        """获取环境特定配置"""
        configs = {
            TestEnvironment.DEVELOPMENT: {
                'database': {'url': 'sqlite:///data/dev_test_bot.db'},
                'debug_mode': True,
                'verbose_output': True,
                'stop_on_failure': False,
                'enable_performance_monitoring': False
            },
            TestEnvironment.TESTING: {
                'database': {'url': 'sqlite:///data/test_marketing_bot.db'},
                'debug_mode': False,
                'verbose_output': True,
                'stop_on_failure': False,
                'enable_performance_monitoring': True
            },
            TestEnvironment.STAGING: {
                'database': {'url': 'sqlite:///data/staging_test_bot.db'},
                'debug_mode': False,
                'verbose_output': False,
                'stop_on_failure': True,
                'enable_performance_monitoring': True,
                'retry_attempts': 3
            },
            TestEnvironment.PRODUCTION_SIMULATION: {
                'database': {'url': 'sqlite:///data/prod_sim_test_bot.db'},
                'debug_mode': False,
                'verbose_output': False,
                'stop_on_failure': True,
                'enable_performance_monitoring': True,
                'enable_memory_profiling': True,
                'retry_attempts': 1,
                'max_workers': 2
            }
        }
        
        return configs.get(self.test_environment, {})
    
    def apply_environment_config(self):
        """应用环境特定配置"""
        env_config = self.get_environment_specific_config()
        
        for key, value in env_config.items():
            if key == 'database' and isinstance(value, dict):
                for db_key, db_value in value.items():
                    setattr(self.database, db_key, db_value)
            else:
                setattr(self, key, value)
    
    def validate(self) -> List[str]:
        """验证配置"""
        errors = []
        
        # 检查超时配置
        if self.test_timeout <= 0:
            errors.append("test_timeout 必须大于0")
        
        if self.module_timeout < self.test_timeout:
            errors.append("module_timeout 应该大于等于 test_timeout")
        
        if self.suite_timeout < self.module_timeout:
            errors.append("suite_timeout 应该大于等于 module_timeout")
        
        # 检查并发配置
        if self.max_workers <= 0:
            errors.append("max_workers 必须大于0")
        
        if self.max_parallel_modules > self.max_workers:
            errors.append("max_parallel_modules 不应该大于 max_workers")
        
        # 检查重试配置
        if self.retry_attempts < 0:
            errors.append("retry_attempts 不能为负数")
        
        # 检查数据库配置
        if not self.database.url:
            errors.append("数据库URL不能为空")
        
        # 检查报告目录
        if not self.reporting.output_dir:
            errors.append("报告输出目录不能为空")
        
        return errors
    
    def is_module_enabled(self, module_name: str) -> bool:
        """检查模块是否启用"""
        return module_name not in self.disabled_modules
    
    def get_module_priority(self, module_name: str) -> int:
        """获取模块优先级"""
        if module_name in self.priority_modules:
            return self.priority_modules.index(module_name)
        return 999  # 默认低优先级
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"TestConfig(environment={self.test_environment.value}, log_level={self.log_level.value})"


# 预定义配置模板
class ConfigTemplates:
    """配置模板"""
    
    @staticmethod
    def development() -> TestConfig:
        """开发环境配置"""
        config = TestConfig()
        config.test_environment = TestEnvironment.DEVELOPMENT
        config.debug_mode = True
        config.verbose_output = True
        config.stop_on_failure = False
        config.enable_performance_monitoring = False
        config.database.url = "sqlite:///data/dev_test_bot.db"
        return config
    
    @staticmethod
    def ci_cd() -> TestConfig:
        """CI/CD环境配置"""
        config = TestConfig()
        config.test_environment = TestEnvironment.TESTING
        config.verbose_output = False
        config.stop_on_failure = True
        config.max_workers = 2
        config.module_timeout = 600  # 10分钟
        config.suite_timeout = 3600  # 1小时
        config.database.url = "sqlite:///data/ci_test_bot.db"
        return config
    
    @staticmethod
    def performance() -> TestConfig:
        """性能测试配置"""
        config = TestConfig()
        config.test_environment = TestEnvironment.STAGING
        config.enable_performance_monitoring = True
        config.enable_memory_profiling = True
        config.performance.concurrent_users = 50
        config.performance.enable_profiling = True
        config.database.url = "sqlite:///data/perf_test_bot.db"
        return config
    
    @staticmethod
    def production_simulation() -> TestConfig:
        """生产环境模拟配置"""
        config = TestConfig()
        config.test_environment = TestEnvironment.PRODUCTION_SIMULATION
        config.debug_mode = False
        config.stop_on_failure = True
        config.retry_attempts = 1
        config.max_workers = 1
        config.enable_parallel_execution = False
        config.database.url = "sqlite:///data/prod_sim_test_bot.db"
        return config


def create_default_config_file():
    """创建默认配置文件"""
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / "tests" / "config" / "test_config.json"
    
    # 创建默认配置
    default_config = TestConfig()
    default_config.apply_environment_config()
    
    # 保存到文件
    default_config.save(str(config_path))
    
    print(f"默认配置文件已创建: {config_path}")
    return config_path


if __name__ == "__main__":
    # 创建默认配置文件
    create_default_config_file()