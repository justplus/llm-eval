from flask import Flask, g, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from .config import Config
import datetime
import logging  # 添加logging模块导入

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "请登录以访问此页面。"
login_manager.login_message_category = "info"

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
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

    with app.app_context():
        from app.services import model_service
        model_service.sync_system_models()

    # 错误处理器，需要正确缩进到create_app函数内部
    @app.errorhandler(403)
    def forbidden_error(error):
        flash("您的会话已过期或无权访问此页面，请重新登录。", "warning")
        return redirect(url_for('auth.login'))

    return app
