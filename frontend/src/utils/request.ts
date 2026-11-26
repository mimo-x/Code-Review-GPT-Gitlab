import axios from 'axios'
import type { AxiosInstance, AxiosResponse } from 'axios'
import { API_CONFIG } from '@/config/api'
import router from '@/router'

declare module 'axios' {
  interface AxiosRequestConfig {
    inlineError?: boolean
  }
}

let redirectingToLogin = false

const service: AxiosInstance = axios.create({
  timeout: API_CONFIG.TIMEOUT,
  headers: API_CONFIG.HEADERS,
  withCredentials: true  // 允许携带 Cookie
})

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    // Cookie 会自动携带，不需要手动添加 Authorization header
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
    if (error.config?.inlineError && error.response?.status !== 401) {
      return Promise.reject(error)
    }
    console.error('Response error:', error)

    if (error.response) {
      const { status, config } = error.response

      // 判断是否是登录接口
      const isLoginRequest = config.url?.includes('/auth/login')

      switch (status) {
        case 401:
          // 如果是登录接口返回 401，不做任何处理，让登录页面自己处理错误提示
          if (isLoginRequest) {
            break
          }
          // 其他接口返回 401，说明 token 过期，清除用户名并跳转到登录页
          localStorage.removeItem('username')
          // 一个页面可能同时发出多个请求，只跳转和提示一次
          if (!redirectingToLogin && router.currentRoute.value.path !== '/login') {
            redirectingToLogin = true
            router.push('/login').finally(() => {
              redirectingToLogin = false
            })
            alert('登录已过期，请重新登录')
          }
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
