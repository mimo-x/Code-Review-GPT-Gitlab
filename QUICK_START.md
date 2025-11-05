# 快速开始指南

> 10 分钟内完成 Code Review GPT (Django + MongoDB) 的部署和配置

## 前置要求

- Docker 和 Docker Compose (推荐)
- 或 Python 3.8+ 和 MongoDB

## 方式一：Docker Compose (最简单,推荐)

### 1. 克隆项目

```bash
git clone git@github.com:mimo-x/Code-Review-GPT-Gitlab.git
cd Code-Review-GPT-Gitlab/backend
```

### 2. 配置环境变量

```bash
# 复制配置示例
cp .env.example .env

# 编辑配置文件
vim .env
```

**最少需要配置以下项:**

```bash
# GitLab 配置 (必需)
GITLAB_SERVER_URL=https://gitlab.com
GITLAB_PRIVATE_TOKEN=your-gitlab-token

# LLM 配置 (必需)
LLM_PROVIDER=deepseek
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat
```

### 3. 启动服务

```bash
docker-compose up -d
```

就这么简单! 🎉

### 4. 验证服务

```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker-compose logs -f django

# 健康检查
curl http://localhost:8000/health/
```

应该看到:
```json
{"status": "ok", "message": "Code Review GPT is running"}
```

### 5. 配置 GitLab Webhook

1. 打开你的 GitLab 项目
2. 进入 **Settings** > **Webhooks**
3. 添加 Webhook URL: `http://your-server-ip:8000/api/webhook/gitlab/`
4. 勾选 **Merge request events**
5. 点击 **Add webhook**

### 6. 测试

创建一个 Merge Request,等待代码审查评论! ✨

---

## 方式二：本地开发

### 1. 准备环境

```bash
# 克隆项目
git clone git@github.com:mimo-x/Code-Review-GPT-Gitlab.git
cd Code-Review-GPT-Gitlab/backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate
```

### 2. 安装 MongoDB

**macOS:**
```bash
brew install mongodb-community
brew services start mongodb-community
```

**Ubuntu/Debian:**
```bash
sudo apt-get install mongodb
sudo systemctl start mongodb
```

**或使用 Docker:**
```bash
docker run -d -p 27017:27017 --name mongodb mongo:6.0
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
vim .env
```

配置:
```bash
GITLAB_SERVER_URL=https://gitlab.com
GITLAB_PRIVATE_TOKEN=your-token
LLM_PROVIDER=deepseek
LLM_API_KEY=your-key
LLM_MODEL=deepseek-chat
MONGODB_HOST=localhost
MONGODB_PORT=27017
```

### 5. 初始化数据库

```bash
python manage.py migrate
```

### 6. 启动服务

```bash
# 开发模式
./start.sh

# 或
python manage.py runserver 0.0.0.0:8000
```

### 7. 配置 GitLab Webhook

同方式一步骤 5

---

## 配置项说明

### 获取 GitLab Token

1. 登录 GitLab
2. 点击右上角头像 > **Preferences**
3. 左侧菜单选择 **Access Tokens**
4. 创建 Personal Access Token,权限勾选:
   - ✅ api
   - ✅ read_repository
   - ✅ write_repository
5. 复制生成的 Token

### 获取 LLM API Key

#### DeepSeek (推荐,性价比高)
1. 访问 [DeepSeek 官网](https://platform.deepseek.com/)
2. 注册并登录
3. 创建 API Key
4. 配置: `LLM_PROVIDER=deepseek`

#### OpenAI
1. 访问 [OpenAI Platform](https://platform.openai.com/)
2. 创建 API Key
3. 配置: `LLM_PROVIDER=openai`

#### Ollama (本地部署,免费)
1. 安装 Ollama: `curl https://ollama.ai/install.sh | sh`
2. 拉取模型: `ollama pull llama3.2`
3. 配置:
   ```bash
   LLM_PROVIDER=ollama
   LLM_API_BASE=http://localhost:11434
   LLM_MODEL=llama3.2
   ```

---

## 常见问题

### Q: Docker 启动失败?

```bash
# 查看详细日志
docker-compose logs

# 重新构建
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Q: MongoDB 连接失败?

确保 MongoDB 正在运行:
```bash
# Docker
docker ps | grep mongo

# 本地
sudo systemctl status mongodb
```

### Q: GitLab Webhook 无响应?

1. 检查 Webhook URL 是否正确
2. 检查服务是否运行: `curl http://localhost:8000/health/`
3. 查看 GitLab Webhook 日志
4. 检查防火墙设置

### Q: LLM API 调用失败?

1. 确认 API Key 正确
2. 检查网络连接
3. 查看日志: `docker-compose logs -f django`

---

## 下一步

### 启用钉钉通知 (可选)

```bash
# 编辑 .env
DINGDING_BOT_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGDING_SECRET=your-secret

# 重启服务
docker-compose restart django
```

### 访问管理后台

```bash
# 创建管理员账号
docker-compose exec django python manage.py createsuperuser

# 访问
http://localhost:8000/admin/
```

### 查看数据

```bash
# 进入 Django Shell
docker-compose exec django python manage.py shell

# 查询数据
>>> from apps.webhook.models import WebhookLog, MergeRequestReview
>>> WebhookLog.objects.count()
>>> MergeRequestReview.objects.all()
```

---

## 生产部署建议

### 1. 安全配置

```bash
# .env
DEBUG=False
DJANGO_SECRET_KEY=<生成一个复杂的密钥>
ALLOWED_HOSTS=your-domain.com
```

### 2. 使用 HTTPS

配置 Nginx 反向代理和 SSL 证书

### 3. 数据备份

```bash
# 备份 MongoDB
docker-compose exec mongodb mongodump --out /backup

# 定期备份
0 2 * * * docker-compose exec mongodb mongodump --out /backup/$(date +\%Y\%m\%d)
```

### 4. 监控

- 监控服务运行状态
- 设置日志告警
- 监控 MongoDB 性能

---

## 获取帮助

- 📖 完整文档: [backend/README.md](backend/README.md)
- 🔄 迁移指南: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- 📝 更新日志: [CHANGELOG.md](CHANGELOG.md)
- 🐛 报告问题: [GitHub Issues](https://github.com/mimo-x/Code-Review-GPT-Gitlab/issues)

- 📮 Email: mixuxin@163.com
- 📱 微信: isxuxin

---

## 成功部署的标志

✅ `curl http://localhost:8000/health/` 返回 `{"status": "ok"}`
✅ Docker 容器运行正常: `docker-compose ps`
✅ MongoDB 数据库可访问
✅ GitLab Webhook 配置成功
✅ 创建 MR 后收到代码审查评论

---

🎉 恭喜! 你已经成功部署了 Code Review GPT!

现在创建一个 Merge Request 来测试吧! 🚀
