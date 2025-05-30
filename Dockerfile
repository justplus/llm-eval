# 使用Python 3.12作为基础镜像
FROM artifacts.iflytek.com/docker-repo/library/python:3.12-slim as base

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    FLASK_ENV=production \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 依赖安装阶段
FROM base as deps-stage

# 复制requirements.txt并安装Python依赖（单独一层，利用缓存）
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://depend.iflytek.com/artifactory/api/pypi/pypi-repo/simple

# 最终阶段
FROM deps-stage as final

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/uploads /app/outputs /app/instance /app/logs

# 设置权限
RUN chmod +x /app/run.py
RUN chmod +x /app/init_database.py

# 创建启动脚本
COPY start.py /app/start.py
RUN chmod +x /app/start.py

# 暴露端口
EXPOSE 5000

# 使用Python脚本启动
CMD ["python", "/app/start.py"] 