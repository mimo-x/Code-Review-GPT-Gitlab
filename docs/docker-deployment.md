# Docker 部署指南

本文档介绍如何使用Docker部署Code Review GPT Gitlab项目。

## 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少2GB可用内存
- 至少5GB可用磁盘空间

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/Code-Review-GPT-Gitlab.git
cd Code-Review-GPT-Gitlab
```

### 2. 配置环境变量

```bash
# 开发环境
cp .env.example .env

# 生产环境
cp .env.prod.example .env.prod
```

编辑 `.env` 文件，填入必要的配置信息：

```bash
# 必须配置的项
SECRET_KEY=your-secret-key
GITLAB_PRIVATE_TOKEN=your-gitlab-token
LLM_API_KEY=your-llm-api-key
```

### 3. 启动服务

#### 开发环境

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

#### 生产环境

```bash
# 启动生产环境
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f

# 停止服务
docker-compose -f docker-compose.prod.yml down
```

## 服务访问

启动成功后，可以通过以下地址访问：

- **前端应用**: http://localhost:3000 (开发) / http://localhost (生产)
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/api/docs/
- **管理后台**: http://localhost:8000/admin/

## 开发工具（可选）

启用开发工具：

```bash
# 启动包含开发工具的环境
docker-compose --profile tools up -d
```

可用的开发工具：

- **Adminer**: http://localhost:8080 (数据库管理)

## 常用命令

### 服务管理

```bash
# 启动服务
docker-compose up -d

# 重新构建并启动
docker-compose up -d --build

# 停止服务
docker-compose down

# 重启特定服务
docker-compose restart backend

# 查看服务状态
docker-compose ps
```

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs

# 查看特定服务日志
docker-compose logs backend

# 实时跟踪日志
docker-compose logs -f frontend
```

### 数据管理

```bash
# 进入后端容器
docker-compose exec backend bash

# 备份数据库
docker-compose exec backend python manage.py dumpdata > backup.json

# 恢复数据库
docker-compose exec backend python manage.py loaddata backup.json
```

### 清理操作

```bash
# 停止并删除所有容器
docker-compose down --remove-orphans

# 删除所有数据卷（慎用！）
docker-compose down -v

# 清理未使用的镜像和容器
docker system prune -a
```

## 环境变量详解

### 必需配置

- `SECRET_KEY`: Django密钥
- `GITLAB_PRIVATE_TOKEN`: GitLab访问令牌
- `LLM_API_KEY`: 大语言模型API密钥

### 数据库配置

- `DATABASE_NAME`: 数据库名称
- `SQLITE_DATABASE`: SQLite数据库文件路径

### LLM配置

- `LLM_PROVIDER`: LLM提供商（deepseek, openai, claude等）
- `LLM_API_BASE`: LLM API基础地址
- `LLM_MODEL`: 使用的模型名称

### 通知配置

- `DINGDING_BOT_WEBHOOK`: 钉钉机器人Webhook
- `SLACK_WEBHOOK_URL`: Slack Webhook URL
- `FEISHU_WEBHOOK_URL`: 飞书Webhook URL

## 生产环境部署

### 1. 安全配置

```bash
# 生成强密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 配置HTTPS
# 编辑 docker-compose.prod.yml 中的nginx配置
```

### 2. 数据持久化

生产环境的数据会持久化到以下目录：

```
./data/
├── redis/          # Redis数据
├── media/          # 用户上传文件
└── logs/           # 应用日志
```

### 3. 监控和日志

```bash
# 查看资源使用情况
docker stats

# 设置日志轮转
# 编辑 /etc/docker/daemon.json
```

### 4. 备份策略

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec backend python manage.py dumpdata > backup_$DATE.json
tar -czf backup_$DATE.tar.gz ./data/ backup_$DATE.json
```

## 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 检查端口占用
   netstat -tulpn | grep :8000

   # 修改docker-compose.yml中的端口映射
   ```

2. **权限问题**
   ```bash
   # 修复文件权限
   sudo chown -R $USER:$USER ./data/
   ```

3. **内存不足**
   ```bash
   # 检查内存使用
   docker stats

   # 调整Docker内存限制
   ```

4. **网络连接问题**
   ```bash
   # 检查网络连接
   docker-compose exec backend ping redis

   # 重建网络
   docker-compose down
   docker network prune
   docker-compose up -d
   ```

### 日志分析

```bash
# 查看错误日志
docker-compose logs backend | grep ERROR

# 查看访问日志
docker-compose exec nginx tail -f /var/log/nginx/access.log
```

## 更新和升级

```bash
# 拉取最新代码
git pull origin main

# 重新构建并启动
docker-compose up -d --build

# 数据库迁移
docker-compose exec backend python manage.py migrate
```

## 支持和帮助

如果在部署过程中遇到问题，请：

1. 检查日志文件
2. 查看GitHub Issues
3. 提交新的Issue并提供详细的错误信息

---

更多详细信息请参考项目README.md文件。