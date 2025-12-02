# 快速开始

本文档介绍如何通过单个 `docker-compose.yml` 快速拉起 Code Review GPT Gitlab 的体验环境，后端镜像由 `docker/backend/Dockerfile` 构建，可提前安装系统依赖。

## 前置要求

- Docker 20.10+
- Docker Compose v2（Docker Desktop 已内置）
- 至少 2 GB 可用内存 & 3 GB 磁盘空间

## 快速开始

### 1. 克隆项目并配置变量

```bash
git clone https://github.com/your-username/Code-Review-GPT-Gitlab.git
cd Code-Review-GPT-Gitlab
cp .env.example .env
# 编辑 .env，填入 GitLab 等基础访问配置（LLM/通知渠道在系统内配置）
```

### 2. 启动服务

```bash
# 首次启动会自动安装 Python/Node 依赖，需要几分钟
docker compose up -d

# 查看状态
docker compose ps

# 跟踪日志
docker compose logs -f backend
```

服务启动后：
- 前端：http://localhost:3000（Vite Dev Server）
- 后端：http://localhost:8000（Gunicorn）
- 管理后台：http://localhost:8000/admin/

停服清理：`docker compose down`

## 服务说明

| 服务 | 镜像 | 说明 |
| --- | --- | --- |
| backend | 自建镜像（基于 python:3.11-slim） | 通过 `docker/backend/Dockerfile` 安装系统依赖与 Python 包，运行时挂载 `backend/` 并执行迁移 + Gunicorn |
| frontend | node:18-alpine | 挂载 `frontend/`，启动时 `npm install` + `npm run dev` |
| redis | redis:7.2-alpine | 默认内存运行，无持久化 |

`frontend-node-modules` 命名卷用于缓存前端依赖，避免每次启动重复安装。

> LLM 参数和通知渠道统一在系统运行后通过 `LLMConfig` / `NotificationChannel` 管理，无需配置环境变量。

## 常用操作

```bash
# 查看日志
docker compose logs -f frontend

# 进入容器
docker compose exec backend bash
docker compose exec frontend sh

# 执行 Django 管理命令
docker compose exec backend python manage.py createsuperuser

# 安装新的前端依赖
docker compose exec frontend npm install <pkg>
```

## 故障排除

1. **容器无法启动**
   ```bash
   docker compose logs backend
   docker compose restart backend
   ```

2. **端口冲突**
   ```bash
   lsof -i :3000
   lsof -i :8000
   lsof -i :6379
   ```

3. **依赖安装缓慢或失败**
   - 配置国内 npm/pip 源
   - 重新执行 `docker compose up --force-recreate`

4. **环境变量未生效**
   ```bash
   docker compose up -d --force-recreate
   ```

## 生产部署建议

当前 Compose 主要用于本地体验：
- 如果线上仍需 Docker，可在 `docker/backend/Dockerfile` 中固化更多依赖，或另外编写适合的 Dockerfile/Compose，配置持久化、HTTPS 等
- 若不使用 Docker，可直接参考源码部署流程（pip + npm）

完成体验后，执行 `docker compose down` 释放资源。
