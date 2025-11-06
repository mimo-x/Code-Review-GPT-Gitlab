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
            <tr v-if="loading">
              <td colspan="10" class="px-6 py-12 text-center text-gray-500">
                <div class="flex items-center justify-center">
                  <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                  <span class="ml-2">加载中...</span>
                </div>
              </td>
            </tr>
            <tr v-else v-for="review in filteredReviews" :key="review.id" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800">{{ review.id }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <span class="badge-info">!{{ review.mrId }}</span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-800">{{ review.project }}</td>
              <td class="px-6 py-4 text-sm text-gray-800 max-w-xs truncate">{{ review.title }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{{ review.author }}</td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <span :class="getStatusBadge(review.status)">{{ review.statusText }}</span>
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
                <button @click="openGitlab(review.mrUrl)" class="btn-primary inline-flex items-center gap-2">
                  <ExternalLink class="w-4 h-4" />
                  查看 MR
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
import { ref, computed, onMounted } from 'vue'
import { Search, ExternalLink } from 'lucide-vue-next'
import { getReviews } from '@/api/index'

const searchText = ref('')
const loading = ref(false)
const totalReviews = ref(0)
const reviewsList = ref([])

const filteredReviews = computed(() => {
  if (!searchText.value) return reviewsList.value
  return reviewsList.value.filter(review =>
    review.project.toLowerCase().includes(searchText.value.toLowerCase()) ||
    review.mrId.toString().includes(searchText.value)
  )
})

// 获取审核记录
const fetchReviews = async () => {
  loading.value = true
  try {
    const response = await getReviews()
    if (response.data.status === 'success') {
      reviewsList.value = response.data.results || []
      totalReviews.value = response.data.total || response.data.count || 0
    }
  } catch (error) {
    console.error('获取审核记录失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchReviews()
})

const getStatusBadge = (status: string) => {
  const badgeMap: Record<string, string> = {
    'completed': 'badge-success',
    'processing': 'badge-info',
    'failed': 'badge-danger',
    'pending': 'badge-warning',
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

const openGitlab = (url: string) => {
  window.open(url, '_blank')
}
</script>
