# 项目文档目录

欢迎来到Code Review GPT Gitlab项目的文档中心！

## 📚 文档目录

### 配置指南
- **[配置指南](./config.md)** - 详细的项目配置说明，包括LLM、GitLab和消息通知配置

### 功能说明
- **[代码审查功能](./review.md)** - 代码审查功能的详细说明和使用方法
- **[消息通知功能](./response.md)** - 多渠道消息通知功能说明

### 部署文档
- **[Docker部署指南](./docker-deployment.md)** - 使用Docker快速部署完整指南

### 图片资源
- **[图片资源](./img/)** - 项目相关的截图和架构图

## 🚀 快速开始

1. **环境配置**
   ```bash
   cp .env.example .env
   # 编辑.env文件配置必要信息（LLM/通知请在系统内配置）
   ```

2. **Docker部署**
   ```bash
   docker compose up -d
   ```

3. **源码部署**
   ```bash
   # 后端
   cd backend && python manage.py runserver

   # 前端
   cd frontend && npm run dev
   ```

## 📖 详细信息

如需了解更多信息，请参考：
- 项目主README：[../README.md](../README.md)
- 英文文档：[../README_EN.md](../README_EN.md)

## 🔗 相关链接

- [GitLab配置](./config.md#gitlab配置)
- [LLM配置](./config.md#大模型配置)
- [Docker部署](./docker-deployment.md)
- [功能预览](./img/)
