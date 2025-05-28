from flask import Flask
from app import create_app, db
from app.models import User, AIModel, ChatSession, ChatMessage
import logging  # 添加logging模块导入
import argparse  # 添加命令行参数解析

# 创建应用实例 - 这是Flask命令行工具寻找的变量
app = create_app()

# 配置根日志级别为INFO
logging.basicConfig(level=logging.INFO)

# @app.shell_context_processor
# def make_shell_context():
#     """提供shell上下文，用于flask shell命令"""
#     return {'db': db, 'User': User, 'AIModel': AIModel, 'ChatSession': ChatSession, 'ChatMessage': ChatMessage}

if __name__ == '__main__':
    # 添加命令行参数支持
    parser = argparse.ArgumentParser(description='运行Flask应用')
    parser.add_argument('--port', type=int, default=5000, help='端口号 (默认: 5000)')
    parser.add_argument('--host', default='0.0.0.0', help='主机地址 (默认: 0.0.0.0)')
    parser.add_argument('--no-debug', action='store_true', help='禁用调试模式')
    parser.add_argument('--no-reload', action='store_true', help='禁用自动重载')
    
    args = parser.parse_args()
    
    # 确定是否启用调试模式和自动重载
    debug_mode = not args.no_debug
    use_reloader = not args.no_reload
    
    print(f"🚀 启动Flask应用...")
    print(f"📍 地址: http://{args.host}:{args.port}")
    print(f"🔧 调试模式: {'开启' if debug_mode else '关闭'}")
    print(f"🔄 自动重载: {'开启' if use_reloader else '关闭'}")
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