# Code Review GPT - Django Backend

基于 Django + MongoDB 的 GitLab 代码审查后端服务

## 项目架构

### 技术栈
- **框架**: Django 4.2.9 + Django REST Framework
- **数据库**: MongoDB (��用 djongo ORM)
- **LLM集成**: UnionLLM (支持多种大模型)
- **生产服务器**: Gunicorn + Gevent

### 项目结构
```
backend/
├── core/                   # Django 核心配置
│   ├── settings.py        # 项目设置
│   ├── urls.py            # 路由配置
│   ├── wsgi.py            # WSGI 配置
│   └── exceptions.py      # 异常处理
├── apps/                   # Django 应用
│   ├── webhook/           # Webhook 处理
│   │   ├── models.py      # 数据模型
│   │   ├── views.py       # 视图
│   │   ├── serializers.py # 序列化器
│   │   └── urls.py        # 路由
│   ├── review/            # 代码审查逻辑
│   │   ├── services.py    # 业务服务
│   │   └── views.py       # 视图
│   ├── llm/               # LLM 集成
│   │   └── services.py    # LLM 服务
│   └── response/          # 通知响应
│       └── services.py    # 通知服务
├── utils/                 # 工具函数
│   └── gitlab_parser.py   # GitLab 解析工具
├── manage.py              # Django 管理脚本
├── requirements.txt       # 依赖列表
├── Dockerfile             # Docker 配置
├── docker-compose.yml     # Docker Compose 配置
├── start.sh               # 开发环境启动脚本
└── start_production.sh    # 生产环境启动脚本
```

## 快速开始

### 方式一：Docker Compose (推荐)

1. **克隆仓库**
```bash
git clone git@github.com:mimo-x/Code-Review-GPT-Gitlab.git
cd Code-Review-GPT-Gitlab/backend
```

2. **配置环境变量**
```bash
cp .env.example .env
vim .env  # 编辑配置文件
```

3. **启动服务**
```bash
docker-compose up -d
```

4. **查看日志**
```bash
docker-compose logs -f django
```

服务将在 `http://localhost:8000` 启动

### 方式二：本地开发

1. **安装 MongoDB**

确保本地已安装并运行 MongoDB

2. **创建虚拟环境**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **配置环境变量**
```bash
cp .env.example .env
vim .env  # 编辑配置文件
```

5. **运行迁移**
```bash
python manage.py migrate
```

6. **启动开发服务器**
```bash
./start.sh
# 或
python manage.py runserver 0.0.0.0:8000
```

## 配置说明

### 必需配置

#### GitLab 配置
```bash
GITLAB_SERVER_URL=https://gitlab.com
GITLAB_PRIVATE_TOKEN=your-gitlab-token  # GitLab Personal Access Token
```

#### LLM 配置
```bash
LLM_PROVIDER=deepseek  # 支持: openai, deepseek, azure, ollama 等
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat
```

#### MongoDB 配置
```bash
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_NAME=code_review_gpt
MONGODB_USER=admin
MONGODB_PASSWORD=password
```

### 可选配置

#### 钉钉通知
```bash
DINGDING_BOT_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxx
DINGDING_SECRET=your-secret
```

#### 代码审查设置
```bash
EXCLUDE_FILE_TYPES=.py,.java,.vue,.go  # 需要审查的文件类型
IGNORE_FILE_TYPES=mod.go               # 忽略的文件
CONTEXT_LINES_NUM=5                    # 上下文代码行数
```

## GitLab Webhook 配置

1. 在 GitLab 项目中进入 **Settings** > **Webhooks**

2. 配置 Webhook URL:
```
http://your-domain:8000/api/webhook/gitlab/
```

3. 选择触发���件:
- ✅ Merge request events

4. 点击 **Add webhook**

## API 端点

### Webhook 端点
- `POST /api/webhook/gitlab/` - GitLab Webhook 接收端点

### 健康检查
- `GET /health/` - 服务健康检查

## 数据模型

### WebhookLog
记录所有接收到的 Webhook 事件
```python
- event_type: 事件类型
- project_id: 项目 ID
- merge_request_iid: MR ID
- payload: 原始请求数据
- processed: 是否已处理
```

### MergeRequestReview
存储代码审查结果
```python
- project_id: 项目 ID
- merge_request_iid: MR ID
- review_content: 审查内容
- review_score: 评分 (0-100)
- status: 状态 (pending/processing/completed/failed)
- files_reviewed: 已审查的文件列表
```

## 生产部署

### 使用 Gunicorn

```bash
./start_production.sh
```

或手动启动:
```bash
gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class gevent \
    --timeout 300
```

### 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/backend/staticfiles/;
    }
}
```

## 支持的 LLM 提供商

通过 UnionLLM,支持以下 LLM 提供商:

- OpenAI (GPT-3.5, GPT-4)
- DeepSeek
- Azure OpenAI
- Anthropic Claude
- Google Gemini
- 百度文心一言
- 阿里通义千问
- 智谱 AI
- Ollama (本地部署)
- 更多...

配置示例:

```bash
# DeepSeek
LLM_PROVIDER=deepseek
LLM_API_KEY=your-key
LLM_MODEL=deepseek-chat

# OpenAI
LLM_PROVIDER=openai
LLM_API_KEY=your-key
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4

# Ollama (本地)
LLM_PROVIDER=ollama
LLM_API_BASE=http://localhost:11434
LLM_MODEL=llama3.2
```

## 常见问题

### 1. MongoDB 连接失败

确保 MongoDB 服务正在运行:
```bash
# 检查 MongoDB 状态
systemctl status mongod

# 或使用 Docker
docker ps | grep mongo
```

### 2. Djongo 兼容性问题

如果遇到 djongo 相关错误,确保安装正确版��:
```bash
pip install djongo==1.3.6 pymongo==3.12.3 sqlparse==0.2.4
```

### 3. LLM API 调用失败

- 检查 API Key 是否正确
- 确认网络连接
- 查看日志文件: `logs/django.log`

## 开发调试

### 查看日志
```bash
# 实时查看日志
tail -f logs/django.log

# Docker 环境
docker-compose logs -f django
```

### Django Shell
```bash
python manage.py shell
```

### 创建超级用户
```bash
python manage.py createsuperuser
```

访问管理后台: `http://localhost:8000/admin/`

## 迁移说明

本项目已从 Flask 框架迁移到 Django 框架,主要改进:

1. ✅ 使用 Django ORM + djongo 连接 MongoDB
2. ✅ 更好的项目结构和模块化设计
3. ✅ 完善的数据模型和数据持久化
4. ✅ Django REST Framework 提供标准 API
5. ✅ 更好的日志和错误处理
6. ✅ 生产级部署配置

## 许可证

MIT License

## 联系方式

- Email: mixuxin@163.com
- 微信: isxuxin
