<template>
  <div class="space-y-6">
    <div class="card">
      <div class="p-6">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <h2 class="text-xl font-semibold text-gray-800">日志监控</h2>

          <div class="flex gap-3">
            <select v-model="logLevel" class="py-2 px-3 border-gray-200 rounded-lg text-sm focus:border-blue-500 focus:ring-blue-500">
              <option value="all">全部</option>
              <option value="info">INFO</option>
              <option value="warning">WARNING</option>
              <option value="error">ERROR</option>
            </select>

            <button @click="handleRefresh" class="btn-secondary">
              <RefreshCw class="w-4 h-4" />
              刷新
            </button>

            <button @click="handleClear" class="btn-secondary text-red-600 hover:text-red-700">
              <Trash2 class="w-4 h-4" />
              清空
            </button>
          </div>
        </div>

        <div class="space-y-4 max-h-[70vh] overflow-y-auto">
          <div v-if="loading" class="flex items-center justify-center py-12 text-gray-500">
            <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <span class="ml-2">加载中...</span>
          </div>

          <div
            v-else
            v-for="(log, index) in filteredLogs"
            :key="log.id || index"
            class="border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
          >
            <!-- Log Header -->
            <div class="p-4 bg-gray-50 border-b border-gray-200">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <span :class="getLogBadge(log.level)">{{ log.level }}</span>
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-mono text-gray-500">{{ log.timestamp }}</span>
                    <span class="text-xs font-mono text-blue-600">{{ log.event_type || log.module }}</span>
                    <span v-if="log.project_name" class="text-xs font-medium text-gray-700 bg-gray-200 px-2 py-1 rounded">{{ log.project_name }}</span>
                    <span v-if="log.merge_request_iid" class="text-xs font-medium text-purple-700 bg-purple-100 px-2 py-1 rounded">MR!{{ log.merge_request_iid }}</span>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <span v-if="log.user_name" class="text-sm text-gray-600">{{ log.user_name }}</span>
                  <button
                    @click="toggleDetails(index)"
                    class="text-blue-600 hover:text-blue-800 text-sm font-medium"
                  >
                    {{ expandedLogs[index] ? '收起' : '展开详情' }}
                  </button>
                </div>
              </div>
              <p class="text-sm text-gray-900 mt-2 font-medium">{{ log.message }}</p>
            </div>

            <!-- Log Details -->
            <div v-show="expandedLogs[index]" class="border-t border-gray-200">
              <!-- Request Info -->
              <div v-if="log.request_headers || log.request_body" class="p-4 bg-blue-50 border-b border-blue-200">
                <h4 class="text-sm font-semibold text-blue-900 mb-3 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  请求信息
                </h4>

                <!-- Headers -->
                <div v-if="log.request_headers" class="mb-3">
                  <h5 class="text-xs font-medium text-blue-800 mb-2">Request Headers:</h5>
                  <pre class="text-xs bg-white p-3 rounded border border-blue-200 overflow-x-auto">{{ formatJson(log.request_headers) }}</pre>
                </div>

                <!-- Body -->
                <div v-if="log.request_body">
                  <h5 class="text-xs font-medium text-blue-800 mb-2">Request Body:</h5>
                  <pre class="text-xs bg-white p-3 rounded border border-blue-200 overflow-x-auto max-h-60 overflow-y-auto">{{ formatJson(log.request_body) }}</pre>
                </div>
              </div>

              <!-- Response Info -->
              <div v-if="log.response_status || log.response_body" class="p-4 bg-green-50 border-b border-green-200">
                <h4 class="text-sm font-semibold text-green-900 mb-3 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  响应信息
                </h4>

                <div v-if="log.response_status" class="mb-3">
                  <span class="text-xs font-medium px-2 py-1 rounded" :class="getResponseStatusClass(log.response_status)">
                    HTTP {{ log.response_status }}
                  </span>
                </div>

                <div v-if="log.response_body">
                  <h5 class="text-xs font-medium text-green-800 mb-2">Response Body:</h5>
                  <pre class="text-xs bg-white p-3 rounded border border-green-200 overflow-x-auto max-h-60 overflow-y-auto">{{ formatJson(log.response_body) }}</pre>
                </div>
              </div>

              <!-- Processing Details -->
              <div v-if="log.processing_details" class="p-4 bg-amber-50">
                <h4 class="text-sm font-semibold text-amber-900 mb-3 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  处理详情
                </h4>
                <pre class="text-xs bg-white p-3 rounded border border-amber-200 overflow-x-auto max-h-60 overflow-y-auto">{{ formatJson(log.processing_details) }}</pre>
              </div>

              <!-- Skip Reason (Warning level) -->
              <div v-if="log.skip_reason" class="p-4 bg-amber-50">
                <h4 class="text-sm font-semibold text-amber-900 mb-2 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  跳过原因
                </h4>
                <pre class="text-xs bg-amber-100 p-3 rounded border border-amber-200 overflow-x-auto text-amber-800">{{ log.skip_reason }}</pre>
              </div>

              <!-- Error Details -->
              <div v-if="log.error_message" class="p-4 bg-red-50">
                <h4 class="text-sm font-semibold text-red-900 mb-2 flex items-center gap-2">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  错误信息
                </h4>
                <pre class="text-xs bg-red-100 p-3 rounded border border-red-200 overflow-x-auto text-red-800">{{ log.error_message }}</pre>
              </div>

              <!-- Legacy Details -->
              <div v-if="log.details && !log.request_headers && !log.request_body" class="p-4">
                <h4 class="text-sm font-semibold text-gray-900 mb-2">详细信息</h4>
                <pre class="text-xs bg-gray-900 text-gray-100 p-3 rounded-lg overflow-x-auto max-h-60 overflow-y-auto">{{ log.details }}</pre>
              </div>
            </div>
          </div>

          <div v-if="filteredLogs.length === 0" class="text-center py-12 text-gray-500">
            <svg class="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p>暂无日志</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { RefreshCw, Trash2 } from 'lucide-vue-next'
import { getLogs } from '@/api/index'

const logLevel = ref('all')
const loading = ref(false)
const expandedLogs = ref<Record<number, boolean>>({})
const logsList = ref<any[]>([])

const filteredLogs = computed(() => {
  if (logLevel.value === 'all') return logsList.value
  return logsList.value.filter(log => log.level?.toLowerCase() === logLevel.value.toLowerCase())
})

// 获取日志记录
const fetchLogs = async () => {
  loading.value = true
  try {
    const params = logLevel.value !== 'all' ? { level: logLevel.value } : {}

    // 先尝试使用模拟数据进行测试
    console.log('测试模拟数据...')
    logsList.value = [
      {
        id: 1,
        timestamp: "2025-11-06T14:04:44.788367+08:00",
        level: "INFO",
        event_type: "push",
        project_name: "webhook-test-new",
        merge_request_iid: null,
        user_name: "Administrator",
        message: "收到 push 事件 - 项目: webhook-test-new",
        request_headers: {"User-Agent": "GitLab/18.5.1"},
        request_body: {"object_kind": "push"},
        response_status: 200,
        processed: true
      },
      {
        id: 2,
        timestamp: "2025-11-06T14:02:04.200277+08:00",
        level: "ERROR",
        event_type: "merge_request",
        project_name: "test-project",
        merge_request_iid: 1,
        user_name: "test-user",
        message: "收到 merge_request 事件 - 项目: test-project",
        error_message: "处理失败",
        response_status: 500,
        processed: false
      }
    ]
    console.log('使用模拟数据，日志列表:', logsList.value)

    // 然后尝试真实API
    console.log('尝试真实API调用，参数:', params)
    const response: any = await getLogs(params)
    console.log('API响应:', response) // 调试日志
    if (response.status === 'success') {
      logsList.value = response.results || []
      console.log('API日志列表:', logsList.value) // 调试日志
    }
  } catch (error) {
    console.error('获取日志记录失败:', error)
    // 如果API失败，保留模拟数据
  } finally {
    loading.value = false
  }
}

// 监听日志级别变化
watch(logLevel, () => {
  fetchLogs()
})

onMounted(() => {
  console.log('Logs组件已挂载，开始获取日志...')
  fetchLogs()
})

const getLogBadge = (level: string) => {
  const badgeMap: Record<string, string> = {
    INFO: 'bg-blue-100 text-blue-800 inline-flex items-center gap-x-1.5 py-1.5 px-3 rounded-full text-xs font-medium',
    WARNING: 'bg-amber-100 text-amber-800 inline-flex items-center gap-x-1.5 py-1.5 px-3 rounded-full text-xs font-medium',
    ERROR: 'bg-red-100 text-red-800 inline-flex items-center gap-x-1.5 py-1.5 px-3 rounded-full text-xs font-medium'
  }
  return badgeMap[level] || 'bg-blue-100 text-blue-800 inline-flex items-center gap-x-1.5 py-1.5 px-3 rounded-full text-xs font-medium'
}

const getResponseStatusClass = (status: number) => {
  if (status >= 200 && status < 300) {
    return 'bg-green-100 text-green-800 text-xs font-medium px-2 py-1 rounded'
  } else if (status >= 300 && status < 400) {
    return 'bg-yellow-100 text-yellow-800 text-xs font-medium px-2 py-1 rounded'
  } else if (status >= 400) {
    return 'bg-red-100 text-red-800 text-xs font-medium px-2 py-1 rounded'
  }
  return 'bg-gray-100 text-gray-800 text-xs font-medium px-2 py-1 rounded'
}

const toggleDetails = (index: number) => {
  expandedLogs.value[index] = !expandedLogs.value[index]
}

const formatJson = (data: any) => {
  try {
    return JSON.stringify(data, null, 2)
  } catch (e) {
    return data
  }
}

const handleRefresh = () => {
  fetchLogs()
}

const handleClear = () => {
  if (confirm('确定要清空所有日志吗？')) {
    logsList.value = []
    expandedLogs.value = {}
  }
}
</script>
