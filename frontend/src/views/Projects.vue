<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="section-header">项目管理</h1>
        <p class="text-xs text-apple-500 mt-1">Manage webhook-enabled GitLab projects</p>
      </div>
      <div class="flex items-center gap-3">
        <div class="relative">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索项目..."
            class="input-field w-64"
          />
          <Search class="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-apple-400" />
        </div>
      </div>
    </div>

    <!-- Stats Overview -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="stat-card group">
        <div class="relative z-10 flex flex-col">
          <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">总项目数</div>
          <div class="text-4xl font-bold text-apple-900 mb-1 tracking-tight">{{ stats.totalProjects }}</div>
          <div class="text-2xs text-apple-600">已配置 Webhook</div>
        </div>
        <FolderKanban class="absolute bottom-4 right-4 w-12 h-12 text-apple-300/30 group-hover:text-apple-blue-500/20 transition-colors duration-300" />
      </div>

      <div class="stat-card group">
        <div class="relative z-10 flex flex-col">
          <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">活跃项目</div>
          <div class="text-4xl font-bold text-apple-900 mb-1 tracking-tight">{{ stats.activeProjects }}</div>
          <div class="text-2xs text-green-600">审查功能已开启</div>
        </div>
        <CheckCircle2 class="absolute bottom-4 right-4 w-12 h-12 text-apple-300/30 group-hover:text-green-500/20 transition-colors duration-300" />
      </div>

      <div class="stat-card group">
        <div class="relative z-10 flex flex-col">
          <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">本周审查</div>
          <div class="text-4xl font-bold text-apple-900 mb-1 tracking-tight">{{ stats.weeklyReviews }}</div>
          <div class="text-2xs text-apple-600">活跃项目审查</div>
        </div>
        <Activity class="absolute bottom-4 right-4 w-12 h-12 text-apple-300/30 group-hover:text-purple-500/20 transition-colors duration-300" />
      </div>

      <div class="stat-card group">
        <div class="relative z-10 flex flex-col">
          <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">最近事件</div>
          <div class="text-4xl font-bold text-apple-900 mb-1 tracking-tight">{{ stats.recentEvents }}</div>
          <div class="text-2xs text-apple-600">24小时内</div>
        </div>
        <GitPullRequest class="absolute bottom-4 right-4 w-12 h-12 text-apple-300/30 group-hover:text-orange-500/20 transition-colors duration-300" />
      </div>
    </div>

    <!-- Projects Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
      <div
        v-for="project in filteredProjects"
        :key="project.project_id"
        class="card group hover:shadow-apple-lg transition-all duration-300 hover:-translate-y-1"
      >
        <div class="p-6 space-y-4">
          <!-- Project Header -->
          <div class="flex items-start justify-between">
            <div class="flex items-start gap-3 flex-1 min-w-0">
              <div class="flex-shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br from-apple-blue-500 to-apple-blue-600 flex items-center justify-center shadow-lg">
                <GitBranch class="w-6 h-6 text-white" />
              </div>
              <div class="flex-1 min-w-0">
                <h3 class="text-base font-semibold text-apple-900 truncate group-hover:text-apple-blue-600 transition-colors">
                  {{ project.project_name }}
                </h3>
                <p class="text-xs text-apple-500 mt-0.5">{{ project.namespace }}</p>
              </div>
            </div>

            <!-- Enable/Disable Toggle -->
            <div class="flex-shrink-0">
              <button
                @click="toggleProjectReview(project.project_id)"
                :disabled="loading"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ease-in-out',
                  project.review_enabled ? 'bg-apple-blue-500' : 'bg-apple-300'
                ]"
              >
                <span
                  :class="[
                    'inline-block h-4 w-4 transform rounded-full bg-white shadow-lg transition-transform duration-200 ease-in-out',
                    project.review_enabled ? 'translate-x-6' : 'translate-x-1'
                  ]"
                ></span>
              </button>
            </div>
          </div>

          <!-- Description -->
          <p class="text-sm text-apple-600 line-clamp-2 min-h-[2.5rem]">
            {{ project.description || '暂无项目描述' }}
          </p>

          <!-- Stats -->
          <div class="flex items-center gap-4 pt-2 border-t border-apple-200/50">
            <div class="flex items-center gap-1.5 text-xs text-apple-600">
              <GitCommit class="w-3.5 h-3.5" />
              <span>{{ project.commits_count || 0 }} commits</span>
            </div>
            <div class="flex items-center gap-1.5 text-xs text-apple-600">
              <GitPullRequest class="w-3.5 h-3.5" />
              <span>{{ project.mr_count || 0 }} MRs</span>
            </div>
            <div class="flex items-center gap-1.5 text-xs text-apple-600">
              <Users class="w-3.5 h-3.5" />
              <span>{{ project.members_count || 0 }}</span>
            </div>
          </div>

          <!-- Last Activity -->
          <div class="flex items-center justify-between pt-2">
            <div class="flex items-center gap-2 text-xs text-apple-500">
              <Clock class="w-3.5 h-3.5" />
              <span>{{ project.last_activity || '未知' }}</span>
            </div>
            <span
              :class="[
                'badge',
                project.review_enabled ? 'badge-success' : 'bg-apple-200 text-apple-700'
              ]"
            >
              {{ project.review_enabled ? '审查已开启' : '审查已关闭' }}
            </span>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 pt-2">
            <button
              @click="viewProjectDetail(project.project_id)"
              class="btn-primary flex-1"
              :disabled="loading"
            >
              <Eye class="w-4 h-4" />
              <span>查看详情</span>
            </button>
            <button
              class="btn-ghost flex-shrink-0"
              @click="openWebhookUrl(project.webhook_url)"
            >
              <ExternalLink class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="filteredProjects.length === 0"
      class="card text-center py-16"
    >
      <div class="flex flex-col items-center gap-4">
        <div class="w-16 h-16 rounded-full bg-apple-100 flex items-center justify-center">
          <FolderKanban class="w-8 h-8 text-apple-400" />
        </div>
        <div>
          <h3 class="text-lg font-semibold text-apple-900 mb-1">暂无项目</h3>
          <p class="text-sm text-apple-500">配置 Webhook 后项目将自动显示在这里</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search,
  FolderKanban,
  CheckCircle2,
  Activity,
  GitPullRequest,
  GitBranch,
  GitCommit,
  Users,
  Clock,
  Eye,
  ExternalLink
} from 'lucide-vue-next'
import {
  getProjects,
  getAllProjectStats,
  enableProjectReview,
  disableProjectReview
} from '@/api'

const router = useRouter()
const searchQuery = ref('')
const loading = ref(false)

const stats = ref({
  totalProjects: 0,
  activeProjects: 0,
  weeklyReviews: 0,
  recentEvents: 0
})

const projects = ref<any[]>([])

const filteredProjects = computed(() => {
  if (!searchQuery.value) return projects.value

  const query = searchQuery.value.toLowerCase()
  return projects.value.filter(project =>
    project.project_name?.toLowerCase().includes(query) ||
    project.namespace?.toLowerCase().includes(query) ||
    project.description?.toLowerCase().includes(query)
  )
})

const loadProjects = async () => {
  try {
    loading.value = true
    const response = await getProjects()
    if (response && response.projects) {
      projects.value = response.projects
    }
  } catch (error) {
    console.error('Failed to load projects:', error)
    alert('加载项目列表失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const response = await getAllProjectStats()
    if (response && response.stats) {
      stats.value = {
        totalProjects: response.stats.total_projects || 0,
        activeProjects: response.stats.active_projects || 0,
        weeklyReviews: response.stats.weekly_reviews || 0,
        recentEvents: response.stats.recent_events || 0
      }
    }
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

const toggleProjectReview = async (projectId: number) => {
  try {
    const project = projects.value.find(p => p.project_id === projectId)
    if (!project) return

    const originalStatus = project.review_enabled
    project.review_enabled = !originalStatus

    try {
      if (project.review_enabled) {
        await enableProjectReview(projectId.toString())
        alert('已启用代码审查')
        stats.value.activeProjects++
      } else {
        await disableProjectReview(projectId.toString())
        alert('已禁用代码审查')
        stats.value.activeProjects--
      }
    } catch (apiError) {
      // Revert on API error
      project.review_enabled = originalStatus
      throw apiError
    }
  } catch (error) {
    console.error('Failed to toggle project review:', error)
    alert('操作失败，请重试')
  }
}

const viewProjectDetail = (projectId: number) => {
  router.push(`/projects/${projectId}`)
}

const openWebhookUrl = (url: string) => {
  if (url) {
    window.open(url, '_blank')
  }
}

const refreshData = async () => {
  await Promise.all([loadProjects(), loadStats()])
}

onMounted(() => {
  refreshData()
})
</script>
