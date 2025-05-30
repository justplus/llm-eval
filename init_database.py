#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
用于Docker容器启动时初始化数据库表和基础数据
"""

import sys
import os
import time
import pymysql

def wait_for_database():
    """等待数据库连接可用"""
    print("等待数据库连接...")
    
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = int(os.environ.get('DB_PORT', 3306))
    db_user = os.environ.get('DB_USER', 'root')
    db_password = os.environ.get('DB_PASSWORD', '')
    db_name = os.environ.get('DB_NAME', 'llm_eva')
    
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            connection = pymysql.connect(
                host=db_host,
                port=db_port,
                user=db_user,
                password=db_password,
                database=db_name,
                connect_timeout=5
            )
            connection.close()
            print("数据库连接成功！")
            return True
        except Exception as e:
            retry_count += 1
            print(f"数据库未就绪，等待5秒... ({retry_count}/{max_retries})")
            time.sleep(5)
    
    print("数据库连接超时！")
    return False

def init_database():
    """初始化数据库表和数据"""
    try:
        from app import create_app, db
        from app.models import init_database_data
        
        print("初始化数据库表和数据...")
        
        app = create_app()
        with app.app_context():
            # 创建所有表
            print("正在创建数据库表...")
            db.create_all()
            print("数据库表创建完成")
            
            # 验证表是否创建成功
            from sqlalchemy import text
            result = db.session.execute(text("SHOW TABLES"))
            tables = [row[0] for row in result.fetchall()]
            print(f"已创建的表: {', '.join(tables)}")
            
            # 初始化基础数据（只在首次部署时执行）
            print("开始初始化基础数据...")
            init_database_data()
            
            # 同步系统模型（在表创建完成后执行）
            print("同步系统模型...")
            try:
                from app.services import model_service
                model_service.sync_system_models()
                print("✅ 系统模型同步完成")
            except Exception as e:
                print(f"⚠️ 系统模型同步失败: {e}")
                # 不影响整体初始化流程
            
        print("数据库初始化完成")
        return True
        
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("开始数据库初始化")
    print("=" * 50)
    
    # 等待数据库可用
    if not wait_for_database():
        sys.exit(1)
    
    # 初始化数据库
    if not init_database():
        sys.exit(1)
    
    print("数据库初始化成功完成！")
    sys.exit(0)

if __name__ == "__main__":
    main() 