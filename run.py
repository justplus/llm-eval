from flask import Flask
from app import create_app, db
from app.models import User, AIModel, ChatSession, ChatMessage
import logging  # 添加logging模块导入

# 创建应用实例 - 这是Flask命令行工具寻找的变量
app = create_app()

# 配置根日志级别为INFO
logging.basicConfig(level=logging.INFO)

# @app.shell_context_processor
# def make_shell_context():
#     """提供shell上下文，用于flask shell命令"""
#     return {'db': db, 'User': User, 'AIModel': AIModel, 'ChatSession': ChatSession, 'ChatMessage': ChatMessage}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') 