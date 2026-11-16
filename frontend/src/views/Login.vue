<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-apple-blue-50 to-apple-purple-50 px-4">
    <div class="max-w-md w-full">
      <!-- Logo and Title -->
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-apple-gray-900 mb-2">Code Review Admin</h1>
        <p class="text-apple-gray-600">AI代码审查管理系统</p>
      </div>

      <!-- Login Card -->
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <h2 class="text-2xl font-semibold text-apple-gray-900 mb-6">登录</h2>

        <form @submit.prevent="handleLogin">
          <!-- Username Input -->
          <div class="mb-4">
            <label for="username" class="block text-sm font-medium text-apple-gray-700 mb-2">
              用户名
            </label>
            <input
              id="username"
              v-model="formData.username"
              type="text"
              required
              class="w-full px-4 py-3 border border-apple-gray-300 rounded-lg focus:ring-2 focus:ring-apple-blue-500 focus:border-transparent transition-all"
              placeholder="请输入用户名"
              :disabled="loading"
            />
          </div>

          <!-- Password Input -->
          <div class="mb-6">
            <label for="password" class="block text-sm font-medium text-apple-gray-700 mb-2">
              密码
            </label>
            <div class="relative">
              <input
                id="password"
                v-model="formData.password"
                :type="showPassword ? 'text' : 'password'"
                required
                class="w-full px-4 py-3 pr-12 border border-apple-gray-300 rounded-lg focus:ring-2 focus:ring-apple-blue-500 focus:border-transparent transition-all"
                placeholder="请输入密码"
                :disabled="loading"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-apple-gray-500 hover:text-apple-gray-700 rounded-lg hover:bg-apple-gray-100 transition-all"
                :disabled="loading"
                tabindex="-1"
              >
                <EyeOff v-if="!showPassword" class="w-5 h-5" />
                <Eye v-else class="w-5 h-5" />
              </button>
            </div>
          </div>

          <!-- Error Message -->
          <div v-if="errorMessage" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p class="text-sm text-red-600">{{ errorMessage }}</p>
          </div>

          <!-- Login Button -->
          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-apple-blue-600 hover:bg-apple-blue-700 text-white font-medium py-3 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="!loading">登录</span>
            <span v-else>登录中...</span>
          </button>
        </form>

        <!-- Default Account Hint -->
        <div class="mt-6 p-4 bg-apple-gray-50 rounded-lg">
          <p class="text-xs text-apple-gray-600 text-center">
            <!-- 默认账号密码在 .env 文件中配置 -->
          </p>
        </div>
      </div>

      <!-- Footer -->
      <div class="text-center mt-6">
        <p class="text-sm text-apple-gray-500">
          © 2026 Code Review GPT GitLab
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Eye, EyeOff } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const formData = reactive({
  username: '',
  password: ''
})

const loading = ref(false)
const errorMessage = ref('')
const showPassword = ref(false)

const handleLogin = async () => {
  errorMessage.value = ''
  loading.value = true

  try {
    const success = await authStore.login(formData.username, formData.password)

    if (success) {
      // 登录成功，跳转到项目列表页
      router.push('/projects')
    } else {
      errorMessage.value = '用户名或密码错误'
    }
  } catch (error) {
    errorMessage.value = '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* Apple 风格的输入框聚焦效果 */
input:focus {
  outline: none;
}
</style>
