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

// 通知通道列表
export const getNotificationChannels = (params?: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.NOTIFICATION_CHANNELS),
    method: 'get',
    params
  })
}

// 创建通知通道
export const createNotificationChannel = (data: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.NOTIFICATION_CHANNELS),
    method: 'post',
    data
  })
}

// 更新通知通道
export const updateNotificationChannel = (id: string | number, data: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.NOTIFICATION_CHANNEL_DETAIL(id)),
    method: 'patch',
    data
  })
}

// 删除通知通道
export const deleteNotificationChannel = (id: string | number) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.NOTIFICATION_CHANNEL_DETAIL(id)),
    method: 'delete'
  })
}

// 测试通知渠道
export const testNotificationChannel = (id: string | number) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.NOTIFICATION_CHANNEL_DETAIL(id) + 'test/'),
    method: 'post'
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

// 项目通知 - 获取
export const getProjectNotifications = (id: string | number) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_NOTIFICATIONS(id)),
    method: 'get'
  })
}

// 项目通知 - 更新
export const updateProjectNotifications = (id: string | number, data: any) => {
  return request({
    url: getApiUrl(API_ENDPOINTS.PROJECT_NOTIFICATIONS_UPDATE(id)),
    method: 'post',
    data
  })
}

// 项目 Webhook 事件 - 获取
export const getProjectWebhookEvents = (id: string | number) => {
  return request({
    url: getApiUrl(`/webhook/projects/${id}/webhook-events/`),
    method: 'get'
  })
}

// 项目 Webhook 事件 - 更新
export const updateProjectWebhookEvents = (id: string | number, data: any) => {
  return request({
    url: getApiUrl(`/webhook/projects/${id}/webhook-events/update/`),
    method: 'post',
    data
  })
}

// 项目 Webhook 事件 Prompt - 获取
export const getProjectWebhookEventPrompts = (id: string | number) => {
  return request({
    url: getApiUrl(`/webhook/projects/${id}/webhook-event-prompts/`),
    method: 'get'
  })
}

// 项目 Webhook 事件 Prompt - 更新
export const updateProjectWebhookEventPrompt = (id: string | number, data: any) => {
  return request({
    url: getApiUrl(`/webhook/projects/${id}/webhook-event-prompts/update/`),
    method: 'post',
    data
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

// Webhook事件规则 - 获取列表
export const getWebhookEventRules = (params?: any) => {
  return request({
    url: getApiUrl('/webhook-event-rules/'),
    method: 'get',
    params
  })
}

// Webhook事件规则 - 获取详情
export const getWebhookEventRule = (id: string | number) => {
  return request({
    url: getApiUrl(`/webhook-event-rules/${id}/`),
    method: 'get'
  })
}

// Webhook事件规则 - 创建
export const createWebhookEventRule = (data: any) => {
  return request({
    url: getApiUrl('/webhook-event-rules/'),
    method: 'post',
    data
  })
}

// Webhook事件规则 - 更新
export const updateWebhookEventRule = (id: string | number, data: any) => {
  return request({
    url: getApiUrl(`/webhook-event-rules/${id}/`),
    method: 'patch',
    data
  })
}

// Webhook事件规则 - 删除
export const deleteWebhookEventRule = (id: string | number) => {
  return request({
    url: getApiUrl(`/webhook-event-rules/${id}/`),
    method: 'delete'
  })
}

// Webhook事件规则 - 测试规则
export const testWebhookEventRule = (id: string | number, payload: any) => {
  return request({
    url: getApiUrl(`/webhook-event-rules/${id}/test_rule/`),
    method: 'post',
    data: { payload }
  })
}

// Webhook事件规则 - 验证payload
export const validateWebhookPayload = (payload: any) => {
  return request({
    url: getApiUrl('/webhook-event-rules/validate_payload/'),
    method: 'post',
    data: { payload }
  })
}

// Webhook事件规则 - 初始化默认规则
export const initializeDefaultWebhookEventRules = () => {
  return request({
    url: getApiUrl('/webhook-event-rules/initialize_defaults/'),
    method: 'post'
  })
}

// 获取 Webhook URL
export const getWebhookUrl = () => {
  return request({
    url: getApiUrl('/webhook/webhook-url/'),
    method: 'get'
  })
}

// 测试 OpenCode CLI 配置
export const testOpencodeCliConfigApi = (data: any) => {
  return request({
    url: getApiUrl('/configs/test-opencode-cli/'),
    method: 'post',
    data,
    timeout: 90000  // 90 秒超时（后端测试最多 45 秒 + 额外处理时间）
  })
}
