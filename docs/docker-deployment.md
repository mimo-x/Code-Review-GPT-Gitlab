# Quick Start

This guide explains how to bring up a Code Review GPT GitLab demo stack with a single `docker-compose.yml`. The backend image is built from `docker/backend/Dockerfile`, so system dependencies are preinstalled.

## Prerequisites

- Docker 20.10+
- Docker Compose v2 (bundled with Docker Desktop)
- At least 2 GB of free memory and 3 GB of disk space

## Quick Start

### 1. Clone the repository and configure environment variables

```bash
git clone https://github.com/your-username/Code-Review-GPT-Gitlab.git
cd Code-Review-GPT-Gitlab
cp .env.example .env
# Edit .env and add the required GitLab credentials (LLM/notification channels are configured inside the app)
```

### 2. Start the services

```bash
# The first start installs Python/Node dependencies and may take a few minutes
docker compose up -d

# Check status
docker compose ps

# Tail logs
docker compose logs -f backend
```

After the services are up:
- Frontend: http://localhost:3000 (Vite dev server)
- Backend: http://localhost:8000 (Gunicorn)
- Admin console: http://localhost:8000/admin/

Shut everything down with `docker compose down`.

## Service Overview

| Service  | Image                             | Description |
|----------|-----------------------------------|-------------|
| backend  | Custom image (based on python:3.11-slim) | Built via `docker/backend/Dockerfile`; installs system deps and Python packages, mounts `backend/`, runs migrations, then starts Gunicorn |
| frontend | node:18-alpine                     | Mounts `frontend/`; runs `npm install` and `npm run dev` on startup |
| redis    | redis:7.2-alpine                   | Runs in-memory without persistence |

The named volume `frontend-node-modules` caches front-end dependencies to avoid reinstalling them on every boot.

> LLM credentials and notification channels are managed within the running system via `LLMConfig` / `NotificationChannel`, so no environment variables are required for them.

## Common Operations

```bash
# View logs
docker compose logs -f frontend

# Enter containers
docker compose exec backend bash
docker compose exec frontend sh

# Run Django management commands
docker compose exec backend python manage.py createsuperuser

# Install new front-end dependencies
docker compose exec frontend npm install <pkg>
```

## Troubleshooting

1. **Container fails to start**
   ```bash
   docker compose logs backend
   docker compose restart backend
   ```

2. **Port conflicts**
   ```bash
   lsof -i :3000
   lsof -i :8000
   lsof -i :6379
   ```

3. **Slow or failed dependency installation**
   - Switch to a local npm/pip mirror.
   - Re-run `docker compose up --force-recreate`.

4. **Environment variables not applied**
   ```bash
   docker compose up -d --force-recreate
   ```

## Production Recommendations

The provided Compose setup is designed for local evaluation:
- If you plan to keep Docker in production, extend `docker/backend/Dockerfile` with any extra dependencies, or craft a dedicated Dockerfile/Compose setup with persistence and HTTPS.
- If you prefer to run without Docker, follow the source-based workflow (pip + npm) directly.

After you finish testing, run `docker compose down` to free resources.
