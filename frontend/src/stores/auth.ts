import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const isAuthenticated = ref(false)
  const username = ref('')

  /**
   * 登录方法 - 调用后端 API 验证
   * 后端会自动设置 HttpOnly Cookie
   * @param user 用户名
   * @param pass 密码
   * @returns 登录是否成功
   */
  const login = async (user: string, pass: string): Promise<boolean> => {
    try {
      const response: any = await api.login({
        username: user,
        password: pass
      })

      if (response.success && response.data) {
        // 后端已经设置了 HttpOnly Cookie，前端不需要手动管理 token
        // 只需要保存用户名到 localStorage 用于显示
        localStorage.setItem('username', response.data.username)
        isAuthenticated.value = true
        username.value = response.data.username
        return true
      }
      return false
    } catch (error) {
      console.error('登录失败:', error)
      return false
    }
  }

  /**
   * 登出方法
   * 后端会自动清除 Cookie
   */
  const logout = async () => {
    try {
      await api.logout()
    } catch (error) {
      console.error('登出失败:', error)
    } finally {
      // 清除本地存储的用户名
      localStorage.removeItem('username')
      isAuthenticated.value = false
      username.value = ''
    }
  }

  /**
   * 检查登录状态
   * 通过调用后端接口验证 Cookie 中的 token 是否有效
   * @returns 是否已登录
   */
  const checkAuth = async (): Promise<boolean> => {
    try {
      const savedUsername = localStorage.getItem('username')
      if (!savedUsername) {
        return false
      }

      // 调用后端接口验证 Cookie 中的 token
      const response: any = await api.checkAuth()

      if (response.success && response.data) {
        isAuthenticated.value = true
        username.value = response.data.username
        // 更新本地存储的用户名
        localStorage.setItem('username', response.data.username)
        return true
      }
      return false
    } catch (error) {
      // Token 无效或已过期
      localStorage.removeItem('username')
      isAuthenticated.value = false
      username.value = ''
      return false
    }
  }

  return {
    isAuthenticated,
    username,
    login,
    logout,
    checkAuth
  }
})
