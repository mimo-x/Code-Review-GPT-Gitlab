FROM node:18-alpine

# 设置工作目录
WORKDIR /app

# 复制package文件
COPY frontend/package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码
COPY frontend/ .

# 暴露端口
EXPOSE 3000

# 开发模式启动命令
CMD ["npm", "run", "dev"]