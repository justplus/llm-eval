# 使用Python 3.12作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/uploads /app/outputs /app/instance /app/logs

# 设置权限
RUN chmod +x /app/run.py
RUN chmod +x /app/init_database.py

# 创建启动脚本
RUN echo '#!/bin/bash\n\
    set -e\n\
    \n\
    # 初始化数据库\n\
    echo "正在初始化数据库..."\n\
    python /app/init_database.py\n\
    \n\
    # 启动应用\n\
    echo "启动Flask应用..."\n\
    exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 run:app\n\
    ' > /app/start.sh && chmod +x /app/start.sh

# 暴露端口
EXPOSE 5000

# 设置启动命令
CMD ["/app/start.sh"] 