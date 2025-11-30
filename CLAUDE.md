# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 当我没有在书面上请求你生成任何说明文档的时候，禁止你生成任何说明文档

## Project Overview

Code Review GPT GitLab is a Django + Vue.js full-stack application that automates code review using Large Language Models (LLMs). It integrates with GitLab via webhooks and supports 40+ LLM providers through UnionLLM.

## Development Commands

### Backend (Django)
```bash
# Development server
python manage.py runserver 0.0.0.0:8000
./start.sh                   # Automated development startup

# Database
python manage.py migrate    # Run migrations
python manage.py createsuperuser  # Admin user

# Production
./start_production.sh       # Production deployment with gunicorn
gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 4 --worker-class gevent

# Docker
docker compose up -d        # Build backend image + start stack
```

### Frontend (Vue.js)
```bash
npm install                 # Install dependencies
npm run dev                 # Development server (localhost:3000)
npm run build              # Production build
npm run preview            # Preview production build
```

## Architecture

### Backend Structure
- **Django Apps**: `webhook` (GitLab integration), `review` (code review logic), `llm` (LLM integration), `response` (notifications)
- **Entry Point**: `backend/core/wsgi.py` for production, `manage.py` for development
- **Main Settings**: `backend/core/settings.py` - contains all Django, LLM, and notification configurations
- **Database**: SQLite by default with Redis caching

### Frontend Structure
- **Framework**: Vue 3 + TypeScript + Vite
- **UI**: Tailwind CSS + Preline components
- **State**: Pinia for state management
- **API**: Axios for backend communication

### Key Application Flow
1. GitLab webhook → `/api/webhook/gitlab/` (apps/webhook/views.py)
2. Code analysis → GitLab API service
3. LLM processing → UnionLLM integration (apps/llm/)
4. Response generation → Multi-channel notifications (apps/response/)
5. Frontend dashboard → Management interface

## Configuration

### Environment Variables (.env)
- **GitLab**: 通过后台的 GitLab 配置页面维护，不再依赖 `.env`
- **Database**: SQLite with Redis for caching and session storage
- **Claude CLI**: `CLAUDE_CLI_PATH`, `CLAUDE_CLI_TIMEOUT` for Claude integration
> LLM 及通知渠道改为通过数据库管理（`LLMConfig` / `NotificationChannel`）。

### Important Files
- `backend/core/settings.py` - Main Django configuration
- `backend/requirements.txt` - Python dependencies
- `frontend/package.json` - Node.js dependencies and scripts
- `docker-compose.yml` - 统一的后端/前端/Redis 编排

## LLM Integration

The project uses **UnionLLM** as the primary LLM abstraction layer, supporting:
- OpenAI (GPT-3.5, GPT-4)
- DeepSeek (primary focus)
- Anthropic Claude
- Google Gemini
- Azure OpenAI
- Ollama (local)
- 40+ other providers

The review prompt template is defined in `settings.py` and can be customized per project.

## Database Models

### Key Models (apps/webhook/models.py)
- `Project` - GitLab project configuration
- `WebhookLog` - Webhook event logging
- `MergeRequestReview` - Review results storage
- `ProjectNotificationSetting` - Notification configuration

### LLM Models (apps/llm/models.py)
- `LLMConfig` - LLM provider settings
- `GitLabConfig` - GitLab API configuration
- `NotificationChannel` - Multi-channel notification setup
- `WebhookEventRule` - Event processing rules

## Key Features

- **Automated Code Review**: GitLab MR triggers LLM analysis
- **Multi-LLM Support**: 40+ providers via UnionLLM
- **Multi-Channel Notifications**: DingTalk, Slack, Feishu, WeChat Work, Email
- **Custom Review Logic**: Project-specific prompts and rules
- **Management Dashboard**: Vue.js admin interface
- **Claude CLI Integration**: Optional Claude Code integration for advanced analysis

## Development Notes

- **Timezone**: Configured for Asia/Shanghai, not UTC
- **Language**: Chinese language code (`zh-hans`)
- **Mock Mode**: 将 `LLMConfig.provider` 设置为 `mock` 以启用本地模拟
- **File Filtering**: Configure file types to include/exclude via `EXCLUDE_FILE_TYPES` and `IGNORE_FILE_TYPES`
- **CORS**: Pre-configured for frontend development servers

## Testing

Currently no test framework is configured. This is a known gap that should be addressed with pytest or Django's test framework.

## Deployment

- **Production Server**: Gunicorn with gevent workers
- **Database**: SQLite (default) with Redis caching
- **Docker**: Compose builds backend via `docker/backend/Dockerfile`
- **Static Files**: Collected to `staticfiles/` directory
