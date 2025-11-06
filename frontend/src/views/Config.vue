<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-gray-900">配置管理</h2>
      <div class="flex gap-3">
        <button @click="handleSave" :disabled="saving" class="btn-primary">
          <Save class="w-4 h-4" />
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
        <button @click="handleReset" :disabled="saving" class="btn-secondary">
          <RotateCcw class="w-4 h-4" />
          重置
        </button>
      </div>
    </div>

    <!-- 状态消息 -->
    <div v-if="message" :class="[
      'p-4 rounded-md',
      messageType === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
    ]">
      <div class="flex">
        <div class="flex-shrink-0">
          <CheckCircle v-if="messageType === 'success'" class="h-5 w-5 text-green-400" />
          <XCircle v-else class="h-5 w-5 text-red-400" />
        </div>
        <div class="ml-3">
          <p class="text-sm font-medium">{{ message }}</p>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="config-tabs">
      <nav class="-mb-px flex space-x-8">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          @click="activeTab = tab.key"
          :class="[
            'config-tab',
            activeTab === tab.key ? 'config-tab-active' : 'config-tab-inactive'
          ]"
        >
          {{ tab.label }}
        </button>
      </nav>
    </div>

    <!-- LLM Config -->
    <div v-show="activeTab === 'llm'" class="config-section">
      <div class="p-6 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-apple-blue-500 rounded-full"></div>
          <h3 class="text-lg font-semibold text-apple-900">LLM 配置</h3>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="config-field-group">
            <label class="config-label">LLM 提供商</label>
            <select v-model="config.llm.provider" class="input-field">
              <option value="openai">OpenAI GPT-4</option>
              <option value="deepseek">DeepSeek</option>
              <option value="claude">Anthropic Claude</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </div>

          <div class="config-field-group">
            <label class="config-label">模型名称</label>
            <input v-model="config.llm.model" type="text" class="input-field" placeholder="例如: gpt-4" />
          </div>

          <div class="md:col-span-2 config-field-group">
            <label class="config-label">API Key</label>
            <input v-model="config.llm.apiKey" type="password" class="input-field" placeholder="请输入 API Key" />
          </div>

          <div class="md:col-span-2 config-field-group">
            <label class="config-label">API Base URL (可选)</label>
            <input v-model="config.llm.apiBase" type="text" class="input-field" placeholder="自定义API端点" />
          </div>
        </div>
      </div>
    </div>

    <!-- GitLab Config -->
    <div v-show="activeTab === 'gitlab'" class="config-section">
      <div class="p-6 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-orange-500 rounded-full"></div>
          <h3 class="text-lg font-semibold text-apple-900">GitLab 配置</h3>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="md:col-span-2 config-field-group">
            <label class="config-label">GitLab URL</label>
            <input v-model="config.gitlab.serverUrl" type="text" class="input-field" placeholder="https://gitlab.com" />
          </div>

          <div class="md:col-span-2 config-field-group">
            <label class="config-label">Access Token</label>
            <input v-model="config.gitlab.privateToken" type="password" class="input-field" placeholder="GitLab Access Token" />
          </div>

          <div class="config-field-group">
            <label class="config-label">最大审查文件数</label>
            <input v-model.number="config.gitlab.maxFiles" type="number" class="input-field" min="1" max="200" />
          </div>

          <div class="config-field-group">
            <label class="config-label">上下文行数</label>
            <input v-model.number="config.gitlab.contextLines" type="number" class="input-field" min="0" max="20" />
          </div>
        </div>
      </div>
    </div>

    <!-- Notification Config -->
    <div v-show="activeTab === 'notification'" class="config-section">
      <div class="p-6 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-2 h-2 bg-green-500 rounded-full"></div>
          <h3 class="text-lg font-semibold text-apple-900">通知配置</h3>
        </div>

        <div class="space-y-6">
          <div class="p-4 rounded-xl bg-apple-50/50 border border-apple-200/30">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                  <div class="w-4 h-4 bg-blue-500 rounded-sm"></div>
                </div>
                <h4 class="font-medium text-apple-900">钉钉通知</h4>
              </div>
              <label class="config-toggle">
                <input v-model="config.notification.dingtalk.enabled" type="checkbox" class="config-toggle-input" />
                <div class="config-toggle-slider"></div>
              </label>
            </div>

            <div v-if="config.notification.dingtalk.enabled" class="space-y-4">
              <div class="config-field-group">
                <label class="config-label">Webhook URL</label>
                <input v-model="config.notification.dingtalk.webhook" type="text" class="input-field" placeholder="https://oapi.dingtalk.com/robot/send?access_token=xxx" />
              </div>
              <div class="config-field-group">
                <label class="config-label">Secret</label>
                <input v-model="config.notification.dingtalk.secret" type="password" class="input-field" placeholder="钉钉机器人密钥" />
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-apple-50/50 border border-apple-200/30">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 bg-orange-100 rounded-lg flex items-center justify-center">
                  <div class="w-4 h-4 bg-orange-500 rounded-full"></div>
                </div>
                <h4 class="font-medium text-apple-900">GitLab 评论</h4>
              </div>
              <label class="config-toggle">
                <input v-model="config.notification.gitlab.enabled" type="checkbox" class="config-toggle-input" checked />
                <div class="config-toggle-slider"></div>
              </label>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-apple-50/50 border border-apple-200/30">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
                  <div class="w-4 h-4 bg-green-500 rounded-sm"></div>
                </div>
                <h4 class="font-medium text-apple-900">飞书通知</h4>
              </div>
              <label class="config-toggle">
                <input v-model="config.notification.feishu.enabled" type="checkbox" class="config-toggle-input" />
                <div class="config-toggle-slider"></div>
              </label>
            </div>

            <div v-if="config.notification.feishu.enabled" class="space-y-4">
              <div class="config-field-group">
                <label class="config-label">Webhook URL</label>
                <input v-model="config.notification.feishu.webhook" type="text" class="input-field" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" />
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="config-field-group">
                  <label class="config-label">App ID</label>
                  <input v-model="config.notification.feishu.app_id" type="text" class="input-field" placeholder="应用ID" />
                </div>
                <div class="config-field-group">
                  <label class="config-label">App Secret</label>
                  <input v-model="config.notification.feishu.app_secret" type="password" class="input-field" placeholder="应用密钥" />
                </div>
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-apple-50/50 border border-apple-200/30">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                  <div class="w-4 h-4 bg-blue-500 rounded-sm"></div>
                </div>
                <h4 class="font-medium text-apple-900">企业微信通知</h4>
              </div>
              <label class="config-toggle">
                <input v-model="config.notification.wechat.enabled" type="checkbox" class="config-toggle-input" />
                <div class="config-toggle-slider"></div>
              </label>
            </div>

            <div v-if="config.notification.wechat.enabled" class="space-y-4">
              <div class="config-field-group">
                <label class="config-label">Webhook URL</label>
                <input v-model="config.notification.wechat.webhook" type="text" class="input-field" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" />
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div class="config-field-group">
                  <label class="config-label">企业ID</label>
                  <input v-model="config.notification.wechat.corp_id" type="text" class="input-field" placeholder="企业ID" />
                </div>
                <div class="config-field-group">
                  <label class="config-label">企业密钥</label>
                  <input v-model="config.notification.wechat.corp_secret" type="password" class="input-field" placeholder="企业密钥" />
                </div>
                <div class="config-field-group">
                  <label class="config-label">应用ID</label>
                  <input v-model="config.notification.wechat.agent_id" type="text" class="input-field" placeholder="应用ID" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Save, RotateCcw, CheckCircle, XCircle } from 'lucide-vue-next'
import { getConfigSummary, batchUpdateConfig } from '@/api/index'

// 响应式数据
const activeTab = ref('llm')
const saving = ref(false)
const message = ref('')
const messageType = ref<'success' | 'error'>('success')

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
    },
    feishu: {
      enabled: false,
      webhook: '',
      app_id: '',
      app_secret: ''
    },
    wechat: {
      enabled: false,
      corp_id: '',
      corp_secret: '',
      agent_id: '',
      webhook: ''
    }
  }
})

// 原始配置，用于重置
const originalConfig = ref({})

// 显示消息
const showMessage = (text: string, type: 'success' | 'error' = 'success') => {
  message.value = text
  messageType.value = type
  setTimeout(() => {
    message.value = ''
  }, 3000)
}

// 加载配置
const loadConfig = async () => {
  try {
    const response = await getConfigSummary()
    console.log('API Response:', response) // 添加调试日志
    const data = response

    // 更新LLM配置
    if (data.llm) {
      config.value.llm = {
        provider: data.llm.provider || 'openai',
        model: data.llm.model || 'gpt-4',
        apiKey: data.llm.api_key || '',
        apiBase: data.llm.api_base || ''
      }
    }

    // 更新GitLab配置
    if (data.gitlab) {
      config.value.gitlab = {
        serverUrl: data.gitlab.server_url || 'https://gitlab.com',
        privateToken: data.gitlab.private_token || '',
        maxFiles: data.gitlab.max_files || 50,
        contextLines: data.gitlab.context_lines || 5
      }
    }

    // 更新通知配置
    if (data.notifications && data.notifications.length > 0) {
      console.log('Notifications data:', data.notifications)
      data.notifications.forEach((notif: any) => {
        if (notif.notification_type === 'dingtalk') {
          console.log('Dingtalk config:', notif)
          config.value.notification.dingtalk = {
            enabled: notif.enabled,
            webhook: notif.webhook || '',
            secret: notif.secret || ''
          }
          console.log('Updated dingtalk config:', config.value.notification.dingtalk)
        } else if (notif.notification_type === 'gitlab') {
          config.value.notification.gitlab = {
            enabled: notif.enabled
          }
        } else if (notif.notification_type === 'feishu') {
          config.value.notification.feishu = {
            enabled: notif.enabled,
            webhook: notif.webhook || '',
            app_id: notif.app_id || '',
            app_secret: notif.app_secret || ''
          }
        } else if (notif.notification_type === 'wechat') {
          config.value.notification.wechat = {
            enabled: notif.enabled,
            corp_id: notif.corp_id || '',
            corp_secret: notif.corp_secret || '',
            agent_id: notif.agent_id || '',
            webhook: notif.webhook || ''
          }
        }
      })
    }

    // 保存原始配置
    originalConfig.value = JSON.parse(JSON.stringify(config.value))

  } catch (error) {
    console.error('Failed to load config:', error)
    showMessage('加载配置失败', 'error')
  }
}

// 保存配置
const handleSave = async () => {
  saving.value = true
  try {
    // 准备API数据格式
    const apiData = {
      llm: {
        provider: config.value.llm.provider,
        model: config.value.llm.model,
        api_key: config.value.llm.apiKey,
        api_base: config.value.llm.apiBase || null,
        is_active: true
      },
      gitlab: {
        server_url: config.value.gitlab.serverUrl,
        private_token: config.value.gitlab.privateToken,
        max_files: config.value.gitlab.maxFiles,
        context_lines: config.value.gitlab.contextLines,
        is_active: true
      },
      notifications: [
        {
          notification_type: 'dingtalk',
          enabled: config.value.notification.dingtalk.enabled,
          webhook: config.value.notification.dingtalk.webhook,
          secret: config.value.notification.dingtalk.secret,
          is_active: true
        },
        {
          notification_type: 'gitlab',
          enabled: config.value.notification.gitlab.enabled,
          is_active: true
        },
        {
          notification_type: 'feishu',
          enabled: config.value.notification.feishu.enabled,
          webhook: config.value.notification.feishu.webhook,
          app_id: config.value.notification.feishu.app_id,
          app_secret: config.value.notification.feishu.app_secret,
          is_active: true
        },
        {
          notification_type: 'wechat',
          enabled: config.value.notification.wechat.enabled,
          corp_id: config.value.notification.wechat.corp_id,
          corp_secret: config.value.notification.wechat.corp_secret,
          agent_id: config.value.notification.wechat.agent_id,
          webhook: config.value.notification.wechat.webhook,
          is_active: true
        }
      ]
    }

    await batchUpdateConfig(apiData)
    showMessage('配置保存成功')

    // 更新原始配置
    originalConfig.value = JSON.parse(JSON.stringify(config.value))

  } catch (error) {
    console.error('Failed to save config:', error)
    showMessage('保存配置失败', 'error')
  } finally {
    saving.value = false
  }
}

// 重置配置
const handleReset = () => {
  if (JSON.stringify(originalConfig.value)) {
    config.value = JSON.parse(JSON.stringify(originalConfig.value))
    showMessage('配置已重置')
  }
}

// 页面加载时获取配置
onMounted(() => {
  loadConfig()
})
</script>
