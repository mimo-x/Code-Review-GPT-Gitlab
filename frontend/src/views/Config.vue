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

        <div class="bg-apple-50/50 border border-apple-200/40 rounded-xl p-4 text-sm text-apple-600">
          管理全局通知通道。每个项目可在项目详情页选择需要启用的通道，支持为不同项目配置独立的通知名称与 Webhook。
        </div>

        <div class="flex items-center justify-between">
          <h4 class="text-sm font-semibold text-apple-900">通道列表</h4>
          <button @click="openChannelForm()" class="btn-primary">
            <PlusCircle class="w-4 h-4" />
            新建通道
          </button>
        </div>

        <div v-if="totalChannelCount === 0" class="p-6 bg-apple-50 border border-dashed border-apple-200 text-center rounded-xl text-sm text-apple-500">
          暂无通知通道，请点击「新建通道」开始配置。
        </div>

        <div v-else class="space-y-6">
          <div v-for="type in channelTypes" :key="type.value" class="space-y-3">
            <div class="flex items-center justify-between">
              <div class="text-sm font-medium text-apple-900">{{ type.label }}</div>
              <button @click="openChannelForm(type.value)" class="text-xs text-apple-blue-600 hover:text-apple-blue-500 flex items-center gap-1">
                <PlusCircle class="w-3 h-3" />
                新增
              </button>
            </div>

            <div v-if="groupedChannels[type.value]?.length" class="space-y-3">
              <div
                v-for="channel in groupedChannels[type.value]"
                :key="channel.id"
                class="p-4 border border-apple-200/60 rounded-xl bg-white shadow-sm space-y-3"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="text-sm font-semibold text-apple-900">{{ channel.name }}</div>
                    <div class="text-xs text-apple-500 mt-1">{{ channel.description || '暂无备注' }}</div>
                  </div>
                  <div class="flex items-center gap-2">
                    <span v-if="channel.is_default" class="badge badge-success">默认</span>
                    <span v-if="channel.is_active === false" class="badge bg-apple-200 text-apple-700">停用</span>
                  </div>
                </div>
                <div class="text-xs text-apple-500 space-y-1">
                  <div v-if="channel.webhook_url">Webhook：{{ channel.webhook_url }}</div>
                  <div v-else>未配置 Webhook</div>
                </div>
                <div class="flex items-center gap-3 pt-2">
                  <button class="btn-secondary" @click="editChannel(channel)">
                    <Pencil class="w-4 h-4" />
                    编辑
                  </button>
                  <button class="btn-ghost text-red-500 hover:text-red-600" @click="removeChannel(channel)">
                    <Trash2 class="w-4 h-4" />
                    删除
                  </button>
                </div>
              </div>
            </div>
            <div v-else class="text-xs text-apple-500 bg-apple-50 rounded-lg px-3 py-2">暂无 {{ type.label }} 通道</div>
          </div>
        </div>

        <div v-if="channelEditorVisible" id="channel-editor" class="border-t border-apple-200/60 pt-6 space-y-4">
          <div class="flex items-center justify-between">
            <h4 class="text-sm font-semibold text-apple-900">{{ channelForm.id ? '编辑通道' : '新建通道' }}</h4>
            <button class="text-xs text-apple-500 hover:text-apple-700" @click="cancelChannelEdit">取消</button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="config-field-group">
              <label class="config-label">通道名称</label>
              <input v-model="channelForm.name" type="text" class="input-field" placeholder="用于区分不同项目的通道名称" />
            </div>
            <div class="config-field-group">
              <label class="config-label">通道类型</label>
              <select v-model="channelForm.notification_type" class="input-field" :disabled="channelForm.id !== null">
                <option v-for="type in channelTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
              </select>
            </div>
            <div class="config-field-group md:col-span-2">
              <label class="config-label">备注</label>
              <textarea v-model="channelForm.description" class="input-field" rows="2" placeholder="补充说明该通道的使用场景"></textarea>
            </div>
            <div
              class="config-field-group md:col-span-2"
              v-if="['dingtalk', 'feishu', 'slack', 'wechat'].includes(channelForm.notification_type)"
            >
              <label class="config-label">Webhook URL</label>
              <input v-model="channelForm.webhook_url" type="text" class="input-field" placeholder="https://" />
            </div>
            <div
              class="config-field-group md:col-span-2"
              v-if="['dingtalk', 'feishu'].includes(channelForm.notification_type)"
            >
              <label class="config-label">Secret</label>
              <input v-model="channelForm.secret" type="text" class="input-field" placeholder="可选：签名密钥" />
            </div>
            <div class="flex items-center gap-4 md:col-span-2">
              <label class="flex items-center gap-2 text-xs text-apple-600">
                <input v-model="channelForm.is_active" type="checkbox" />
                启用此通道
              </label>
              <label class="flex items-center gap-2 text-xs text-apple-600">
                <input v-model="channelForm.is_default" type="checkbox" />
                设为默认通道
              </label>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <button @click="submitChannelForm" class="btn-primary" :disabled="channelSaving">
              <Save class="w-4 h-4" />
              {{ channelSaving ? '保存中...' : '保存通道' }}
            </button>
            <button @click="cancelChannelEdit" class="btn-secondary" :disabled="channelSaving">
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { Save, RotateCcw, CheckCircle, XCircle, PlusCircle, Pencil, Trash2 } from 'lucide-vue-next'
import {
  getConfigSummary,
  batchUpdateConfig,
  getNotificationChannels,
  createNotificationChannel,
  updateNotificationChannel,
  deleteNotificationChannel
} from '@/api/index'

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
  }
})

const channels = ref<any[]>([])
const baseChannelTypes: Record<string, string> = {
  dingtalk: '钉钉通知',
  feishu: '飞书通知',
  wechat: '企业微信通知',
  slack: 'Slack 通知',
  gitlab: 'GitLab 评论',
  email: '邮件通知'
}

const channelEditorVisible = ref(false)
const channelSaving = ref(false)
const channelForm = ref({
  id: null as number | null,
  name: '',
  notification_type: 'dingtalk',
  description: '',
  webhook_url: '',
  secret: '',
  is_active: true,
  is_default: false
})

const channelTypes = computed(() => {
  const typeSet = new Set<string>(Object.keys(baseChannelTypes))
  channels.value.forEach(channel => typeSet.add(channel.notification_type))
  return Array.from(typeSet).map(value => ({
    value,
    label: baseChannelTypes[value] || value
  }))
})

const groupedChannels = computed(() => {
  const map: Record<string, any[]> = {}
  channelTypes.value.forEach(item => {
    map[item.value] = []
  })
  channels.value.forEach(channel => {
    if (!map[channel.notification_type]) {
      map[channel.notification_type] = []
    }
    map[channel.notification_type].push(channel)
  })
  return map
})

const totalChannelCount = computed(() => channels.value.length)

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

const normalizeChannelList = (data: any) => {
  if (!data) return []
  if (Array.isArray(data)) return data
  if (Array.isArray(data.results)) return data.results
  if (Array.isArray(data.channels)) return data.channels
  return []
}

const resetChannelForm = (notificationType?: string) => {
  channelForm.value = {
    id: null,
    name: '',
    notification_type: notificationType || channelTypes.value[0]?.value || 'dingtalk',
    description: '',
    webhook_url: '',
    secret: '',
    is_active: true,
    is_default: false
  }
}

const refreshChannels = async () => {
  try {
    const response = await getNotificationChannels()
    channels.value = normalizeChannelList(response)
  } catch (error) {
    console.error('Failed to load channels:', error)
    showMessage('加载通知通道失败', 'error')
  }
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

    // 更新通知通道列表
    if (data.channels) {
      channels.value = normalizeChannelList(data.channels)
    } else {
      await refreshChannels()
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
      }
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

const openChannelForm = (notificationType?: string) => {
  resetChannelForm(notificationType)
  channelEditorVisible.value = true
  nextTick(() => {
    const el = document.getElementById('channel-editor')
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })
}

const editChannel = (channel: any) => {
  channelForm.value = {
    id: channel.id,
    name: channel.name,
    notification_type: channel.notification_type,
    description: channel.description || '',
    webhook_url: channel.webhook_url || '',
    secret: channel.secret || '',
    is_active: channel.is_active !== false,
    is_default: channel.is_default || false
  }
  channelEditorVisible.value = true
}

const cancelChannelEdit = () => {
  channelEditorVisible.value = false
  resetChannelForm()
}

const submitChannelForm = async () => {
  channelSaving.value = true
  try {
    const payload: any = {
      name: channelForm.value.name,
      notification_type: channelForm.value.notification_type,
      description: channelForm.value.description,
      is_active: channelForm.value.is_active,
      is_default: channelForm.value.is_default
    }

    if (['dingtalk', 'feishu', 'slack', 'wechat'].includes(channelForm.value.notification_type)) {
      payload.webhook_url = channelForm.value.webhook_url
    }

    if (['dingtalk', 'feishu'].includes(channelForm.value.notification_type)) {
      payload.secret = channelForm.value.secret
    }

    if (channelForm.value.id) {
      await updateNotificationChannel(channelForm.value.id, payload)
      showMessage('通知通道更新成功')
    } else {
      await createNotificationChannel(payload)
      showMessage('通知通道创建成功')
    }

    channelEditorVisible.value = false
    resetChannelForm()
    await refreshChannels()

  } catch (error) {
    console.error('Failed to save notification channel:', error)
    showMessage('保存通知通道失败', 'error')
  } finally {
    channelSaving.value = false
  }
}

const removeChannel = async (channel: any) => {
  if (!channel?.id) return

  const confirmed = window.confirm(`确认删除通道「${channel.name}」吗？`)
  if (!confirmed) return

  try {
    await deleteNotificationChannel(channel.id)
    showMessage('已删除通知通道')
    await refreshChannels()
  } catch (error) {
    console.error('Failed to delete notification channel:', error)
    showMessage('删除通知通道失败', 'error')
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
