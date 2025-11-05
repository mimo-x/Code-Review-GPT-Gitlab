<template>
  <div class="space-y-6">
    <!-- Header Card -->
    <div class="card">
      <div class="p-6">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h2 class="text-xl font-semibold text-gray-800">审查记录</h2>

          <!-- Search -->
          <div class="relative">
            <div class="absolute inset-y-0 start-0 flex items-center ps-3.5 pointer-events-none">
              <Search class="w-4 h-4 text-gray-400" />
            </div>
            <input
              v-model="searchText"
              type="text"
              class="py-2.5 ps-10 pe-4 block w-full sm:w-80 border-gray-200 rounded-lg text-sm focus:border-blue-500 focus:ring-blue-500"
              placeholder="搜索 MR ID 或项目名"
              @input="handleSearch"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Table Card -->
    <div class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase">ID</th>
              <th class="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase">MR</th>
              <th class="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase">项目</th>
              <th class="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase">标题</th>
              <th class="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase">作者</th>
              <th class="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase">状态</th>
              <th class="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase">LLM</th>
              <th class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">问题数</th>
              <th class="px-6 py-3 text-start text-xs font-medium text-gray-500 uppercase">时间</th>
              <th class="px-6 py-3 text-end text-xs font-medium text-gray-500 uppercase">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200">
            <tr v-for="review in filteredReviews" :key="review.id" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800">{{ review.id }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <span class="badge-info">!{{ review.mrId }}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800">{{ review.project }}</td>
              <td class="px-6 py-4 text-sm text-gray-800 max-w-xs truncate">{{ review.title }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{{ review.author }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <span :class="getStatusBadge(review.status)">{{ review.status }}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{{ review.llmModel }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-center">
                <span v-if="review.issuesCount > 0" class="badge-warning">
                  {{ review.issuesCount }}
                </span>
                <span v-else class="text-green-600 font-medium">0</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{{ review.createdAt }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-end text-sm font-medium">
                <button @click="viewDetail(review.id)" class="text-blue-600 hover:text-blue-800 mr-3">
                  查看详情
                </button>
                <button @click="openGitlab(review.mrUrl)" class="text-gray-600 hover:text-gray-800">
                  <ExternalLink class="w-4 h-4 inline" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="px-6 py-4 border-t border-gray-200">
        <div class="flex items-center justify-between">
          <div class="text-sm text-gray-700">
            显示 <span class="font-medium">1</span> 到 <span class="font-medium">{{ filteredReviews.length }}</span> 条，
            共 <span class="font-medium">{{ totalReviews }}</span> 条
          </div>
          <div class="flex gap-2">
            <button class="btn-secondary">上一页</button>
            <button class="btn-secondary">下一页</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Search, ExternalLink } from 'lucide-vue-next'

const router = useRouter()

const searchText = ref('')
const totalReviews = ref(100)

const reviewsList = ref([
  {
    id: 1,
    mrId: 123,
    project: 'Code-Review-GPT-Gitlab',
    title: 'feat: 添加前端管理界面',
    author: 'developer',
    status: '已完成',
    llmModel: 'GPT-4',
    issuesCount: 3,
    createdAt: '2025-01-15 10:30',
    mrUrl: 'https://gitlab.com/project/merge_requests/123'
  },
  {
    id: 2,
    mrId: 122,
    project: 'Code-Review-GPT-Gitlab',
    title: 'fix: 修复webhook处理bug',
    author: 'admin',
    status: '进行中',
    llmModel: 'DeepSeek',
    issuesCount: 0,
    createdAt: '2025-01-15 09:15',
    mrUrl: 'https://gitlab.com/project/merge_requests/122'
  },
  {
    id: 3,
    mrId: 121,
    project: 'Code-Review-GPT-Gitlab',
    title: 'refactor: 重构LLM调用逻辑',
    author: 'developer',
    status: '已完成',
    llmModel: 'Claude',
    issuesCount: 5,
    createdAt: '2025-01-14 16:45',
    mrUrl: 'https://gitlab.com/project/merge_requests/121'
  },
  {
    id: 4,
    mrId: 120,
    project: 'Code-Review-GPT-Gitlab',
    title: 'docs: 更新README文档',
    author: 'admin',
    status: '已完成',
    llmModel: 'GPT-4',
    issuesCount: 0,
    createdAt: '2025-01-14 14:20',
    mrUrl: 'https://gitlab.com/project/merge_requests/120'
  },
  {
    id: 5,
    mrId: 119,
    project: 'Code-Review-GPT-Gitlab',
    title: 'feat: 添加多智能体支持',
    author: 'developer',
    status: '失败',
    llmModel: 'Gemini',
    issuesCount: 12,
    createdAt: '2025-01-14 11:05',
    mrUrl: 'https://gitlab.com/project/merge_requests/119'
  }
])

const filteredReviews = computed(() => {
  if (!searchText.value) return reviewsList.value
  return reviewsList.value.filter(review =>
    review.project.toLowerCase().includes(searchText.value.toLowerCase()) ||
    review.mrId.toString().includes(searchText.value)
  )
})

const getStatusBadge = (status: string) => {
  const badgeMap: Record<string, string> = {
    '已完成': 'badge-success',
    '进行中': 'badge-info',
    '失败': 'badge-danger',
    '等待中': 'badge-warning'
  }
  return badgeMap[status] || 'badge-info'
}

const handleSearch = () => {
  // Search logic
}

const viewDetail = (id: number) => {
  router.push(`/reviews/${id}`)
}

const openGitlab = (url: string) => {
  window.open(url, '_blank')
}
</script>
