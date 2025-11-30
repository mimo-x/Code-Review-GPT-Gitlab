import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { API_CONFIG } from '@/config/api'

const service: AxiosInstance = axios.create({
  timeout: API_CONFIG.TIMEOUT,
  headers: API_CONFIG.HEADERS
})

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    // 可以在这里添加token等
    return config
  },
  (error) => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const { data, status } = response

    // 2xx 状态码都认为是成功
    if (status >= 200 && status < 300) {
      return data
    }

    alert(data.message || '请求失败')
    return Promise.reject(new Error(data.message || 'Error'))
  },
  (error) => {
    console.error('Response error:', error)

    if (error.response) {
      const { status } = error.response
      switch (status) {
        case 401:
          alert('未授权，请重新登录')
          break
        case 403:
          alert('拒绝访问')
          break
        case 404:
          alert('请求地址不存在')
          break
        case 500:
          alert('服务器内部错误')
          break
        default:
          alert(error.response.data?.message || '请求失败')
      }
    } else {
      alert('网络连接失败')
    }

    return Promise.reject(error)
  }
)

export default service
