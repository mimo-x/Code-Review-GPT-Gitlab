import request from '@/utils/request'

// 统计数据
export const getStatistics = () => {
  return request({
    url: '/statistics',
    method: 'get'
  })
}

// 审查记录列表
export const getReviews = (params?: any) => {
  return request({
    url: '/reviews',
    method: 'get',
    params
  })
}

// 审查详情
export const getReviewDetail = (id: string) => {
  return request({
    url: `/reviews/${id}`,
    method: 'get'
  })
}

// 配置信息
export const getConfig = () => {
  return request({
    url: '/config',
    method: 'get'
  })
}

// 更新配置
export const updateConfig = (data: any) => {
  return request({
    url: '/config',
    method: 'post',
    data
  })
}

// 日志列表
export const getLogs = (params?: any) => {
  return request({
    url: '/logs',
    method: 'get',
    params
  })
}

// 系统信息
export const getSystemInfo = () => {
  return request({
    url: '/system/info',
    method: 'get'
  })
}

// Webhook 测试
export const testWebhook = (data: any) => {
  return request({
    url: '/test/webhook',
    method: 'post',
    data
  })
}

// 项目管理 - 获取项目列表
export const getProjects = (params?: any) => {
  return request({
    url: '/projects',
    method: 'get',
    params
  })
}

// 项目管理 - 获取项目详情
export const getProjectDetail = (id: string) => {
  return request({
    url: `/projects/${id}`,
    method: 'get'
  })
}

// 项目管理 - 切换项目审查状态
export const toggleProjectReview = (id: string, enabled: boolean) => {
  return request({
    url: `/projects/${id}/review`,
    method: 'post',
    data: { enabled }
  })
}

// 项目管理 - 获取项目事件列表
export const getProjectEvents = (id: string, params?: any) => {
  return request({
    url: `/projects/${id}/events`,
    method: 'get',
    params
  })
}

// 项目管理 - 获取项目统计数据
export const getProjectStats = (id: string) => {
  return request({
    url: `/projects/${id}/stats`,
    method: 'get'
  })
}
