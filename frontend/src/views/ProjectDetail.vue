<template>
  <div class="space-y-6">
    <!-- Header with Back Button -->
    <div class="flex items-center gap-4">
      <button
        @click="goBack"
        class="btn-ghost"
      >
        <ArrowLeft class="w-4 h-4" />
        <span>返回</span>
      </button>
      <div class="flex-1">
        <h1 class="section-header">{{ project?.name }}</h1>
        <p class="text-xs text-apple-500 mt-1">{{ project?.namespace }}</p>
      </div>
      <span
        :class="[
          'badge',
          project?.reviewEnabled ? 'badge-success' : 'bg-apple-200 text-apple-700'
        ]"
      >
        {{ project?.reviewEnabled ? '审查已开启' : '审查已关闭' }}
      </span>
    </div>

    <!-- Project Overview -->
    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <div class="lg:col-span-3 space-y-6">
        <!-- Basic Information -->
        <div class="card">
          <div class="p-6">
            <h3 class="section-header mb-4">项目信息</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div class="space-y-4">
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">项目名称</div>
                  <div class="text-sm text-apple-900">{{ project?.name }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">命名空间</div>
                  <div class="text-sm text-apple-900">{{ project?.namespace }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">Webhook URL</div>
                  <div class="flex items-center gap-2">
                    <span class="text-sm text-apple-blue-600 truncate">{{ project?.webhookUrl }}</span>
                    <button
                      @click="openWebhookUrl(project?.webhookUrl)"
                      class="flex-shrink-0 text-apple-600 hover:text-apple-blue-600 transition-colors"
                    >
                      <ExternalLink class="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              <div class="space-y-4">
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">创建时间</div>
                  <div class="text-sm text-apple-900">{{ project?.createdAt }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">最后活动</div>
                  <div class="text-sm text-apple-900">{{ project?.lastActivity }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">团队成员</div>
                  <div class="flex items-center gap-2">
                    <Users class="w-4 h-4 text-apple-600" />
                    <span class="text-sm text-apple-900">{{ project?.membersCount }} 成员</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-6 pt-6 border-t border-apple-200/50">
              <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">项目描述</div>
              <p class="text-sm text-apple-700">{{ project?.description || '暂无项目描述' }}</p>
            </div>
          </div>
        </div>

        <!-- Statistics Charts -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="card">
            <div class="p-6">
              <h3 class="section-header mb-4">审查统计</h3>
              <div ref="reviewChartRef" class="h-64"></div>
            </div>
          </div>

          <div class="card">
            <div class="p-6">
              <h3 class="section-header mb-4">问题分布</h3>
              <div ref="issueChartRef" class="h-64"></div>
            </div>
          </div>
        </div>

        <!-- Recent Events -->
        <div class="card">
          <div class="p-6">
            <h3 class="section-header mb-4">最近事件</h3>
            <div class="space-y-4">
              <div
                v-for="(event, index) in recentEvents"
                :key="index"
                class="flex gap-4 p-4 rounded-xl bg-apple-50 hover:bg-apple-100 transition-colors duration-200"
              >
                <div class="flex-shrink-0">
                  <div
                    :class="[
                      'w-10 h-10 rounded-xl flex items-center justify-center',
                      getEventBgColor(event.type)
                    ]"
                  >
                    <component
                      :is="getEventIcon(event.type)"
                      class="w-5 h-5 text-white"
                    />
                  </div>
                </div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex-1">
                      <h4 class="text-sm font-semibold text-apple-900">{{ event.title }}</h4>
                      <p class="text-xs text-apple-600 mt-0.5">{{ event.description }}</p>
                    </div>
                    <span class="text-2xs text-apple-500 flex-shrink-0">{{ event.time }}</span>
                  </div>
                  <div class="flex items-center gap-3 mt-2">
                    <div class="flex items-center gap-1.5 text-2xs text-apple-600">
                      <User class="w-3 h-3" />
                      <span>{{ event.author }}</span>
                    </div>
                    <div class="flex items-center gap-1.5 text-2xs text-apple-600">
                      <GitBranch class="w-3 h-3" />
                      <span>{{ event.branch }}</span>
                    </div>
                    <span
                      :class="[
                        'badge',
                        getEventBadgeClass(event.status)
                      ]"
                    >
                      {{ event.status }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Sidebar -->
      <div class="space-y-6">
        <!-- Quick Stats -->
        <div class="card">
          <div class="p-6 space-y-4">
            <h3 class="section-header mb-4">项目统计</h3>

            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <GitCommit class="w-4 h-4" />
                  <span>总提交数</span>
                </div>
                <span class="text-sm font-semibold text-apple-900">{{ project?.commitsCount }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <GitPullRequest class="w-4 h-4" />
                  <span>合并请求</span>
                </div>
                <span class="text-sm font-semibold text-apple-900">{{ project?.mrCount }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <CheckCircle2 class="w-4 h-4" />
                  <span>审查完成</span>
                </div>
                <span class="text-sm font-semibold text-green-600">{{ projectStats.reviewsCompleted }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <AlertCircle class="w-4 h-4" />
                  <span>发现问题</span>
                </div>
                <span class="text-sm font-semibold text-orange-600">{{ projectStats.issuesFound }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <TrendingUp class="w-4 h-4" />
                  <span>审查成功率</span>
                </div>
                <span class="text-sm font-semibold text-apple-blue-600">{{ projectStats.successRate }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Contributors -->
        <div class="card">
          <div class="p-6">
            <h3 class="section-header mb-4">活跃贡献者</h3>
            <div class="space-y-3">
              <div
                v-for="(contributor, index) in topContributors"
                :key="index"
                class="flex items-center gap-3 p-3 rounded-xl hover:bg-apple-50 transition-colors duration-200"
              >
                <div class="w-8 h-8 rounded-full bg-gradient-to-br from-apple-blue-500 to-apple-blue-600 flex items-center justify-center text-white text-xs font-semibold">
                  {{ contributor.initials }}
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-xs font-medium text-apple-900">{{ contributor.name }}</div>
                  <div class="text-2xs text-apple-500">{{ contributor.commits }} commits</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="card">
          <div class="p-6 space-y-3">
            <button
              @click="toggleReview"
              class="btn-primary w-full"
            >
              <Power class="w-4 h-4" />
              <span>{{ project?.reviewEnabled ? '关闭审查' : '开启审查' }}</span>
            </button>
            <button
              @click="openWebhookUrl(project?.webhookUrl)"
              class="btn-secondary w-full"
            >
              <ExternalLink class="w-4 h-4" />
              <span>查看 GitLab</span>
            </button>
            <button class="btn-ghost w-full">
              <Settings class="w-4 h-4" />
              <span>项目配置</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import {
  ArrowLeft,
  ExternalLink,
  Users,
  GitCommit,
  GitPullRequest,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Power,
  Settings,
  User,
  GitBranch,
  FileCheck,
  AlertTriangle,
  XCircle
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const reviewChartRef = ref<HTMLElement>()
const issueChartRef = ref<HTMLElement>()

const project = ref({
  id: 1,
  name: 'Code-Review-GPT-Gitlab',
  namespace: 'DevOps / AI Tools',
  description: 'AI-powered code review tool for GitLab merge requests using LLM models',
  reviewEnabled: true,
  commitsCount: 324,
  mrCount: 45,
  membersCount: 8,
  lastActivity: '2 分钟前',
  webhookUrl: 'https://gitlab.com/devops/code-review-gpt',
  createdAt: '2024-01-15'
})

const projectStats = ref({
  reviewsCompleted: 145,
  issuesFound: 267,
  successRate: 96.5
})

const recentEvents = ref([
  {
    type: 'merge',
    title: 'Merge Request #123 已审查',
    description: 'feat: Add project management module',
    author: '张三',
    branch: 'feature/project-manage',
    status: '通过',
    time: '2 分钟前'
  },
  {
    type: 'commit',
    title: '新的提交已推送',
    description: 'fix: Resolve authentication bug',
    author: '李四',
    branch: 'fix/auth-bug',
    status: '待审查',
    time: '15 分钟前'
  },
  {
    type: 'issue',
    title: '发现代码问题',
    description: '检测到潜在的安全漏洞',
    author: '王五',
    branch: 'develop',
    status: '警告',
    time: '1 小时前'
  },
  {
    type: 'merge',
    title: 'Merge Request #122 已审查',
    description: 'refactor: Improve error handling',
    author: '赵六',
    branch: 'refactor/error-handling',
    status: '通过',
    time: '3 小时前'
  },
  {
    type: 'error',
    title: '审查失败',
    description: 'LLM API 调用超时',
    author: '钱七',
    branch: 'feature/new-feature',
    status: '失败',
    time: '5 小时前'
  }
])

const topContributors = ref([
  { name: '张三', initials: 'ZS', commits: 142 },
  { name: '李四', initials: 'LS', commits: 98 },
  { name: '王五', initials: 'WW', commits: 76 },
  { name: '赵六', initials: 'ZL', commits: 54 }
])

const getEventIcon = (type: string) => {
  const iconMap: Record<string, any> = {
    merge: FileCheck,
    commit: GitCommit,
    issue: AlertTriangle,
    error: XCircle
  }
  return iconMap[type] || GitCommit
}

const getEventBgColor = (type: string) => {
  const colorMap: Record<string, string> = {
    merge: 'bg-green-500',
    commit: 'bg-apple-blue-500',
    issue: 'bg-orange-500',
    error: 'bg-red-500'
  }
  return colorMap[type] || 'bg-apple-400'
}

const getEventBadgeClass = (status: string) => {
  const classMap: Record<string, string> = {
    '通过': 'badge-success',
    '待审查': 'badge-info',
    '警告': 'badge-warning',
    '失败': 'badge-danger'
  }
  return classMap[status] || 'bg-apple-200 text-apple-700'
}

const initReviewChart = () => {
  if (!reviewChartRef.value) return

  const chart = echarts.init(reviewChartRef.value)
  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e8e8ed',
      borderWidth: 1,
      textStyle: { color: '#1d1d1f', fontSize: 12 },
      padding: 12,
      borderRadius: 12
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: { lineStyle: { color: '#e8e8ed' } },
      axisLabel: { color: '#86868b', fontSize: 10 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#86868b', fontSize: 10 },
      splitLine: { lineStyle: { color: '#f5f5f7', type: 'dashed' } }
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: [12, 18, 15, 22, 28, 19, 24],
        lineStyle: { color: '#007aff', width: 2 },
        itemStyle: { color: '#007aff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 122, 255, 0.2)' },
            { offset: 1, color: 'rgba(0, 122, 255, 0)' }
          ])
        }
      }
    ]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

const initIssueChart = () => {
  if (!issueChartRef.value) return

  const chart = echarts.init(issueChartRef.value)
  const option: EChartsOption = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e8e8ed',
      borderWidth: 1,
      textStyle: { color: '#1d1d1f', fontSize: 12 },
      padding: 12,
      borderRadius: 12
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: '#86868b', fontSize: 11 }
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false },
        labelLine: { show: false },
        data: [
          { value: 45, name: '代码质量', itemStyle: { color: '#007aff' } },
          { value: 28, name: '安全问题', itemStyle: { color: '#ff3b30' } },
          { value: 32, name: '性能优化', itemStyle: { color: '#34c759' } },
          { value: 19, name: '代码规范', itemStyle: { color: '#ff9500' } }
        ]
      }
    ]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

const goBack = () => {
  router.push('/projects')
}

const toggleReview = () => {
  if (project.value) {
    project.value.reviewEnabled = !project.value.reviewEnabled
  }
}

const openWebhookUrl = (url?: string) => {
  if (url) {
    window.open(url, '_blank')
  }
}

onMounted(() => {
  initReviewChart()
  initIssueChart()
})
</script>
