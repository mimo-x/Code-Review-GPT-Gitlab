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
        <h1 class="section-header">{{ project?.project_name }}</h1>
        <p class="text-xs text-apple-500 mt-1">{{ project?.namespace }}</p>
      </div>
      <span
        :class="[
          'badge',
          project?.review_enabled ? 'badge-success' : 'bg-apple-200 text-apple-700'
        ]"
      >
        {{ project?.review_enabled ? '审查已开启' : '审查已关闭' }}
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
                  <div class="text-sm text-apple-900">{{ project?.project_name }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">命名空间</div>
                  <div class="text-sm text-apple-900">{{ project?.namespace }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">Webhook URL</div>
                  <div class="flex items-center gap-2">
                    <span class="text-sm text-apple-blue-600 truncate">{{ project?.webhook_url }}</span>
                    <button
                      @click="openWebhookUrl(project?.webhook_url)"
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
                  <div class="text-sm text-apple-900">{{ project?.created_at ? new Date(project.created_at).toLocaleDateString() : '未知' }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">最后活动</div>
                  <div class="text-sm text-apple-900">{{ project?.last_activity || '未知' }}</div>
                </div>
                <div>
                  <div class="text-xs font-medium text-apple-600 mb-1 uppercase tracking-wide">团队成员</div>
                  <div class="flex items-center gap-2">
                    <Users class="w-4 h-4 text-apple-600" />
                    <span class="text-sm text-apple-900">{{ project?.members_count || 0 }} 成员</span>
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
                <span class="text-sm font-semibold text-apple-900">{{ project?.commits_count || 0 }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <GitPullRequest class="w-4 h-4" />
                  <span>合并请求</span>
                </div>
                <span class="text-sm font-semibold text-apple-900">{{ project?.mr_count || 0 }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <CheckCircle2 class="w-4 h-4" />
                  <span>审查完成</span>
                </div>
                <span class="text-sm font-semibold text-green-600">{{ projectStats?.reviews?.completed || 0 }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <AlertCircle class="w-4 h-4" />
                  <span>本周审查</span>
                </div>
                <span class="text-sm font-semibold text-orange-600">{{ projectStats?.reviews?.weekly || 0 }}</span>
              </div>

              <div class="divider"></div>

              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs text-apple-600">
                  <TrendingUp class="w-4 h-4" />
                  <span>审查成功率</span>
                </div>
                <span class="text-sm font-semibold text-apple-blue-600">{{ projectStats?.reviews?.completion_rate?.toFixed(1) || 0 }}%</span>
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
              :disabled="loading"
              class="btn-primary w-full"
            >
              <Power class="w-4 h-4" />
              <span>{{ project?.review_enabled ? '关闭审查' : '开启审查' }}</span>
            </button>
            <button
              @click="openWebhookUrl(project?.webhook_url)"
              class="btn-secondary w-full"
            >
              <ExternalLink class="w-4 h-4" />
              <span>查看 GitLab</span>
            </button>
            <button
              @click="refreshData"
              :disabled="loading"
              class="btn-ghost w-full"
            >
              <Settings class="w-4 h-4" />
              <span>{{ loading ? '刷新中...' : '刷新数据' }}</span>
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
import {
  getProjectDetail,
  getProjectWebhookLogs,
  getProjectReviewHistory,
  enableProjectReview,
  disableProjectReview
} from '@/api'

const route = useRoute()
const router = useRouter()

const reviewChartRef = ref<HTMLElement>()
const issueChartRef = ref<HTMLElement>()
const loading = ref(false)

const project = ref<any>(null)
const projectStats = ref<any>(null)
const recentEvents = ref<any[]>([])
const topContributors = ref<any[]>([])

const loadProjectDetail = async () => {
  try {
    loading.value = true
    const projectId = route.params.id as string
    const response = await getProjectDetail(projectId)

    if (response.data && response.data.project) {
      project.value = response.data.project
      projectStats.value = response.data.stats
    }
  } catch (error) {
    console.error('Failed to load project detail:', error)
    alert('加载项目详情失败')
  } finally {
    loading.value = false
  }
}

const loadRecentEvents = async () => {
  try {
    const projectId = route.params.id as string
    const response = await getProjectWebhookLogs(projectId, { limit: 10 })

    if (response.data && response.data.logs) {
      recentEvents.value = response.data.logs.map((log: any) => ({
        type: log.event_type,
        title: getEventTitle(log.event_type, log.merge_request_iid),
        description: getEventDescription(log.event_type, log.object_attributes),
        author: log.user_name,
        branch: log.source_branch || log.target_branch,
        status: getEventStatus(log.event_type, log.processed),
        time: formatTimeAgo(log.created_at)
      }))
    }
  } catch (error) {
    console.error('Failed to load recent events:', error)
  }
}

const loadReviewHistory = async () => {
  try {
    const projectId = route.params.id as string
    const response = await getProjectReviewHistory(projectId, { limit: 20, days: 30 })

    if (response.data && response.data.reviews) {
      // Process review history to create charts data
      processReviewData(response.data.reviews)
    }
  } catch (error) {
    console.error('Failed to load review history:', error)
  }
}

const getEventTitle = (eventType: string, mrIid?: number) => {
  const titleMap: Record<string, string> = {
    'merge_request': `Merge Request #${mrIid} 已审查`,
    'push': '新的提交已推送',
    'issue': '发现代码问题',
    'note': '新增评论'
  }
  return titleMap[eventType] || '未知事件'
}

const getEventDescription = (eventType: string, objectAttributes?: any) => {
  if (eventType === 'merge_request' && objectAttributes) {
    return objectAttributes.title || '合并请求'
  }
  if (eventType === 'push' && objectAttributes) {
    return objectAttributes.message || '代码提交'
  }
  return '事件描述'
}

const getEventStatus = (eventType: string, processed: boolean) => {
  if (!processed) return '处理中'

  const statusMap: Record<string, string> = {
    'merge_request': '通过',
    'push': '已推送',
    'issue': '警告',
    'note': '已评论'
  }
  return statusMap[eventType] || '完成'
}

const formatTimeAgo = (timestamp: string) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 30) return `${days} 天前`

  return date.toLocaleDateString()
}

const processReviewData = (reviews: any[]) => {
  // Process reviews to create charts data
  const dailyStats: Record<string, number> = {}
  const issueTypes: Record<string, number> = {}

  reviews.forEach(review => {
    const date = new Date(review.created_at).toLocaleDateString()
    dailyStats[date] = (dailyStats[date] || 0) + 1

    // Analyze review content for issue types
    if (review.review_content) {
      const content = review.review_content.toLowerCase()
      if (content.includes('security') || content.includes('安全')) {
        issueTypes['安全问题'] = (issueTypes['安全问题'] || 0) + 1
      } else if (content.includes('performance') || content.includes('性能')) {
        issueTypes['性能优化'] = (issueTypes['性能优化'] || 0) + 1
      } else if (content.includes('style') || content.includes('规范')) {
        issueTypes['代码规范'] = (issueTypes['代码规范'] || 0) + 1
      } else {
        issueTypes['代码质量'] = (issueTypes['代码质量'] || 0) + 1
      }
    }
  })

  // Update charts with real data
  updateChartsWithData(dailyStats, issueTypes)
}

const updateChartsWithData = (dailyStats: Record<string, number>, issueTypes: Record<string, number>) => {
  // This will be called after data is loaded to update charts
  // Implementation depends on chart initialization
}

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

const toggleReview = async () => {
  if (!project.value) return

  try {
    const projectId = project.value.project_id
    const originalStatus = project.value.review_enabled
    project.value.review_enabled = !originalStatus

    try {
      if (project.value.review_enabled) {
        await enableProjectReview(projectId.toString())
        alert('已启用代码审查')
      } else {
        await disableProjectReview(projectId.toString())
        alert('已禁用代码审查')
      }
    } catch (apiError) {
      // Revert on API error
      project.value.review_enabled = originalStatus
      throw apiError
    }
  } catch (error) {
    console.error('Failed to toggle review:', error)
    alert('操作失败，请重试')
  }
}

const openWebhookUrl = (url?: string) => {
  if (url) {
    window.open(url, '_blank')
  }
}

const refreshData = async () => {
  await Promise.all([
    loadProjectDetail(),
    loadRecentEvents(),
    loadReviewHistory()
  ])
}

onMounted(() => {
  refreshData()
})
</script>
