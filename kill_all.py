#!/usr/bin/env python3
"""
快速清理工具 - 一键杀死所有相关进程
使用方法：python3 kill_all.py
"""
import os
import sys
import subprocess
import signal

def main():
    print("🔥 强制清理所有相关进程...")
    
    # 1. 按端口清理
    ports = [8001, 8002, 8011]
    for port in ports:
        try:
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                  capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                            print(f"✅ 清理端口{port}: PID {pid}")
                        except:
                            pass
        except:
            pass
    
    # 2. 按名称清理
    try:
        subprocess.run(['pkill', '-f', 'run.py'], check=False)
        subprocess.run(['pkill', '-f', 'uvicorn'], check=False) 
        subprocess.run(['pkill', '-f', 'asgi_app'], check=False)
        print("✅ 清理相关Python进程")
    except:
        pass
    
    print("🎉 清理完成！现在可以重新启动。")

if __name__ == "__main__":
    main()