# LLM评估系统 Docker部署指南

## 概述

本文档介绍如何使用Docker部署LLM评估系统，包括Flask应用和MySQL数据库。

## 系统要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少4GB可用内存
- 至少10GB可用磁盘空间

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd llm-eva
```

### 2. 配置环境变量

编辑 `docker-compose.yml` 文件中的环境变量，特别是以下配置：

```yaml
# API配置（请根据实际情况修改）
SYSTEM_OPENAI_API_KEY: "你的实际API密钥"
DEFAULT_MODEL_API_KEY: "你的实际API密钥"
SYSTEM_PROVIDER_BASE_URL: "你的实际API基础URL"
SYSTEM_PROVIDER_API_KEY: "你的实际API密钥"
```

### 3. 构建并启动服务

```bash
# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f web
```

### 4. 访问应用

应用启动后，可以通过以下地址访问：

- Web应用: http://localhost:5000
- MySQL数据库: localhost:3306

## 服务说明

### MySQL数据库服务

- **镜像**: mysql:8.0
- **端口**: 3306
- **数据库名**: llm_eva
- **用户名**: llm_user
- **密码**: llm_password
- **数据持久化**: 使用Docker volume `mysql_data`

### Flask Web应用服务

- **基础镜像**: python:3.9-slim
- **端口**: 5000
- **工作目录**: /app
- **启动方式**: Gunicorn (4个worker进程)

## 数据库初始化

系统使用独立的初始化脚本 `init_database.py` 来管理数据库初始化：

### 自动初始化流程

1. 容器启动时自动执行 `init_database.py`
2. 脚本会等待MySQL数据库启动（最多等待150秒）
3. 创建Flask应用所需的数据表
4. 检查并初始化基础数据（数据集分类、系统数据集等）
   - 只在数据库为空时执行，避免重复插入
   - 使用Python代码管理，更加优雅和可控

### 手动初始化数据库

如果需要手动重新初始化数据库数据，可以使用以下命令：

```bash
# 方法1：进入容器执行初始化脚本
docker-compose exec web python /app/init_database.py

# 方法2：使用Flask CLI命令
docker-compose exec web flask init-db

# 方法3：使用健康检查脚本（包含初始化功能）
docker-compose exec web python /app/healthcheck.py
```

### 初始化脚本特点

- **独立脚本**: `init_database.py` 是一个独立的Python脚本，代码清晰易维护
- **智能等待**: 自动等待数据库可用，支持重试机制
- **错误处理**: 完善的错误处理和日志输出
- **幂等性**: 可以安全地多次执行，不会重复插入数据

### 数据库初始化内容

- **数据集分类**: 包含函数调用、创作、多模态等12个分类
- **系统数据集**: 包含CMMLU、E-EVAL、C-Eval等评估数据集
- **自动检查**: 只在表为空时插入，避免重复数据

## 目录结构

```
llm-eva/
├── Dockerfile              # Flask应用的Docker镜像定义
├── docker-compose.yml      # Docker Compose配置文件
├── requirements.txt        # Python依赖包列表
├── init.sql               # 数据库初始化脚本
├── run.py                 # Flask应用入口文件
├── app/                   # Flask应用代码
├── uploads/               # 文件上传目录（挂载到容器）
├── outputs/               # 输出文件目录（挂载到容器）
└── logs/                  # 日志文件目录（挂载到容器）
```

## 常用命令

### 启动服务

```bash
# 后台启动所有服务
docker-compose up -d

# 重新构建并启动
docker-compose up -d --build

# 启动特定服务
docker-compose up -d mysql
docker-compose up -d web
```

### 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷（注意：会删除数据库数据）
docker-compose down -v
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs

# 查看特定服务日志
docker-compose logs web
docker-compose logs mysql

# 实时查看日志
docker-compose logs -f web
```

### 进入容器

```bash
# 进入Web应用容器
docker-compose exec web bash

# 进入MySQL容器
docker-compose exec mysql bash

# 连接MySQL数据库
docker-compose exec mysql mysql -u llm_user -p llm_eva
```

## 数据备份与恢复

### 备份数据库

```bash
# 备份数据库到文件
docker-compose exec mysql mysqldump -u llm_user -p llm_eva > backup.sql
```

### 恢复数据库

```bash
# 从备份文件恢复数据库
docker-compose exec -T mysql mysql -u llm_user -p llm_eva < backup.sql
```

## 生产环境部署建议

### 1. 安全配置

- 修改默认密码和密钥
- 使用HTTPS
- 配置防火墙规则
- 定期更新镜像

### 2. 性能优化

- 根据服务器配置调整Gunicorn worker数量
- 配置MySQL参数优化
- 使用外部MySQL服务（如云数据库）

### 3. 监控和日志

- 配置日志轮转
- 设置监控告警
- 定期备份数据

### 4. 扩展配置

```yaml
# 在docker-compose.yml中添加资源限制
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查MySQL服务是否启动
   - 验证数据库连接参数
   - 查看网络连接

2. **应用启动失败**
   - 检查Python依赖是否正确安装
   - 查看应用日志
   - 验证环境变量配置

3. **端口冲突**
   - 修改docker-compose.yml中的端口映射
   - 检查本地端口占用情况

### 调试命令

```bash
# 检查容器状态
docker-compose ps

# 查看容器资源使用情况
docker stats

# 检查网络连接
docker-compose exec web ping mysql

# 测试数据库连接
docker-compose exec web python -c "
import pymysql
conn = pymysql.connect(host='mysql', user='llm_user', password='llm_password', database='llm_eva')
print('数据库连接成功')
conn.close()
"
```

## 更新和维护

### 更新应用代码

```bash
# 停止服务
docker-compose down

# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build
```

### 更新依赖包

```bash
# 修改requirements.txt后重新构建
docker-compose build web
docker-compose up -d web
```

## 联系支持

如果遇到问题，请检查：

1. Docker和Docker Compose版本
2. 系统资源使用情况
3. 网络连接状态
4. 日志文件内容

更多技术支持，请联系开发团队。 