# Code Review GPT - Django Backend

基于 Django + SQLite 的 GitLab 代码审查后端服务

## 项目架构

### 技术栈
- **框架**: Django 4.2.9 + Django REST Framework
- **数据库**: SQLite (Django 默认 ORM) + Redis 缓存
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

