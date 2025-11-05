<template>
  <div class="space-y-6">
    <div class="card">
      <div class="p-6">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <h2 class="text-xl font-semibold text-gray-800">日志监控</h2>

          <div class="flex gap-3">
            <select v-model="logLevel" class="py-2 px-3 border-gray-200 rounded-lg text-sm focus:border-blue-500 focus:ring-blue-500">
              <option value="all">全部</option>
              <option value="debug">DEBUG</option>
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
          <div
            v-for="(log, index) in filteredLogs"
            :key="index"
            class="flex gap-4 p-4 rounded-lg hover:bg-gray-50 transition-colors border border-gray-100"
          >
            <div class="flex-shrink-0">
              <span :class="getLogBadge(log.level)">{{ log.level }}</span>
            </div>

            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-mono text-gray-500">{{ log.timestamp }}</span>
                <span class="text-xs font-mono text-blue-600">{{ log.module }}</span>
              </div>
              <p class="text-sm text-gray-900">{{ log.message }}</p>
              <div v-if="log.details" class="mt-2">
                <details class="text-xs">
                  <summary class="cursor-pointer text-blue-600 hover:text-blue-800">详细信息</summary>
                  <pre class="mt-2 p-3 bg-gray-900 text-gray-100 rounded-lg overflow-x-auto">{{ log.details }}</pre>
                </details>
              </div>
            </div>
          </div>

          <div v-if="filteredLogs.length === 0" class="text-center py-12 text-gray-500">
            暂无日志
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { RefreshCw, Trash2 } from 'lucide-vue-next'

const logLevel = ref('all')

const logsList = ref([
  {
    timestamp: '2025-01-15 10:35:23',
    level: 'INFO',
    module: 'webhook_listener',
    message: '收到新的 Merge Request webhook 事件',
    details: '{\n  "event": "merge_request",\n  "mr_id": 123,\n  "project": "Code-Review-GPT-Gitlab"\n}'
  },
  {
    timestamp: '2025-01-15 10:35:26',
    level: 'INFO',
    module: 'review_engine',
    message: '启动代码审查引擎，使用 GPT-4 模型',
    details: null
  },
  {
    timestamp: '2025-01-15 10:35:30',
    level: 'INFO',
    module: 'review_engine',
    message: '代码审查完成，发现 3 个问题',
    details: null
  },
  {
    timestamp: '2025-01-15 10:20:15',
    level: 'WARNING',
    module: 'llm_generator',
    message: 'LLM API 调用失败，正在重试 (1/3)',
    details: '{\n  "error": "Rate limit exceeded",\n  "retry_after": 60\n}'
  },
  {
    timestamp: '2025-01-15 10:18:42',
    level: 'ERROR',
    module: 'gitlab_fetcher',
    message: 'GitLab API 认证失败',
    details: '{\n  "error": "401 Unauthorized",\n  "message": "Invalid token"\n}'
  }
])

const filteredLogs = computed(() => {
  if (logLevel.value === 'all') return logsList.value
  return logsList.value.filter(log => log.level.toLowerCase() === logLevel.value)
})

const getLogBadge = (level: string) => {
  const badgeMap: Record<string, string> = {
    DEBUG: 'badge-info',
    INFO: 'bg-blue-100 text-blue-800 inline-flex items-center gap-x-1.5 py-1.5 px-3 rounded-full text-xs font-medium',
    WARNING: 'badge-warning',
    ERROR: 'badge-danger'
  }
  return badgeMap[level] || 'badge-info'
}

const handleRefresh = () => {
  alert('日志已刷新')
}

const handleClear = () => {
  if (confirm('确定要清空所有日志吗？')) {
    logsList.value = []
  }
}
</script>
