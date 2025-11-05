<template>
  <div class="space-y-6">
    <!-- Back Header -->
    <div>
      <button @click="goBack" class="inline-flex items-center gap-x-2 text-sm text-gray-600 hover:text-gray-800">
        <ArrowLeft class="w-4 h-4" />
        返回列表
      </button>
      <h2 class="text-2xl font-bold text-gray-900 mt-3">审查详情 - MR !{{ reviewData.mrId }}</h2>
    </div>

    <!-- Basic Info Card -->
    <div class="card">
      <div class="p-6">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-lg font-semibold text-gray-800">基本信息</h3>
          <span :class="getStatusBadge(reviewData.status)">{{ reviewData.status }}</span>
        </div>

        <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <dt class="text-sm font-medium text-gray-500">MR ID</dt>
            <dd class="mt-1 text-sm text-gray-900">!{{ reviewData.mrId }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500">项目</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ reviewData.project }}</dd>
          </div>
          <div class="sm:col-span-2">
            <dt class="text-sm font-medium text-gray-500">标题</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ reviewData.title }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500">作者</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ reviewData.author }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500">LLM模型</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ reviewData.llmModel }}</dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500">问题数量</dt>
            <dd class="mt-1">
              <span v-if="reviewData.issuesCount > 0" class="badge-warning">
                {{ reviewData.issuesCount }} 个问题
              </span>
              <span v-else class="text-green-600 font-medium">无问题</span>
            </dd>
          </div>
          <div>
            <dt class="text-sm font-medium text-gray-500">创建时间</dt>
            <dd class="mt-1 text-sm text-gray-900">{{ reviewData.createdAt }}</dd>
          </div>
          <div class="sm:col-span-2">
            <dt class="text-sm font-medium text-gray-500">MR链接</dt>
            <dd class="mt-1">
              <a :href="reviewData.mrUrl" target="_blank" class="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1">
                {{ reviewData.mrUrl }}
                <ExternalLink class="w-3 h-3" />
              </a>
            </dd>
          </div>
        </dl>
      </div>
    </div>

    <!-- Summary Card -->
    <div class="card">
      <div class="p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-gray-800">审查摘要</h3>
          <div class="flex items-center gap-2">
            <Star class="w-5 h-5 text-yellow-400 fill-yellow-400" />
            <span class="text-lg font-semibold">{{ reviewData.score }}/5</span>
          </div>
        </div>
        <p class="text-gray-700 leading-relaxed bg-gray-50 p-4 rounded-lg">
          {{ reviewData.summary }}
        </p>
      </div>
    </div>

    <!-- Issues Card -->
    <div class="card">
      <div class="p-6">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-lg font-semibold text-gray-800">审查问题</h3>
          <span class="badge-info">共 {{ reviewData.issues.length }} 个问题</span>
        </div>

        <div class="space-y-4">
          <div v-for="(issue, index) in reviewData.issues" :key="index" class="border border-gray-200 rounded-lg overflow-hidden">
            <button
              @click="toggleIssue(index)"
              class="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
            >
              <div class="flex items-center gap-3">
                <span :class="getSeverityBadge(issue.severity)">{{ issue.severity }}</span>
                <span class="text-sm font-medium text-gray-900">{{ issue.file }} : {{ issue.line }}</span>
                <span class="badge-info text-xs">{{ issue.category }}</span>
              </div>
              <ChevronDown :class="['w-5 h-5 text-gray-500 transition-transform', openIssues.includes(index) ? 'rotate-180' : '']" />
            </button>

            <div v-if="openIssues.includes(index)" class="p-4 bg-white space-y-4">
              <div>
                <h4 class="text-sm font-semibold text-gray-900 mb-2">问题描述：</h4>
                <p class="text-sm text-gray-700">{{ issue.description }}</p>
              </div>
              <div v-if="issue.suggestion">
                <h4 class="text-sm font-semibold text-gray-900 mb-2">建议修改：</h4>
                <pre class="text-xs bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">{{ issue.suggestion }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, ExternalLink, Star, ChevronDown } from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const openIssues = ref<number[]>([])

const reviewData = ref({
  id: Number(route.params.id),
  mrId: 123,
  project: 'Code-Review-GPT-Gitlab',
  title: 'feat: 添加前端管理界面',
  author: 'developer',
  status: '已完成',
  llmModel: 'GPT-4',
  issuesCount: 3,
  createdAt: '2025-01-15 10:30:25',
  mrUrl: 'https://gitlab.com/project/merge_requests/123',
  score: 4.5,
  summary: '本次代码审查针对前端管理界面的新增功能进行了全面分析。整体代码质量良好，遵循了Vue 3和TypeScript的最佳实践。主要发现了3个需要改进的问题，包括1个安全性问题和2个代码质量问题。建议在合并前修复高优先级问题。',
  issues: [
    {
      severity: '高',
      category: '安全问题',
      file: 'src/utils/request.ts',
      line: 45,
      description: 'API请求中未对敏感数据进行加密处理，存在数据泄露风险',
      suggestion: `建议使用crypto-js对敏感字段进行加密：

// import CryptoJS from 'crypto-js'

const encryptData = (data) => {
  return CryptoJS.AES.encrypt(JSON.stringify(data), secretKey).toString()
}`
    },
    {
      severity: '中',
      category: '代码质量',
      file: 'src/views/Dashboard.vue',
      line: 128,
      description: 'ECharts图表初始化逻辑重复，建议抽取为公共方法',
      suggestion: `// 抽取公共初始化方法
const initChart = (ref: Ref<HTMLElement>, option: EChartsOption) => {
  if (!ref.value) return
  const chart = echarts.init(ref.value)
  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
  return chart
}`
    },
    {
      severity: '低',
      category: '性能优化',
      file: 'src/views/Reviews.vue',
      line: 89,
      description: '列表搜索未使用防抖处理，频繁输入可能导致性能问题',
      suggestion: `// 使用lodash的debounce
// import { debounce } from 'lodash-es'

const handleSearch = debounce(() => {
  currentPage.value = 1
}, 300)`
    }
  ]
})

const goBack = () => {
  router.back()
}

const getStatusBadge = (status: string) => {
  const badgeMap: Record<string, string> = {
    '已完成': 'badge-success',
    '进行中': 'badge-info',
    '失败': 'badge-danger'
  }
  return badgeMap[status] || 'badge-info'
}

const getSeverityBadge = (severity: string) => {
  const badgeMap: Record<string, string> = {
    '高': 'badge-danger',
    '中': 'badge-warning',
    '低': 'badge-info'
  }
  return badgeMap[severity] || 'badge-info'
}

const toggleIssue = (index: number) => {
  const idx = openIssues.value.indexOf(index)
  if (idx > -1) {
    openIssues.value.splice(idx, 1)
  } else {
    openIssues.value.push(index)
  }
}
</script>
