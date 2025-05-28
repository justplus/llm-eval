from flask import Flask, g, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from .config import config
import datetime
import logging  # 添加logging模块导入
import os  # 添加os模块导入
from app.adapter.general_intent_adapter import register_genera_intent_benchmark
# 导入数据集插件，确保@register_dataset装饰器能够正确注册
from app.adapter.general_intent_dataset_plugin import CustomDatasetPlugin

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "请登录以访问此页面。"
login_manager.login_message_category = "info"

def create_app(config_name=None):
    """创建Flask应用实例
    
    Args:
        config_name: 配置名称 ('development', 'production', 'default')
                    如果为None，则从环境变量FLASK_ENV获取
    """
    app = Flask(__name__)
    
    # 确定配置类
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    config_class = config.get(config_name, config['default'])
    app.config.from_object(config_class)
    
    # 输出当前配置信息
    app.logger.info(f"🔧 使用配置: {config_name}")
    app.logger.info(f"🐛 调试模式: {'开启' if app.config.get('DEBUG') else '关闭'}")
    app.logger.info(f"📄 模板自动重载: {'开启' if app.config.get('TEMPLATES_AUTO_RELOAD') else '关闭'}")
    
    # 会话配置
    app.config['SESSION_COOKIE_SECURE'] = False  # 开发环境设为False，生产环境应设为True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=24)  # 会话24小时过期
    
    # 配置日志级别，确保INFO级别的日志能够显示
    app.logger.setLevel(logging.INFO)
    # 如果需要更详细的控制台输出格式，可以添加以下代码
    if not app.debug:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # 添加自定义Jinja2过滤器
    @app.template_filter('from_json')
    def from_json_filter(value):
        """将JSON字符串或Python字典字符串转换为Python对象，如果失败返回None"""
        import json
        import ast
        try:
            # 首先尝试标准JSON解析
            return json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            try:
                # 如果JSON解析失败，尝试使用ast.literal_eval解析Python字典格式
                return ast.literal_eval(value)
            except (ValueError, SyntaxError, TypeError):
                return None

    @app.template_filter('clean_json')
    def clean_json_filter(value):
        """清理模型回答中的JSON格式，去掉代码块标记并压缩JSON"""
        import json
        import re
        
        if not value:
            return value
            
        # 去掉开头的```json或```和结尾的```
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', value.strip())
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        
        # 尝试解析并压缩JSON
        try:
            # 尝试解析为JSON对象
            json_obj = json.loads(cleaned)
            # 返回压缩的JSON字符串（不带缩进和空格）
            return json.dumps(json_obj, ensure_ascii=False, separators=(',', ':'))
        except (json.JSONDecodeError, TypeError, ValueError):
            # 如果不是有效的JSON，返回清理后的文本
            return cleaned.strip()

    @app.before_request
    def global_vars_before_request():
        g.year = datetime.date.today().year
        
        # 处理损坏的会话数据
        from flask import session, request
        try:
            # 尝试访问会话数据，如果损坏会抛出异常
            _ = session.get('_user_id')
        except Exception as e:
            app.logger.warning(f"Session data corrupted, clearing session: {e}")
            session.clear()
            # 只对需要登录的页面进行重定向
            # 数据集列表等页面不需要登录，所以不应该强制重定向

    @app.after_request
    def after_request(response):
        # 添加缓存控制头，防止缓存问题
        if response.status_code >= 400:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    # 注册蓝图
    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.models_routes import bp as models_bp
    app.register_blueprint(models_bp)

    from app.routes.chat_routes import bp as chat_bp
    app.register_blueprint(chat_bp)

    # 注册新的数据集蓝图
    from app.routes.dataset_routes import bp as datasets_bp
    app.register_blueprint(datasets_bp)

    from app.routes.evaluation_routes import bp as evaluations_bp
    app.register_blueprint(evaluations_bp)

    # 注册性能评估蓝图
    from app.routes.perf_eval import perf_eval_bp
    app.register_blueprint(perf_eval_bp)

    register_genera_intent_benchmark()

    with app.app_context():
        from app.services import model_service
        model_service.sync_system_models()

    # 错误处理器，需要正确缩进到create_app函数内部
    @app.errorhandler(400)
    def bad_request_error(error):
        app.logger.warning(f"400 Bad Request: {error}")
        # 清除可能损坏的会话数据
        from flask import session
        session.clear()
        flash("请求无效，可能是会话过期导致的。", "warning")
        return render_template('errors/session_error.html', 
                             title='会话错误',
                             error_message="请求无效，可能是会话过期导致的。",
                             clear_session_url=url_for('auth.clear_session')), 400

    @app.errorhandler(403)
    def forbidden_error(error):
        app.logger.warning(f"403 Forbidden: {error}")
        from flask import session
        session.clear()
        flash("您的会话已过期或无权访问此页面。", "warning")
        return render_template('errors/session_error.html', 
                             title='访问被拒绝',
                             error_message="您的会话已过期或无权访问此页面。",
                             clear_session_url=url_for('auth.clear_session')), 403

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 Internal Server Error: {error}")
        db.session.rollback()
        flash("服务器内部错误，请稍后重试。", "error")
        return redirect(url_for('main.index'))

    return app
