import os
from dotenv import load_dotenv

# Load environment variables from .env or .flaskenv file
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-default-fallback-secret-key'
    
    # 禁用CSRF保护，因为部署在内部网络环境
    WTF_CSRF_ENABLED = False
    
    # Default to SQLite if DATABASE_URL is not set, for easier initial setup.
    # However, the requirement is MySQL, so DATABASE_URL should be set in .flaskenv.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Fernet key for encrypting sensitive data like API keys
    FERNET_ENCRYPTION_KEY = os.environ.get('FERNET_ENCRYPTION_KEY') or \
                                 'thisIsAWeakFallbackKeyPleaseSetItProperly' # Fallback, user MUST set this

    SYSTEM_PROVIDER_API_KEY = os.environ.get('SYSTEM_OPENAI_API_KEY') # Re-using old name for user convenience
    SYSTEM_PROVIDER_BASE_URL = os.environ.get('SYSTEM_PROVIDER_BASE_URL')

    DEFAULT_MODEL_API_KEY = os.environ.get('DEFAULT_MODEL_API_KEY')

    # You can add other configurations here, e.g., for email, etc.    