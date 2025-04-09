# syntax=docker/dockerfile:1
FROM python:3.9-slim

WORKDIR /workspace

# 使用缓存安装系统依赖
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    python3-dev

COPY requirements.txt .

# 使用缓存安装 Python 依赖
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/workspace

CMD ["python", "app.py"]
