#!/usr/bin/env python3
"""
Docker容器启动脚本
"""
import os
import sys
import subprocess

def run_command(cmd, description):
    """运行命令并处理错误"""
    print(f"正在{description}...")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"错误：{description}失败")
        sys.exit(1)

def main():
    """主启动函数"""
    print("=== Docker容器启动 ===")
    
    # 初始化数据库
    run_command("python /app/init_database.py", "初始化数据库")
    
    # 启动Flask应用
    print("启动Flask应用...")
    os.execvp("gunicorn", [
        "gunicorn",
        "--bind", "0.0.0.0:5000",
        "--workers", "4", 
        "--timeout", "120",
        "run:app"
    ])

if __name__ == "__main__":
    main() 