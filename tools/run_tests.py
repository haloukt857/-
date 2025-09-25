#!/usr/bin/env python3
"""
测试运行脚本
提供不同类型测试的运行选项
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """运行命令并显示结果"""
    if description:
        print(f"\n{'='*50}")
        print(f"执行: {description}")
        print(f"命令: {' '.join(cmd)}")
        print(f"{'='*50}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败 (返回码 {e.returncode}):")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Telegram商家机器人测试运行器")
    parser.add_argument("--type", "-t", 
                       choices=["unit", "integration", "load", "all"], 
                       default="unit",
                       help="测试类型")
    parser.add_argument("--coverage", "-c", 
                       action="store_true",
                       help="启用代码覆盖率报告")
    parser.add_argument("--parallel", "-p", 
                       action="store_true",
                       help="并行运行测试")
    parser.add_argument("--verbose", "-v", 
                       action="store_true",
                       help="详细输出")
    parser.add_argument("--fast", "-f", 
                       action="store_true",
                       help="跳过慢速测试")
    
    args = parser.parse_args()
    
    # 检查pytest是否可用
    try:
        subprocess.run(["pytest", "--version"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("错误: pytest未安装，请先安装依赖:")
        print("pip install pytest pytest-asyncio")
        return 1
    
    # 基础命令
    base_cmd = ["python3", "-m", "pytest"]
    
    # 添加覆盖率选项
    if args.coverage:
        try:
            subprocess.run(["pytest-cov", "--version"], check=True, capture_output=True)
            base_cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
        except subprocess.CalledProcessError:
            print("警告: pytest-cov未安装，跳过覆盖率报告")
    
    # 添加并行选项
    if args.parallel:
        try:
            subprocess.run(["pytest-xdist", "--version"], check=True, capture_output=True)
            base_cmd.extend(["-n", "auto"])
        except subprocess.CalledProcessError:
            print("警告: pytest-xdist未安装，跳过并行执行")
    
    # 添加详细输出
    if args.verbose:
        base_cmd.append("-v")
    
    # 跳过慢速测试
    if args.fast:
        base_cmd.extend(["-m", "not slow"])
    
    success = True
    
    if args.type == "unit":
        # 单元测试
        cmd = base_cmd + ["tests/unit/"]
        success = run_command(cmd, "运行单元测试")
        
    elif args.type == "integration":
        # 集成测试
        cmd = base_cmd + ["tests/integration/"]
        success = run_command(cmd, "运行集成测试")
        
    elif args.type == "load":
        # 负载测试
        cmd = base_cmd + ["tests/load/", "-m", "slow"]
        success = run_command(cmd, "运行负载测试")
        
    elif args.type == "all":
        # 所有测试
        print("运行完整测试套件...")
        
        # 1. 单元测试
        cmd = base_cmd + ["tests/unit/"]
        if not run_command(cmd, "运行单元测试"):
            success = False
        
        # 2. 集成测试
        cmd = base_cmd + ["tests/integration/"]
        if not run_command(cmd, "运行集成测试"):
            success = False
        
        # 3. 负载测试（如果不是快速模式）
        if not args.fast:
            cmd = base_cmd + ["tests/load/"]
            if not run_command(cmd, "运行负载测试"):
                success = False
    
    # 生成测试报告总结
    if success:
        print(f"\n{'='*50}")
        print("✅ 所有测试通过!")
        print(f"{'='*50}")
        
        if args.coverage:
            print("\n📊 覆盖率报告已生成到 htmlcov/ 目录")
            print("可以通过浏览器打开 htmlcov/index.html 查看详细报告")
        
        return 0
    else:
        print(f"\n{'='*50}")
        print("❌ 部分测试失败")
        print(f"{'='*50}")
        return 1


if __name__ == "__main__":
    sys.exit(main())