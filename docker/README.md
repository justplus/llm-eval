# Docker 部署说明

## 快速开始

1. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，修改相关配置
   ```

2. **构建并启动服务**
   ```bash
   # 构建镜像并启动服务
   docker-compose up -d --build
   ```

3. **查看服务状态**
   ```bash
   docker-compose ps
   docker-compose logs -f web
   ```

## 注意事项

- 首次启动会自动创建数据库表和初始化数据
- 请确保修改默认密码和API密钥
- 数据持久化存储在 mysql_data volume 中