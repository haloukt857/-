#!/usr/bin/env python3
"""
进程清理工具 - 彻底杀死所有相关进程
使用方法：python3 scripts/cleanup_processes.py
"""

import os
import sys
import signal
import subprocess
import time
import psutil


def kill_by_port(port):
    """根据端口杀死进程"""
    try:
        # 使用lsof查找占用端口的进程
        result = subprocess.run(['lsof', '-ti', f':{port}'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        print(f"✅ 杀死端口{port}的进程 PID:{pid}")
                    except:
                        pass
    except FileNotFoundError:
        # lsof不存在，使用netstat
        try:
            result = subprocess.run(['netstat', '-anp'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTEN' in line:
                    parts = line.split()
                    if len(parts) > 6:
                        pid_program = parts[6]
                        if '/' in pid_program:
                            pid = pid_program.split('/')[0]
                            try:
                                os.kill(int(pid), signal.SIGKILL)
                                print(f"✅ 杀死端口{port}的进程 PID:{pid}")
                            except:
                                pass
        except:
            pass


def kill_by_name(name_patterns):
    """根据进程名杀死进程"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            for pattern in name_patterns:
                if pattern in cmdline:
                    proc.kill()
                    print(f"✅ 杀死进程: {proc.pid} - {cmdline[:60]}...")
                    break
        except:
            pass


def cleanup_all():
    """清理所有相关进程"""
    print("🧹 开始清理所有相关进程...")
    
    # 1. 按端口清理
    ports = [8001, 8002, 8011]
    for port in ports:
        kill_by_port(port)
    
    # 2. 按进程名清理
    patterns = [
        'run.py',
        'main.py', 
        'bot.py',
        'uvicorn',
        'asgi_app',
        'TelegramMerchantBot',
        'scheduler.py'
    ]
    kill_by_name(patterns)
    
    # 3. 等待进程退出
    time.sleep(2)
    
    # 4. 最后检查
    print("🔍 最后检查端口占用...")
    for port in ports:
        try:
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                print(f"⚠️ 端口{port}仍被占用")
            else:
                print(f"✅ 端口{port}已释放")
        except:
            pass
    
    print("🎉 清理完成！")


if __name__ == "__main__":
    cleanup_all()