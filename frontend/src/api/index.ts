import request from '@/utils/request'
import { API_ENDPOINTS, getApiUrl } from '@/config/api'

// 统计数据
export const getStatistics = () => {
  return request({
    url: getApiUrl(API_ENDPOINTS.STATISTICS),
    method: 'get'
  })
}

// 审查记录列表
export const getReviews = (params?: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.REVIEWS),
    method: 'get',
    params
  })
}

// 审查详情
export const getReviewDetail = (id: string) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.REVIEW_DETAIL(id)),
    method: 'get'
  })
}

// 配置信息
export const getConfig = () => {
  return request({
    url: getApiUrl(API_ENDPOINTS.CONFIG),
    method: 'get'
  })
}

// 更新配置
export const updateConfig = (data: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.CONFIG),
    method: 'post',
    data
  })
}

// 获取配置摘要
export const getConfigSummary = () => {
  return request({
    url: getApiUrl(API_ENDPOINTS.CONFIG_SUMMARY),
    method: 'get'
  })
}

// 批量更新配置
export const batchUpdateConfig = (data: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.CONFIG_BATCH_UPDATE),
    method: 'post',
    data
  })
}

// 日志列表
export const getLogs = (params?: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.LOGS),
    method: 'get',
    params
  })
}

// 系统信息
export const getSystemInfo = () => {
  return request({
    url: getApiUrl(API_ENDPOINTS.SYSTEM_INFO),
    method: 'get'
  })
}

// Webhook 测试
export const testWebhook = (data: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.WEBHOOK_TEST),
    method: 'post',
    data
  })
}

// 项目管理 - 获取项目列表
export const getProjects = (params?: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECTS),
    method: 'get',
    params
  })
}

// 项目管理 - 获取项目详情
export const getProjectDetail = (id: string) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_DETAIL(id)),
    method: 'get'
  })
}

// 项目管理 - 启用项目审查
export const enableProjectReview = (id: string) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_ENABLE(id)),
    method: 'post'
  })
}

// 项目管理 - 禁用项目审查
export const disableProjectReview = (id: string) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_DISABLE(id)),
    method: 'post'
  })
}

// 项目管理 - 更新项目设置
export const updateProject = (id: string, data: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_UPDATE(id)),
    method: 'patch',
    data
  })
}

// 项目管理 - 获取项目webhook日志
export const getProjectWebhookLogs = (id: string, params?: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_WEBHOOK_LOGS(id)),
    method: 'get',
    params
  })
}

// 项目管理 - 获取项目审查历史
export const getProjectReviewHistory = (id: string, params?: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_REVIEW_HISTORY(id)),
    method: 'get',
    params
  })
}

// 项目管理 - 获取所有项目的统计数据
export const getAllProjectStats = () => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_STATS),
    method: 'get'
  })
}

// Mock API - 获取审查记录
export const getMockReviews = () => {
  return request({
    url: getApiUrl('/webhook/projects/mock/reviews/'),
    method: 'get'
  })
}

// Mock API - 获取日志记录
export const getMockLogs = () => {
  return request({
    url: getApiUrl('/webhook/projects/mock/logs/'),
    method: 'get'
  })
}
