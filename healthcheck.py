#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康检查脚本
用于检查Flask应用和MySQL数据库的运行状态
"""

import sys
import os
import requests
import pymysql
import time
from urllib.parse import urlparse

def check_database_connection():
    """检查数据库连接"""
    try:
        # 从环境变量获取数据库配置
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = int(os.environ.get('DB_PORT', 3306))
        db_user = os.environ.get('DB_USER', 'llm_user')
        db_password = os.environ.get('DB_PASSWORD', 'llm_password')
        db_name = os.environ.get('DB_NAME', 'llm_eva')
        
        print(f"正在检查数据库连接: {db_host}:{db_port}/{db_name}")
        
        # 尝试连接数据库
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            charset='utf8mb4',
            connect_timeout=10
        )
        
        # 执行简单查询
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            
        connection.close()
        print("✅ 数据库连接正常")
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {str(e)}")
        return False

def check_web_application():
    """检查Web应用"""
    try:
        # 检查应用是否响应
        app_url = "http://localhost:5000"
        print(f"正在检查Web应用: {app_url}")
        
        response = requests.get(app_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Web应用响应正常")
            return True
        else:
            print(f"❌ Web应用响应异常: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Web应用连接失败: 无法连接到服务器")
        return False
    except requests.exceptions.Timeout:
        print("❌ Web应用连接失败: 请求超时")
        return False
    except Exception as e:
        print(f"❌ Web应用检查失败: {str(e)}")
        return False

def check_flask_app_context():
    """检查Flask应用上下文"""
    try:
        print("正在检查Flask应用上下文...")
        
        # 添加应用路径到Python路径
        sys.path.insert(0, '/app')
        
        from app import create_app, db
        from app.models import DatasetCategory, SystemDataset
        
        app = create_app()
        with app.app_context():
            # 检查数据库表是否存在
            from sqlalchemy import text
            result = db.session.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            
            if len(tables) > 0:
                print(f"✅ 发现 {len(tables)} 个数据表")
                
                # 检查初始化数据是否存在
                category_count = DatasetCategory.query.count()
                dataset_count = SystemDataset.query.count()
                
                if category_count > 0 and dataset_count > 0:
                    print(f"✅ 初始化数据完整：{category_count} 个数据集分类，{dataset_count} 个系统数据集")
                    return True
                else:
                    print(f"⚠️  初始化数据不完整：{category_count} 个数据集分类，{dataset_count} 个系统数据集")
                    return False
            else:
                print("⚠️  Flask应用上下文正常，但未发现数据表")
                return False
                
    except Exception as e:
        print(f"❌ Flask应用上下文检查失败: {str(e)}")
        return False

def check_required_directories():
    """检查必要的目录是否存在"""
    try:
        print("正在检查必要目录...")
        
        required_dirs = [
            '/app/uploads',
            '/app/outputs', 
            '/app/logs',
            '/app/instance'
        ]
        
        all_exist = True
        for directory in required_dirs:
            if os.path.exists(directory):
                print(f"✅ 目录存在: {directory}")
            else:
                print(f"❌ 目录不存在: {directory}")
                all_exist = False
                
        return all_exist
        
    except Exception as e:
        print(f"❌ 目录检查失败: {str(e)}")
        return False

def run_database_init():
    """运行数据库初始化脚本"""
    try:
        print("运行数据库初始化脚本...")
        
        import subprocess
        result = subprocess.run(
            [sys.executable, '/app/init_database.py'],
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode == 0:
            print("✅ 数据库初始化脚本执行成功")
            print(result.stdout)
            return True
        else:
            print("❌ 数据库初始化脚本执行失败")
            print(f"错误输出: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ 数据库初始化脚本执行超时")
        return False
    except Exception as e:
        print(f"❌ 执行数据库初始化脚本时发生错误: {str(e)}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("LLM评估系统健康检查")
    print("=" * 50)
    
    checks = [
        ("数据库连接", check_database_connection),
        ("Web应用", check_web_application),
        ("Flask应用上下文", check_flask_app_context),
        ("必要目录", check_required_directories),
        ("数据库初始化", run_database_init)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n🔍 检查项目: {check_name}")
        print("-" * 30)
        
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ 检查过程中发生错误: {str(e)}")
            results.append((check_name, False))
    
    # 输出总结
    print("\n" + "=" * 50)
    print("健康检查总结")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{check_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{total} 项检查通过")
    
    if passed == total:
        print("🎉 所有检查项目都通过了！系统运行正常。")
        sys.exit(0)
    else:
        print("⚠️  部分检查项目失败，请检查系统配置。")
        sys.exit(1)

if __name__ == "__main__":
    main() 