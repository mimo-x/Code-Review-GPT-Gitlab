/**
 * API配置文件
 * 统一管理所有接口地址
 */

// API基础配置
export const API_CONFIG = {
  // 从环境变量获取基础URL
  BASE_URL: import.meta.env.VITE_API_BASE_URL || '/api',

  // 超时时间
  TIMEOUT: 30000,

  // 请求头
  HEADERS: {
    'Content-Type': 'application/json'
  }
}

// 具体接口地址
export const API_ENDPOINTS = {
  // 统计数据
  STATISTICS: '/statistics',

  // 审查记录
  REVIEWS: '/webhook/reviews/',
  REVIEW_DETAIL: (id: string) => `/webhook/reviews/${id}/`,

  // 配置管理
  CONFIG: '/config/',
  CONFIG_SUMMARY: '/configs/summary/',
  CONFIG_BATCH_UPDATE: '/configs/batch_update/',

  // 日志管理
  LOGS: '/webhook/logs/',

  // 系统信息
  SYSTEM_INFO: '/system/info',

  // Webhook测试
  WEBHOOK_TEST: '/test/webhook',

  // 项目管理
  PROJECTS: '/webhook/projects/',
  PROJECT_DETAIL: (id: string | number) => `/webhook/projects/${id}`,
  PROJECT_ENABLE: (id: string | number) => `/webhook/projects/${id}/enable`,
  PROJECT_DISABLE: (id: string | number) => `/webhook/projects/${id}/disable`,
  PROJECT_UPDATE: (id: string | number) => `/webhook/projects/${id}/update`,
  PROJECT_STATS: '/webhook/projects/stats/',
  PROJECT_WEBHOOK_LOGS: (id: string | number) => `/webhook/projects/${id}/webhook-logs`,
  PROJECT_REVIEW_HISTORY: (id: string | number) => `/webhook/projects/${id}/review-history`,

  // GitLab Webhook
  GITLAB_WEBHOOK: '/webhook/gitlab'
}

// 完整URL生成函数
export const getApiUrl = (endpoint: string): string => {
  return `${API_CONFIG.BASE_URL}${endpoint}`
}

// 通用API URL集合（包含完整路径）
export const API_URLS = {
  STATISTICS: getApiUrl(API_ENDPOINTS.STATISTICS),
  REVIEWS: getApiUrl(API_ENDPOINTS.REVIEWS),
  CONFIG: getApiUrl(API_ENDPOINTS.CONFIG),
  LOGS: getApiUrl(API_ENDPOINTS.LOGS),
  SYSTEM_INFO: getApiUrl(API_ENDPOINTS.SYSTEM_INFO),
  WEBHOOK_TEST: getApiUrl(API_ENDPOINTS.WEBHOOK_TEST),
  PROJECTS: getApiUrl(API_ENDPOINTS.PROJECTS),
  PROJECT_STATS: getApiUrl(API_ENDPOINTS.PROJECT_STATS),
  GITLAB_WEBHOOK: getApiUrl(API_ENDPOINTS.GITLAB_WEBHOOK)
}