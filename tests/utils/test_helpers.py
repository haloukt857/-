# -*- coding: utf-8 -*-
"""
测试辅助工具模块

提供测试过程中需要的各种辅助功能：
- 测试结果收集和统计
- 测试报告生成
- 数据库管理
- 性能监控
- 错误处理
"""

import asyncio
import json
import logging
import os
import shutil
import sqlite3
import time
import traceback
import psutil
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading


@dataclass
class TestResultSummary:
    """测试结果摘要"""
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    error_tests: int = 0
    skipped_tests: int = 0
    total_duration: float = 0.0
    pass_rate: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TestResultCollector:
    """测试结果收集器"""
    
    def __init__(self):
        self.module_results: Dict[str, Any] = {}
        self.test_results: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.performance_data: List[Dict[str, Any]] = []
        self.start_time = None
        self.end_time = None
        self._lock = threading.Lock()
    
    def start_collection(self):
        """开始收集"""
        with self._lock:
            self.start_time = datetime.now()
    
    def end_collection(self):
        """结束收集"""
        with self._lock:
            self.end_time = datetime.now()
    
    def add_module_result(self, module_name: str, result: Dict[str, Any]):
        """添加模块测试结果"""
        with self._lock:
            self.module_results[module_name] = result
    
    def add_test_result(self, test_name: str, status: str, duration: float, 
                       error_msg: str = None, details: Dict[str, Any] = None):
        """添加单个测试结果"""
        with self._lock:
            result = {
                'test_name': test_name,
                'status': status,
                'duration': duration,
                'timestamp': datetime.now().isoformat(),
                'error_msg': error_msg,
                'details': details or {}
            }
            self.test_results.append(result)
    
    def add_error(self, error_type: str, error_msg: str, context: str = None):
        """添加错误信息"""
        with self._lock:
            error = {
                'error_type': error_type,
                'error_msg': error_msg,
                'context': context,
                'timestamp': datetime.now().isoformat(),
                'traceback': traceback.format_exc()
            }
            self.errors.append(error)
    
    def add_performance_data(self, metric_name: str, value: float, unit: str = None):
        """添加性能数据"""
        with self._lock:
            metric = {
                'metric_name': metric_name,
                'value': value,
                'unit': unit,
                'timestamp': datetime.now().isoformat()
            }
            self.performance_data.append(metric)
    
    def get_summary(self) -> TestResultSummary:
        """获取测试结果摘要"""
        with self._lock:
            total_tests = len(self.test_results)
            passed_tests = sum(1 for r in self.test_results if r['status'] == 'PASSED')
            failed_tests = sum(1 for r in self.test_results if r['status'] == 'FAILED')
            error_tests = sum(1 for r in self.test_results if r['status'] == 'ERROR')
            skipped_tests = sum(1 for r in self.test_results if r['status'] == 'SKIPPED')
            
            total_duration = sum(r['duration'] for r in self.test_results)
            pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
            
            return TestResultSummary(
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                error_tests=error_tests,
                skipped_tests=skipped_tests,
                total_duration=total_duration,
                pass_rate=pass_rate,
                start_time=self.start_time,
                end_time=self.end_time
            )
    
    def export_to_json(self, file_path: str):
        """导出为JSON格式"""
        with self._lock:
            data = {
                'summary': asdict(self.get_summary()),
                'module_results': self.module_results,
                'test_results': self.test_results,
                'errors': self.errors,
                'performance_data': self.performance_data
            }
            
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)


class TestReporter:
    """测试报告生成器"""
    
    def __init__(self, output_dir: str = "tests/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_comprehensive_report(self, report_data: Dict[str, Any]):
        """生成综合测试报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 生成JSON报告
        json_file = self.output_dir / f"comprehensive_test_report_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
        
        # 生成HTML报告
        html_file = self.output_dir / f"comprehensive_test_report_{timestamp}.html"
        await self._generate_html_report(report_data, html_file)
        
        # 生成Markdown报告
        md_file = self.output_dir / f"comprehensive_test_report_{timestamp}.md"
        await self._generate_markdown_report(report_data, md_file)
        
        return {
            'json_report': str(json_file),
            'html_report': str(html_file),
            'markdown_report': str(md_file)
        }
    
    async def _generate_html_report(self, data: Dict[str, Any], output_file: Path):
        """生成HTML格式报告"""
        summary = data.get('summary', {})
        results = data.get('results', {})
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram商户机器人V2.0综合测试报告</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; text-align: center; margin-bottom: 30px; }}
        h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric {{ background: #ecf0f1; padding: 15px; border-radius: 5px; text-align: center; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ color: #7f8c8d; margin-top: 5px; }}
        .pass {{ color: #27ae60; }}
        .fail {{ color: #e74c3c; }}
        .error {{ color: #f39c12; }}
        .module {{ margin-bottom: 20px; padding: 15px; border: 1px solid #bdc3c7; border-radius: 5px; }}
        .module-header {{ display: flex; justify-content: between; align-items: center; margin-bottom: 10px; }}
        .status-badge {{ padding: 5px 10px; border-radius: 15px; color: white; font-size: 0.8em; }}
        .status-passed {{ background-color: #27ae60; }}
        .status-failed {{ background-color: #e74c3c; }}
        .status-error {{ background-color: #f39c12; }}
        .progress-bar {{ background-color: #ecf0f1; border-radius: 10px; overflow: hidden; height: 20px; margin: 10px 0; }}
        .progress-fill {{ height: 100%; background-color: #3498db; transition: width 0.3s ease; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        .test-passed {{ background-color: #d5f4e6; }}
        .test-failed {{ background-color: #f8d7da; }}
        .test-error {{ background-color: #fff3cd; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Telegram商户机器人V2.0综合测试报告</h1>
        
        <div class="summary">
            <div class="metric">
                <div class="metric-value">{summary.get('execution_time', 0):.1f}s</div>
                <div class="metric-label">执行时间</div>
            </div>
            <div class="metric">
                <div class="metric-value pass">{summary.get('passed_modules', 0)}</div>
                <div class="metric-label">通过模块</div>
            </div>
            <div class="metric">
                <div class="metric-value fail">{summary.get('failed_modules', 0)}</div>
                <div class="metric-label">失败模块</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary.get('module_pass_rate', 0):.1f}%</div>
                <div class="metric-label">模块通过率</div>
            </div>
            <div class="metric">
                <div class="metric-value pass">{summary.get('passed_tests', 0)}</div>
                <div class="metric-label">通过测试</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary.get('test_pass_rate', 0):.1f}%</div>
                <div class="metric-label">测试通过率</div>
            </div>
        </div>
        
        <h2>📋 模块测试结果</h2>
"""
        
        # 添加模块结果
        for module_name, result in results.items():
            status = result.get('status', 'unknown')
            status_class = f"status-{status.lower()}" if status.lower() in ['passed', 'failed', 'error'] else 'status-error'
            
            total_tests = result.get('total_tests', 0)
            passed_tests = result.get('passed_tests', 0)
            pass_rate = result.get('pass_rate', 0)
            
            html_content += f"""
        <div class="module">
            <div class="module-header">
                <h3>{module_name}</h3>
                <span class="status-badge {status_class}">{status}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {pass_rate}%"></div>
            </div>
            <p>测试通过: {passed_tests}/{total_tests} ({pass_rate:.1f}%)</p>
            <p>执行时间: {result.get('duration', 0):.2f}秒</p>
"""
            
            if result.get('error'):
                html_content += f"<p class='error'>错误: {result['error']}</p>"
            
            html_content += "</div>"
        
        html_content += """
        </div>
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    async def _generate_markdown_report(self, data: Dict[str, Any], output_file: Path):
        """生成Markdown格式报告"""
        summary = data.get('summary', {})
        results = data.get('results', {})
        
        md_content = f"""# 🎯 Telegram商户机器人V2.0综合测试报告

## 📊 测试摘要

| 指标 | 数值 |
|------|------|
| 执行时间 | {summary.get('execution_time', 0):.2f}秒 |
| 总模块数 | {summary.get('total_modules', 0)} |
| 通过模块 | {summary.get('passed_modules', 0)} |
| 失败模块 | {summary.get('failed_modules', 0)} |
| 模块通过率 | {summary.get('module_pass_rate', 0):.1f}% |
| 总测试数 | {summary.get('total_tests', 0)} |
| 通过测试 | {summary.get('passed_tests', 0)} |
| 失败测试 | {summary.get('failed_tests', 0)} |
| 测试通过率 | {summary.get('test_pass_rate', 0):.1f}% |

## 📋 模块测试详情

"""
        
        for module_name, result in results.items():
            status_emoji = "✅" if result.get('status') == 'PASSED' else "❌" if result.get('status') == 'FAILED' else "💥"
            
            md_content += f"""### {status_emoji} {module_name}

- **状态**: {result.get('status', 'UNKNOWN')}
- **测试通过**: {result.get('passed_tests', 0)}/{result.get('total_tests', 0)} ({result.get('pass_rate', 0):.1f}%)
- **执行时间**: {result.get('duration', 0):.2f}秒

"""
            
            if result.get('error'):
                md_content += f"- **错误信息**: {result['error']}\n\n"
        
        # 添加环境信息
        env = data.get('environment', {})
        md_content += f"""## 🔧 测试环境

- **Python版本**: {env.get('python_version', 'Unknown')}
- **平台**: {env.get('platform', 'Unknown')}
- **时间戳**: {env.get('timestamp', 'Unknown')}

## 📈 性能指标

"""
        
        perf_metrics = data.get('performance_metrics', {})
        if perf_metrics:
            for metric_name, metric_value in perf_metrics.items():
                md_content += f"- **{metric_name}**: {metric_value}\n"
        
        md_content += "\n---\n\n*本报告由Telegram商户机器人V2.0综合测试系统自动生成*"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data/test_marketing_bot.db"):
        self.db_path = db_path
        self.backup_path = f"{db_path}.backup"
        self.test_db_path = f"{db_path}.test"
        self.connection_pool = []
        self._lock = threading.Lock()
    
    async def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result[0] == 1
        except Exception as e:
            logging.error(f"数据库连接测试失败: {e}")
            return False
    
    async def backup_database(self):
        """备份现有数据库"""
        if Path(self.db_path).exists():
            shutil.copy2(self.db_path, self.backup_path)
            logging.info(f"数据库已备份到: {self.backup_path}")
    
    async def restore_database(self):
        """恢复数据库"""
        if Path(self.backup_path).exists():
            shutil.copy2(self.backup_path, self.db_path)
            logging.info(f"数据库已从备份恢复: {self.backup_path}")
    
    async def create_test_database(self):
        """创建测试数据库"""
        # 复制现有数据库作为测试基础
        if Path(self.db_path).exists():
            shutil.copy2(self.db_path, self.test_db_path)
        
        # 清理测试相关数据
        await self._clean_test_data()
        logging.info(f"测试数据库已创建: {self.test_db_path}")
    
    async def _clean_test_data(self):
        """清理测试数据"""
        test_tables = [
            'binding_codes',
            'merchants',
            'orders',
            'users',
            'reviews'
        ]
        
        try:
            with sqlite3.connect(self.test_db_path) as conn:
                cursor = conn.cursor()
                
                for table in test_tables:
                    try:
                        # 删除测试数据（以test_开头的记录）
                        cursor.execute(f"DELETE FROM {table} WHERE name LIKE 'test_%' OR username LIKE 'test_%'")
                    except sqlite3.OperationalError:
                        # 表不存在或字段不存在，忽略
                        pass
                
                conn.commit()
        except Exception as e:
            logging.warning(f"清理测试数据时出现错误: {e}")
    
    async def run_migrations(self):
        """运行数据库迁移"""
        migration_script = Path(__file__).parent.parent.parent / "scripts" / "migrate_to_v2.py"
        
        if migration_script.exists():
            try:
                # 执行迁移脚本
                import subprocess
                result = subprocess.run(
                    ["python", str(migration_script)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode == 0:
                    logging.info("数据库迁移完成")
                else:
                    logging.error(f"数据库迁移失败: {result.stderr}")
            except Exception as e:
                logging.error(f"执行数据库迁移时出现错误: {e}")
    
    async def initialize_test_data(self):
        """初始化测试数据"""
        try:
            with sqlite3.connect(self.test_db_path) as conn:
                cursor = conn.cursor()
                
                # 创建测试绑定码
                test_codes = ['TESTAB12', 'TESTCD34', 'TESTEFG56']
                for code in test_codes:
                    cursor.execute(
                        "INSERT OR REPLACE INTO binding_codes (code, hours, is_used, created_at) VALUES (?, ?, ?, ?)",
                        (code, 24, 0, datetime.now().isoformat())
                    )
                
                # 创建测试地区
                cursor.execute(
                    "INSERT OR REPLACE INTO cities (id, name, is_active) VALUES (?, ?, ?)",
                    (999, '测试城市', 1)
                )
                
                cursor.execute(
                    "INSERT OR REPLACE INTO districts (id, city_id, name, is_active) VALUES (?, ?, ?, ?)",
                    (999, 999, '测试地区', 1)
                )
                
                conn.commit()
                logging.info("测试数据初始化完成")
                
        except Exception as e:
            logging.error(f"初始化测试数据时出现错误: {e}")
    
    async def cleanup_temp_files(self):
        """清理临时文件"""
        temp_files = [self.test_db_path, self.backup_path]
        
        for file_path in temp_files:
            try:
                if Path(file_path).exists():
                    Path(file_path).unlink()
                    logging.info(f"已删除临时文件: {file_path}")
            except Exception as e:
                logging.warning(f"删除临时文件 {file_path} 时出现错误: {e}")


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = {}
        self.start_time = None
        self.monitor_thread = None
        self._lock = threading.Lock()
    
    def start(self):
        """开始监控"""
        with self._lock:
            if not self.monitoring:
                self.monitoring = True
                self.start_time = time.time()
                self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self.monitor_thread.start()
                logging.info("性能监控已启动")
    
    def stop(self):
        """停止监控"""
        with self._lock:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=1)
            logging.info("性能监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 收集系统指标
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                timestamp = time.time() - self.start_time
                
                with self._lock:
                    if 'cpu_usage' not in self.metrics:
                        self.metrics['cpu_usage'] = []
                    if 'memory_usage' not in self.metrics:
                        self.metrics['memory_usage'] = []
                    
                    self.metrics['cpu_usage'].append((timestamp, cpu_percent))
                    self.metrics['memory_usage'].append((timestamp, memory.percent))
                
                time.sleep(5)  # 每5秒采集一次
                
            except Exception as e:
                logging.error(f"性能监控错误: {e}")
                time.sleep(1)
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        with self._lock:
            if not self.metrics:
                return {}
            
            result = {}
            
            # CPU指标
            if 'cpu_usage' in self.metrics:
                cpu_values = [v for _, v in self.metrics['cpu_usage']]
                result['cpu_avg'] = sum(cpu_values) / len(cpu_values)
                result['cpu_max'] = max(cpu_values)
                result['cpu_min'] = min(cpu_values)
            
            # 内存指标
            if 'memory_usage' in self.metrics:
                mem_values = [v for _, v in self.metrics['memory_usage']]
                result['memory_avg'] = sum(mem_values) / len(mem_values)
                result['memory_max'] = max(mem_values)
                result['memory_min'] = min(mem_values)
            
            return result
    
    def add_custom_metric(self, name: str, value: float):
        """添加自定义指标"""
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = []
            
            timestamp = time.time() - self.start_time if self.start_time else 0
            self.metrics[name].append((timestamp, value))


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.error_log = []
        self._lock = threading.Lock()
    
    def handle_exception(self, e: Exception, context: str = None) -> Dict[str, Any]:
        """处理异常"""
        error_info = {
            'type': type(e).__name__,
            'message': str(e),
            'context': context,
            'timestamp': datetime.now().isoformat(),
            'traceback': traceback.format_exc()
        }
        
        with self._lock:
            self.error_log.append(error_info)
        
        logging.error(f"异常处理 [{context}]: {e}")
        return error_info
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        with self._lock:
            if not self.error_log:
                return {'total_errors': 0}
            
            error_types = {}
            for error in self.error_log:
                error_type = error['type']
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            return {
                'total_errors': len(self.error_log),
                'error_types': error_types,
                'recent_errors': self.error_log[-5:]  # 最近5个错误
            }
    
    @contextmanager
    def error_context(self, context: str):
        """错误上下文管理器"""
        try:
            yield
        except Exception as e:
            self.handle_exception(e, context)
            raise


# 工具函数

def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds:.2f}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{int(minutes)}分{secs:.1f}秒"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{int(hours)}小时{int(minutes)}分钟"


def calculate_pass_rate(passed: int, total: int) -> float:
    """计算通过率"""
    return (passed / total * 100) if total > 0 else 0


def get_status_emoji(status: str) -> str:
    """获取状态表情符号"""
    emoji_map = {
        'PASSED': '✅',
        'FAILED': '❌',
        'ERROR': '💥',
        'TIMEOUT': '⏰',
        'SKIPPED': '⏭️',
        'RUNNING': '🔄'
    }
    return emoji_map.get(status.upper(), '❓')


def ensure_directory(path: Union[str, Path]):
    """确保目录存在"""
    Path(path).mkdir(parents=True, exist_ok=True)


def safe_json_dump(data: Any, file_path: Union[str, Path]):
    """安全的JSON序列化"""
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Path):
            return str(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    ensure_directory(Path(file_path).parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=json_serializer)