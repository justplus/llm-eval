import os
from dotenv import load_dotenv

# Load environment variables from .env or .flaskenv file
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-default-fallback-secret-key'
    
    # 禁用CSRF保护，因为部署在内部网络环境
    WTF_CSRF_ENABLED = False
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FERNET_ENCRYPTION_KEY = os.environ.get('FERNET_ENCRYPTION_KEY') or \
                                 'thisIsAWeakFallbackKeyPleaseSetItProperly' # Fallback, user MUST set this

    SYSTEM_PROVIDER_API_KEY = os.environ.get('SYSTEM_OPENAI_API_KEY') # Re-using old name for user convenience
    SYSTEM_PROVIDER_BASE_URL = os.environ.get('SYSTEM_PROVIDER_BASE_URL')

    DEFAULT_MODEL_API_KEY = os.environ.get('DEFAULT_MODEL_API_KEY')

    # 文件上传配置
    DATASET_UPLOAD_FOLDER = os.environ.get('DATASET_UPLOAD_FOLDER')
    
    # 文件大小限制配置
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))  # 默认50MB
    DATASET_MAX_FILE_SIZE = int(os.environ.get('DATASET_MAX_FILE_SIZE', 50 * 1024 * 1024))  # 50MB
    DATASET_LARGE_FILE_THRESHOLD = int(os.environ.get('DATASET_LARGE_FILE_THRESHOLD', 10 * 1024 * 1024))  # 10MB
    
    # 文件验证配置 - 已优化为只验证前5行，避免大文件导致系统卡顿
    # DATASET_MAX_VALIDATION_LINES 和 DATASET_VALIDATION_SAMPLE_SIZE 已移除，因为现在固定验证前5行

    # You can add other configurations here, e.g., for email, etc.

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    DEVELOPMENT = True
    
    # 开发环境下启用更详细的日志
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    
    # 开发环境下的模板自动重载
    TEMPLATES_AUTO_RELOAD = True
    
    # 发送文件的缓存超时时间（开发环境设为1秒，便于调试静态文件）
    SEND_FILE_MAX_AGE_DEFAULT = 1

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    DEVELOPMENT = False
    
    # 生产环境下禁用模板自动重载
    TEMPLATES_AUTO_RELOAD = False
    
    # 生产环境下的静态文件缓存时间
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1年

# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}    