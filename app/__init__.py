from flask import Flask, g, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from .config import Config
import datetime
import logging  # 添加logging模块导入
from app.adapter.general_intent_adapter import register_genera_intent_benchmark

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "请登录以访问此页面。"
login_manager.login_message_category = "info"

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
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
