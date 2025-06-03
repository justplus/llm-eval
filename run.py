from flask import Flask
from app import create_app, db
from app.models import User, AIModel, ChatSession, ChatMessage
import logging  # 添加logging模块导入
import argparse  # 添加命令行参数解析
import os

def create_database_if_not_exists():
    """创建数据库（如果不存在）"""
    try:
        import pymysql
        from urllib.parse import urlparse
        
        # 从配置中获取数据库连接信息
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = int(os.environ.get('DB_PORT', '3306'))
        db_user = os.environ.get('DB_USER', os.environ.get('MYSQL_USER', 'root'))
        db_password = os.environ.get('DB_PASSWORD', os.environ.get('MYSQL_PASSWORD', ''))
        db_name = os.environ.get('DB_NAME', os.environ.get('MYSQL_DATABASE', 'llm_eva'))
        
        # 先连接到MySQL服务器（不指定数据库）
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            charset='utf8mb4'
        )
        
        try:
            with connection.cursor() as cursor:
                # 检查数据库是否存在
                cursor.execute(f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{db_name}'")
                result = cursor.fetchone()
                
                if not result:
                    print(f"🔧 数据库 '{db_name}' 不存在，正在创建...")
                    cursor.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                    connection.commit()
                    print(f"✅ 数据库 '{db_name}' 创建成功")
                else:
                    print(f"📊 数据库 '{db_name}' 已存在")
                    
        finally:
            connection.close()
            
    except Exception as e:
        print(f"⚠️ 创建数据库时出错: {e}")
        print("🔧 请确保MySQL服务正在运行，并且用户有创建数据库的权限")
        return False
    
    return True

def check_and_init_database(app):
    """检查并初始化数据库"""
    try:
        # 首先确保数据库存在
        if not create_database_if_not_exists():
            return False
            
        with app.app_context():
            # 检查数据库是否存在表
            from sqlalchemy import text, inspect
            
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if not tables:
                print("🔧 数据库为空，开始初始化...")
                
                # 创建所有表
                print("📝 正在创建数据库表...")
                db.create_all()
                print("✅ 数据库表创建完成")
                
                # 验证表是否创建成功
                try:
                    result = db.session.execute(text("SHOW TABLES"))
                    tables = [row[0] for row in result.fetchall()]
                    print(f"📊 已创建的表: {', '.join(tables) if tables else '无'}")
                except Exception as e:
                    print(f"⚠️ 无法检索表信息: {e}")
                
                # 初始化基础数据
                print("🔄 正在初始化基础数据...")
                try:
                    from app.models import init_database_data
                    init_database_data()
                    print("✅ 基础数据初始化完成")
                except Exception as e:
                    print(f"⚠️ 基础数据初始化失败: {e}")
                
                # 同步系统模型
                print("🤖 正在同步系统模型...")
                try:
                    from app.services import model_service
                    model_service.sync_system_models()
                    print("✅ 系统模型同步完成")
                except Exception as e:
                    print(f"⚠️ 系统模型同步失败: {e}")
                
                print("🎉 数据库初始化完成！")
            else:
                print(f"📊 数据库已存在 {len(tables)} 个表，跳过初始化")
                
    except Exception as e:
        print(f"❌ 数据库检查失败: {e}")
        print("⚠️ 应用将继续启动，但可能需要手动初始化数据库")
        return False
    
    return True

# 创建应用实例 - 这是Flask命令行工具寻找的变量
app = create_app()

# 配置根日志级别为INFO
logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    # 添加命令行参数支持
    parser = argparse.ArgumentParser(description='运行Flask应用')
    parser.add_argument('--port', type=int, default=5000, help='端口号 (默认: 5000)')
    parser.add_argument('--host', default='0.0.0.0', help='主机地址 (默认: 0.0.0.0)')
    parser.add_argument('--no-debug', action='store_true', help='禁用调试模式')
    parser.add_argument('--no-reload', action='store_true', help='禁用自动重载')
    parser.add_argument('--skip-db-init', action='store_true', help='跳过数据库初始化检查')
    
    args = parser.parse_args()
    
    # 数据库初始化检查（除非明确跳过）
    if not args.skip_db_init:
        print("=" * 60)
        print("🗄️ 数据库检查阶段")
        print("=" * 60)
        check_and_init_database(app)
        print()
    
    # 确定是否启用调试模式和自动重载
    debug_mode = not args.no_debug
    use_reloader = not args.no_reload
    
    print(f"🚀 启动Flask应用...")
    print(f"📍 地址: http://{args.host}:{args.port}")
    print(f"🔧 调试模式: {'开启' if debug_mode else '关闭'}")
    print(f"🔄 自动重载: {'开启' if use_reloader else '关闭'}")
    print(f"🗄️ 数据库检查: {'已跳过' if args.skip_db_init else '已完成'}")
    print(f"💡 提示: 修改代码后应用会自动重启")
    print("-" * 50)
    
    app.run(
        debug=debug_mode,
        host=args.host,
        port=args.port,
        use_reloader=use_reloader,
        use_debugger=debug_mode,
        threaded=True  # 启用多线程支持
    ) 