FLASK_APP=run.py
FLASK_ENV=development

# TODO: Replace with your actual database URL
# Example for MySQL with PyMySQL: mysql+pymysql://username:password@host:port/database_name
# Example for SQLite (for quick local testing, not for production with MySQL requirement):
# DATABASE_URL="sqlite:///app.db"
DATABASE_URL="mysql+pymysql://admin:SXwx2scw3UWP@mysql.mysql-hf04-gg7jdw.svc.hfb.ipaas.cn:8066/llm_eva"

# TODO: Generate a strong secret key and replace this
SECRET_KEY="3d6f45a5f7b8c9e1d2a0b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7"

# TODO: Generate a Fernet key (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") and replace this
FERNET_ENCRYPTION_KEY="YHNmcnQ_JFnvLH-1MeAUjhtuIkdn2TLCXEEGQZx9yBo="

SYSTEM_PROVIDER_API_KEY="sk-yourGlobalOpenAIKey"

# API Key for the System Model Provider (e.g., your model packager)
# This key is used by the application to fetch the list of available system models.
# Ensure the name 'SYSTEM_OPENAI_API_KEY' is used here as app.config.py reads this specific environment variable name.
SYSTEM_OPENAI_API_KEY="ST-xxx" # TODO: Replace ST-xxx with your actual System Provider API Key

DEFAULT_MODEL_API_KEY="ST-xxx"

# Base URL for the System Model Provider
SYSTEM_PROVIDER_BASE_URL="http://172.31.114.167/v1" # TODO: Verify or update this URL as needed