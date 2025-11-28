FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=core.settings

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY backend/ .

# 创建必要的目录
RUN mkdir -p logs staticfiles media

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]