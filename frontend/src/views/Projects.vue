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
        :key="project.id"
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
                  {{ project.name }}
                </h3>
                <p class="text-xs text-apple-500 mt-0.5">{{ project.namespace }}</p>
              </div>
            </div>

            <!-- Enable/Disable Toggle -->
            <div class="flex-shrink-0">
              <button
                @click="toggleProjectReview(project.id)"
                :class="[
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ease-in-out',
                  project.reviewEnabled ? 'bg-apple-blue-500' : 'bg-apple-300'
                ]"
              >
                <span
                  :class="[
                    'inline-block h-4 w-4 transform rounded-full bg-white shadow-lg transition-transform duration-200 ease-in-out',
                    project.reviewEnabled ? 'translate-x-6' : 'translate-x-1'
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
              <span>{{ project.commitsCount }} commits</span>
            </div>
            <div class="flex items-center gap-1.5 text-xs text-apple-600">
              <GitPullRequest class="w-3.5 h-3.5" />
              <span>{{ project.mrCount }} MRs</span>
            </div>
            <div class="flex items-center gap-1.5 text-xs text-apple-600">
              <Users class="w-3.5 h-3.5" />
              <span>{{ project.membersCount }}</span>
            </div>
          </div>

          <!-- Last Activity -->
          <div class="flex items-center justify-between pt-2">
            <div class="flex items-center gap-2 text-xs text-apple-500">
              <Clock class="w-3.5 h-3.5" />
              <span>{{ project.lastActivity }}</span>
            </div>
            <span
              :class="[
                'badge',
                project.reviewEnabled ? 'badge-success' : 'bg-apple-200 text-apple-700'
              ]"
            >
              {{ project.reviewEnabled ? '审查已开启' : '审查已关闭' }}
            </span>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 pt-2">
            <button
              @click="viewProjectDetail(project.id)"
              class="btn-primary flex-1"
            >
              <Eye class="w-4 h-4" />
              <span>查看详情</span>
            </button>
            <button
              class="btn-ghost flex-shrink-0"
              @click="openWebhookUrl(project.webhookUrl)"
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
import { ref, computed } from 'vue'
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

const router = useRouter()
const searchQuery = ref('')

const stats = ref({
  totalProjects: 12,
  activeProjects: 8,
  weeklyReviews: 156,
  recentEvents: 43
})

const projects = ref([
  {
    id: 1,
    name: 'Code-Review-GPT-Gitlab',
    namespace: 'DevOps / AI Tools',
    description: 'AI-powered code review tool for GitLab merge requests using LLM models',
    reviewEnabled: true,
    commitsCount: 324,
    mrCount: 45,
    membersCount: 8,
    lastActivity: '2 分钟前',
    webhookUrl: 'https://gitlab.com/devops/code-review-gpt'
  },
  {
    id: 2,
    name: 'Frontend-Dashboard',
    namespace: 'Frontend / Vue',
    description: 'Modern dashboard built with Vue 3, Vite, and Tailwind CSS',
    reviewEnabled: true,
    commitsCount: 189,
    mrCount: 28,
    membersCount: 5,
    lastActivity: '15 分钟前',
    webhookUrl: 'https://gitlab.com/frontend/dashboard'
  },
  {
    id: 3,
    name: 'Backend-API-Service',
    namespace: 'Backend / Microservices',
    description: 'RESTful API service built with FastAPI and PostgreSQL',
    reviewEnabled: true,
    commitsCount: 456,
    mrCount: 67,
    membersCount: 12,
    lastActivity: '1 小时前',
    webhookUrl: 'https://gitlab.com/backend/api-service'
  },
  {
    id: 4,
    name: 'Mobile-App-iOS',
    namespace: 'Mobile / iOS',
    description: 'Native iOS application built with Swift and SwiftUI',
    reviewEnabled: false,
    commitsCount: 267,
    mrCount: 34,
    membersCount: 6,
    lastActivity: '3 小时前',
    webhookUrl: 'https://gitlab.com/mobile/ios-app'
  },
  {
    id: 5,
    name: 'DevOps-Infrastructure',
    namespace: 'DevOps / Infrastructure',
    description: 'Infrastructure as Code using Terraform and Ansible',
    reviewEnabled: true,
    commitsCount: 145,
    mrCount: 23,
    membersCount: 4,
    lastActivity: '5 小时前',
    webhookUrl: 'https://gitlab.com/devops/infrastructure'
  },
  {
    id: 6,
    name: 'ML-Model-Training',
    namespace: 'AI / Machine Learning',
    description: 'Machine learning model training pipeline using PyTorch',
    reviewEnabled: true,
    commitsCount: 198,
    mrCount: 31,
    membersCount: 7,
    lastActivity: '8 小时前',
    webhookUrl: 'https://gitlab.com/ai/ml-training'
  },
  {
    id: 7,
    name: 'Documentation-Site',
    namespace: 'Documentation / Docs',
    description: 'Technical documentation site built with VitePress',
    reviewEnabled: false,
    commitsCount: 89,
    mrCount: 15,
    membersCount: 3,
    lastActivity: '1 天前',
    webhookUrl: 'https://gitlab.com/docs/documentation'
  },
  {
    id: 8,
    name: 'Testing-Framework',
    namespace: 'QA / Testing',
    description: 'Automated testing framework using Playwright and Jest',
    reviewEnabled: true,
    commitsCount: 234,
    mrCount: 41,
    membersCount: 9,
    lastActivity: '1 天前',
    webhookUrl: 'https://gitlab.com/qa/testing-framework'
  },
  {
    id: 9,
    name: 'Design-System',
    namespace: 'Design / UI',
    description: 'Component library and design system for all products',
    reviewEnabled: true,
    commitsCount: 312,
    mrCount: 52,
    membersCount: 11,
    lastActivity: '2 天前',
    webhookUrl: 'https://gitlab.com/design/design-system'
  },
  {
    id: 10,
    name: 'Analytics-Dashboard',
    namespace: 'Data / Analytics',
    description: 'Real-time analytics dashboard with data visualization',
    reviewEnabled: false,
    commitsCount: 167,
    mrCount: 29,
    membersCount: 6,
    lastActivity: '2 天前',
    webhookUrl: 'https://gitlab.com/data/analytics'
  },
  {
    id: 11,
    name: 'Security-Scanner',
    namespace: 'Security / Tools',
    description: 'Automated security vulnerability scanner for code repositories',
    reviewEnabled: true,
    commitsCount: 201,
    mrCount: 36,
    membersCount: 8,
    lastActivity: '3 天前',
    webhookUrl: 'https://gitlab.com/security/scanner'
  },
  {
    id: 12,
    name: 'Notification-Service',
    namespace: 'Backend / Microservices',
    description: 'Multi-channel notification service supporting email, SMS, and webhooks',
    reviewEnabled: false,
    commitsCount: 143,
    mrCount: 22,
    membersCount: 5,
    lastActivity: '4 天前',
    webhookUrl: 'https://gitlab.com/backend/notification-service'
  }
])

const filteredProjects = computed(() => {
  if (!searchQuery.value) return projects.value

  const query = searchQuery.value.toLowerCase()
  return projects.value.filter(project =>
    project.name.toLowerCase().includes(query) ||
    project.namespace.toLowerCase().includes(query) ||
    project.description?.toLowerCase().includes(query)
  )
})

const toggleProjectReview = (projectId: number) => {
  const project = projects.value.find(p => p.id === projectId)
  if (project) {
    project.reviewEnabled = !project.reviewEnabled

    // Update stats
    if (project.reviewEnabled) {
      stats.value.activeProjects++
    } else {
      stats.value.activeProjects--
    }
  }
}

const viewProjectDetail = (projectId: number) => {
  router.push(`/projects/${projectId}`)
}

const openWebhookUrl = (url: string) => {
  window.open(url, '_blank')
}
</script>
