# Code Review GPT - 前端管理系统

基于 **Vue 3 + Vite + TypeScript + Tailwind CSS + Preline** 构建的现代化代码审查管理后台。

## ✨ 功能特性

- 📊 **仪表盘** - 审查统计数据可视化展示，实时监控审查趋势
- 📝 **审查记录** - MR审查历史查询、详情查看与问题追踪
- ⚙️ **配置管理** - LLM、GitLab、通知等全面配置管理
- 📋 **日志监控** - 实时日志查看与多级别过滤
- ℹ️ **项目信息** - 系统状态、资源使用、技术栈展示

## 🛠️ 技术栈

### 核心框架
- **Vue 3.4** - 渐进式JavaScript框架
- **Vite 5.0** - 新一代前端构建工具
- **TypeScript 5.3** - JavaScript的超集，提供类型安全

### UI 与样式
- **Tailwind CSS 3.4** - 实用优先的CSS框架
- **Preline 2.0** - 基于Tailwind的开源UI组件库
- **Lucide Icons** - 精美的图标库

### 其他工具
- **Vue Router 4.2** - 官方路由管理器
- **Pinia 2.1** - 轻量级状态管理
- **Axios 1.6** - HTTP客户端
- **ECharts 5.4** - 强大的数据可视化库

## 🚀 快速开始

### 前置要求

- Node.js >= 18.0
- pnpm/npm/yarn

### 安装依赖

```bash
npm install
# 或
pnpm install
# 或
yarn install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 生产构建

```bash
npm run build
```

构建产物输出到 `dist/` 目录。

### 预览生产构建

```bash
npm run preview
```

## 📁 项目结构

```
frontend/
├── public/                 # 静态资源
├── src/
│   ├── api/               # API接口定义
│   ├── assets/            # 资源文件(图片、字体等)
│   ├── layouts/           # 布局组件
│   │   └── MainLayout.vue # 主布局(侧边栏+头部)
│   ├── router/            # 路由配置
│   │   └── index.ts       # 路由定义
│   ├── styles/            # 全局样式
│   │   └── main.css       # Tailwind基础样式
│   ├── utils/             # 工具函数
│   │   └── request.ts     # Axios请求封装
│   ├── views/             # 页面组件
│   │   ├── Dashboard.vue      # 仪表盘
│   │   ├── Reviews.vue        # 审查记录列表
│   │   ├── ReviewDetail.vue   # 审查详情
│   │   ├── Config.vue         # 配置管理
│   │   ├── Logs.vue           # 日志监控
│   │   └── About.vue          # 项目信息
│   ├── App.vue            # 根组件
│   └── main.ts            # 应用入口
├── index.html
├── package.json
├── tailwind.config.js     # Tailwind配置
├── postcss.config.js      # PostCSS配置
├── tsconfig.json          # TypeScript配置
├── vite.config.ts         # Vite配置
└── README.md
```

## ⚙️ 配置说明

### 后端API代理

开发环境下，前端会自动代理API请求到后端服务。在 `vite.config.ts` 中配置:

```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:80',  // 后端Flask服务地址
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, '')
    }
  }
}
```

### 环境变量

创建 `.env.local` 文件进行本地配置:

```bash
# 后端API地址
VITE_API_BASE_URL=http://localhost:80
```

## 📱 主要页面

### 1. 仪表盘 (Dashboard)
- 4个核心指标卡片(今日/本周审查、LLM调用、成功率)
- 审查趋势折线图(支持近7天/30天切换)
- 最近活动时间线
- LLM模型分布饼图
- 问题分类柱状图

### 2. 审查记录 (Reviews)
- 审查记录表格展示
- 实时搜索(MR ID、项目名)
- 状态筛选(已完成、进行中、失败)
- 问题数量统计
- 快速跳转GitLab MR

### 3. 审查详情 (ReviewDetail)
- MR基本信息展示
- 审查摘要与评分
- 问题列表(按严重程度分类)
- 可折叠的问题详情与建议

### 4. 配置管理 (Config)
- **LLM配置**: 提供商、模型、API Key、Base URL
- **GitLab配置**: 服务器地址、Token、文件过滤规则
- **通知配置**: 钉钉Webhook、GitLab评论开关

### 5. 日志监控 (Logs)
- 实时日志流展示
- 级别过滤(DEBUG/INFO/WARNING/ERROR)
- 日志详情展开查看
- 清空与刷新功能

### 6. 项目信息 (About)
- 系统运行状态
- CPU/内存资源使用情况
- 功能特性介绍
- 技术栈展示

## 🎨 使用 Preline UI

Preline 是基于 Tailwind CSS 的开源UI组件库,本项目已集成。

### 常用组件示例

**侧边栏 Overlay (移动端菜单)**
```html
<aside
  id="hs-application-sidebar"
  class="hs-overlay hs-overlay-open:translate-x-0 -translate-x-full..."
>
  <!-- 侧边栏内容 -->
</aside>

<!-- 触发按钮 -->
<button data-hs-overlay="#hs-application-sidebar">
  打开菜单
</button>
```

**下拉菜单**
```html
<div class="hs-dropdown">
  <button class="hs-dropdown-toggle">
    下拉菜单
  </button>
  <div class="hs-dropdown-menu">
    <!-- 菜单项 -->
  </div>
</div>
```

**模态框**
```html
<button data-hs-overlay="#modal">打开模态框</button>

<div id="modal" class="hs-overlay hidden">
  <div class="hs-overlay-open:opacity-100">
    <!-- 模态框内容 -->
  </div>
</div>
```

更多组件请参考: https://preline.co/docs/

## 🎯 自定义样式

项目使用 Tailwind CSS 的自定义类定义了常用样式:

```css
/* src/styles/main.css */

.card {
  @apply bg-white rounded-lg shadow-sm border border-gray-200;
}

.btn-primary {
  @apply py-2 px-4 inline-flex items-center gap-x-2 text-sm font-semibold
         rounded-lg border border-transparent bg-blue-600 text-white
         hover:bg-blue-700;
}

.badge-success {
  @apply inline-flex items-center gap-x-1.5 py-1.5 px-3 rounded-full
         text-xs font-medium bg-teal-100 text-teal-800;
}
```

## 🔌 API 接口对接

所有API接口定义在 `src/api/index.ts`:

```typescript
import request from '@/utils/request'

// 获取审查列表
export const getReviews = (params?: any) => {
  return request({
    url: '/reviews',
    method: 'get',
    params
  })
}

// 获取配置
export const getConfig = () => {
  return request({
    url: '/config',
    method: 'get'
  })
}
```

## 📦 打包部署

### 构建生产版本

```bash
npm run build
```

### 部署到 Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /path/to/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API代理到后端
    location /api {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker 部署

```dockerfile
FROM node:18-alpine as builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## 🌐 浏览器支持

- Chrome >= 90
- Firefox >= 88
- Safari >= 14
- Edge >= 90

## 📄 License

MIT

---

**开发团队**: Code Review GPT Contributors
**技术支持**: https://github.com/your-org/code-review-gpt-gitlab
