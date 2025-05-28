#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开发环境启动脚本
提供便捷的开发功能，包括自动重载、调试模式等
"""

import os
import sys
import argparse
from app import create_app

def main():
    parser = argparse.ArgumentParser(description='Flask开发服务器启动脚本')
    parser.add_argument('--port', '-p', type=int, default=5000, help='端口号 (默认: 5000)')
    parser.add_argument('--host', default='0.0.0.0', help='主机地址 (默认: 0.0.0.0)')
    parser.add_argument('--no-debug', action='store_true', help='禁用调试模式')
    parser.add_argument('--no-reload', action='store_true', help='禁用自动重载')
    parser.add_argument('--sql-echo', action='store_true', help='启用SQL查询日志')
    parser.add_argument('--config', choices=['development', 'production'], 
                       default='development', help='配置环境 (默认: development)')
    
    args = parser.parse_args()
    
    # 设置环境变量
    os.environ['FLASK_ENV'] = args.config
    if args.sql_echo:
        os.environ['SQLALCHEMY_ECHO'] = 'true'
    
    # 创建应用
    app = create_app(args.config)
    
    # 确定运行参数
    debug_mode = not args.no_debug and args.config == 'development'
    use_reloader = not args.no_reload and args.config == 'development'
    
    # 输出启动信息
    print("=" * 60)
    print("🚀 Flask开发服务器启动中...")
    print("=" * 60)
    print(f"📍 访问地址: http://{args.host}:{args.port}")
    print(f"🔧 运行环境: {args.config}")
    print(f"🐛 调试模式: {'开启' if debug_mode else '关闭'}")
    print(f"🔄 自动重载: {'开启' if use_reloader else '关闭'}")
    print(f"📊 SQL日志: {'开启' if args.sql_echo else '关闭'}")
    print(f"📄 模板重载: {'开启' if app.config.get('TEMPLATES_AUTO_RELOAD') else '关闭'}")
    print("-" * 60)
    print("💡 开发提示:")
    print("   • 修改Python代码后应用会自动重启")
    print("   • 修改模板文件后会自动重载")
    print("   • 按 Ctrl+C 停止服务器")
    print("   • 使用 --help 查看更多选项")
    print("=" * 60)
    
    try:
        app.run(
            debug=debug_mode,
            host=args.host,
            port=args.port,
            use_reloader=use_reloader,
            use_debugger=debug_mode,
            threaded=True,
            extra_files=None  # 可以添加额外监控的文件
        )
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 