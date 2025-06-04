# LLM-EVA Docker 环境变量配置文件
# 复制此文件为 .env 并根据实际情况修改配置

MYSQL_DATABASE=llm_eva2
MYSQL_USER=admin
MYSQL_PASSWORD=SXwx2scw3UWP
MYSQL_CHARACTER_SET_SERVER=utf8mb4
MYSQL_COLLATION_SERVER=utf8mb4_unicode_ci

DB_HOST=mysql.mysql-hf04-gg7jdw.svc.hfb.ipaas.cn
DB_PORT=8066
# 请确保与上面的MYSQL配置保持一致

FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=3d6f45a5f7b8c9e1d2a0b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7

SYSTEM_PROVIDER_BASE_URL=http://172.31.114.167/v1
SYSTEM_PROVIDER_API_KEY=ST-xxx

WTF_CSRF_ENABLED=True

WEB_PORT=5001

DATA_UPLOADS_DIR=./data/uploads
DATA_OUTPUTS_DIR=./data/outputs
DATA_LOGS_DIR=./data/logs