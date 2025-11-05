<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-gray-900">配置管理</h2>
      <div class="flex gap-3">
        <button @click="handleSave" class="btn-primary">
          <Save class="w-4 h-4" />
          保存配置
        </button>
        <button @click="handleReset" class="btn-secondary">
          <RotateCcw class="w-4 h-4" />
          重置
        </button>
      </div>
    </div>

    <!-- Tabs -->
    <div class="border-b border-gray-200">
      <nav class="-mb-px flex space-x-8">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="activeTab = tab.key"
          :class="[
            'py-4 px-1 border-b-2 font-medium text-sm transition-colors',
            activeTab === tab.key
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          ]"
        >
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- LLM Config -->
    <div v-show="activeTab === 'llm'" class="card">
      <div class="p-6 space-y-6">
        <h3 class="text-lg font-semibold text-gray-900">LLM 配置</h3>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">LLM 提供商</label>
            <select v-model="config.llm.provider" class="input-field">
              <option value="openai">OpenAI GPT-4</option>
              <option value="deepseek">DeepSeek</option>
              <option value="claude">Anthropic Claude</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">模型名称</label>
            <input v-model="config.llm.model" type="text" class="input-field" placeholder="例如: gpt-4" />
          </div>

          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-700 mb-2">API Key</label>
            <input v-model="config.llm.apiKey" type="password" class="input-field" placeholder="请输入 API Key" />
          </div>

          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-700 mb-2">API Base URL (可选)</label>
            <input v-model="config.llm.apiBase" type="text" class="input-field" placeholder="自定义API端点" />
          </div>
        </div>
      </div>
    </div>

    <!-- GitLab Config -->
    <div v-show="activeTab === 'gitlab'" class="card">
      <div class="p-6 space-y-6">
        <h3 class="text-lg font-semibold text-gray-900">GitLab 配置</h3>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-700 mb-2">GitLab URL</label>
            <input v-model="config.gitlab.serverUrl" type="text" class="input-field" placeholder="https://gitlab.com" />
          </div>

          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-700 mb-2">Access Token</label>
            <input v-model="config.gitlab.privateToken" type="password" class="input-field" placeholder="GitLab Access Token" />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">最大审查文件数</label>
            <input v-model.number="config.gitlab.maxFiles" type="number" class="input-field" min="1" max="200" />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">上下文行数</label>
            <input v-model.number="config.gitlab.contextLines" type="number" class="input-field" min="0" max="20" />
          </div>
        </div>
      </div>
    </div>

    <!-- Notification Config -->
    <div v-show="activeTab === 'notification'" class="card">
      <div class="p-6 space-y-6">
        <h3 class="text-lg font-semibold text-gray-900">通知配置</h3>

        <div class="space-y-6">
          <div>
            <div class="flex items-center justify-between mb-4">
              <h4 class="font-medium text-gray-900">钉钉通知</h4>
              <label class="relative inline-flex items-center cursor-pointer">
                <input v-model="config.notification.dingtalk.enabled" type="checkbox" class="sr-only peer" />
                <div class="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>

            <div v-if="config.notification.dingtalk.enabled" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Webhook URL</label>
                <input v-model="config.notification.dingtalk.webhook" type="text" class="input-field" placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Secret</label>
                <input v-model="config.notification.dingtalk.secret" type="password" class="input-field" placeholder="钉钉机器人密钥" />
              </div>
            </div>
          </div>

          <hr />

          <div>
            <div class="flex items-center justify-between mb-4">
              <h4 class="font-medium text-gray-900">GitLab 评论</h4>
              <label class="relative inline-flex items-center cursor-pointer">
                <input v-model="config.notification.gitlab.enabled" type="checkbox" class="sr-only peer" checked />
                <div class="w-11 h-6 bg-gray-200 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Save, RotateCcw } from 'lucide-vue-next'

const activeTab = ref('llm')

const tabs = [
  { key: 'llm', label: 'LLM 配置' },
  { key: 'gitlab', label: 'GitLab 配置' },
  { key: 'notification', label: '通知配置' }
]

const config = ref({
  llm: {
    provider: 'openai',
    model: 'gpt-4',
    apiKey: '',
    apiBase: ''
  },
  gitlab: {
    serverUrl: 'https://gitlab.com',
    privateToken: '',
    maxFiles: 50,
    contextLines: 5
  },
  notification: {
    dingtalk: {
      enabled: false,
      webhook: '',
      secret: ''
    },
    gitlab: {
      enabled: true
    }
  }
})

const handleSave = () => {
  alert('配置保存成功')
}

const handleReset = () => {
  alert('配置已重置')
}
</script>
