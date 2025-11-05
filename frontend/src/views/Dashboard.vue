<template>
  <div class="space-y-8">
    <!-- Stats Cards - Apple Minimalist Style -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="stat-card group">
        <div class="relative z-10 flex flex-col">
          <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">今日审查</div>
          <div class="text-4xl font-bold text-apple-900 mb-1 tracking-tight">{{ stats.todayReviews }}</div>
          <div class="flex items-center gap-1 text-2xs text-green-600">
            <TrendingUp class="w-3 h-3" />
            <span>较昨日 +{{stats.todayGrowth }}%</span>
          </div>
        </div>
        <BarChart3 class="absolute bottom-4 right-4 w-12 h-12 text-apple-300/30 group-hover:text-apple-blue-500/20 transition-colors duration-300" />
      </div>

      <div class="stat-card group">
        <div class="relative z-10 flex flex-col">
          <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">本周审查</div>
          <div class="text-4xl font-bold text-apple-900 mb-1 tracking-tight">{{ stats.weekReviews }}</div>
          <div class="flex items-center gap-1 text-2xs text-apple-600">
            <Calendar class="w-3 h-3" />
            <span>累计审查次数</span>
          </div>
        </div>
        <Activity class="absolute bottom-4 right-4 w-12 h-12 text-apple-300/30 group-hover:text-purple-500/20 transition-colors duration-300" />
      </div>

      <div class="stat-card group">
        <div class="relative z-10 flex flex-col">
          <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">LLM 调用</div>
          <div class="text-4xl font-bold text-apple-900 mb-1 tracking-tight">{{ stats.llmCalls }}</div>
          <div class="flex items-center gap-1 text-2xs text-apple-600">
            <Zap class="w-3 h-3" />
            <span>今日API调用</span>
          </div>
        </div>
        <MessageSquare class="absolute bottom-4 right-4 w-12 h-12 text-apple-300/30 group-hover:text-orange-500/20 transition-colors duration-300" />
      </div>

      <div class="stat-card group">
        <div class="relative z-10 flex flex-col">
          <div class="text-xs font-medium text-apple-600 mb-2 uppercase tracking-wide">成功率</div>
          <div class="text-4xl font-bold text-apple-900 mb-1 tracking-tight">{{ stats.successRate }}%</div>
          <div class="flex items-center gap-1 text-2xs text-green-600">
            <CheckCircle class="w-3 h-3" />
            <span>审查成功率</span>
          </div>
        </div>
        <Target class="absolute bottom-4 right-4 w-12 h-12 text-apple-300/30 group-hover:text-green-500/20 transition-colors duration-300" />
      </div>
    </div>

    <!-- Charts Row -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Trend Chart -->
      <div class="lg:col-span-2 card">
        <div class="p-6">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h3 class="section-header">审查趋势</h3>
              <p class="text-xs text-apple-500 mt-1">Review trends analysis</p>
            </div>
            <div class="flex gap-2">
              <button
                @click="chartType = 'week'"
                :class="[
                  'px-4 py-2 text-xs font-medium rounded-full transition-all duration-200',
                  chartType === 'week'
                    ? 'bg-apple-900 text-white'
                    : 'bg-apple-100 text-apple-700 hover:bg-apple-200'
                ]"
              >
                近7天
              </button>
              <button
                @click="chartType = 'month'"
                :class="[
                  'px-4 py-2 text-xs font-medium rounded-full transition-all duration-200',
                  chartType === 'month'
                    ? 'bg-apple-900 text-white'
                    : 'bg-apple-100 text-apple-700 hover:bg-apple-200'
                ]"
              >
                近30天
              </button>
            </div>
          </div>
          <div ref="chartRef" class="h-80"></div>
        </div>
      </div>

      <!-- Recent Activities -->
      <div class="card">
        <div class="p-6">
          <div class="mb-6">
            <h3 class="section-header">最近活动</h3>
            <p class="text-xs text-apple-500 mt-1">Recent activity log</p>
          </div>
          <div class="space-y-4">
            <div
              v-for="(activity, index) in recentActivities"
              :key="index"
              class="flex gap-3 group"
            >
              <div class="flex-shrink-0 mt-1">
                <div
                  :class="[
                    'w-2 h-2 rounded-full',
                    getActivityColor(activity.type)
                  ]"
                ></div>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-apple-900 group-hover:text-apple-blue-600 transition-colors">{{ activity.title }}</p>
                <p class="text-xs text-apple-500 mt-0.5">{{ activity.desc }}</p>
                <p class="text-2xs text-apple-400 mt-1">{{ activity.time }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Charts -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Model Distribution -->
      <div class="card">
        <div class="p-6">
          <div class="mb-6">
            <h3 class="section-header">LLM 模型分布</h3>
            <p class="text-xs text-apple-500 mt-1">Model usage distribution</p>
          </div>
          <div ref="pieChartRef" class="h-72"></div>
        </div>
      </div>

      <!-- Issue Categories -->
      <div class="card">
        <div class="p-6">
          <div class="mb-6">
            <h3 class="section-header">审查问题分类</h3>
            <p class="text-xs text-apple-500 mt-1">Issue categories breakdown</p>
          </div>
          <div ref="categoryChartRef" class="h-72"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import {
  TrendingUp,
  Calendar,
  Zap,
  CheckCircle,
  BarChart3,
  Activity,
  MessageSquare,
  Target
} from 'lucide-vue-next'

const stats = ref({
  todayReviews: 24,
  todayGrowth: 12,
  weekReviews: 156,
  llmCalls: 487,
  successRate: 98.5
})

const chartType = ref('week')
const chartRef = ref<HTMLElement>()
const pieChartRef = ref<HTMLElement>()
const categoryChartRef = ref<HTMLElement>()

const recentActivities = ref([
  {
    title: 'MR #123 审查完成',
    desc: 'feature/new-dashboard 合并请求',
    time: '2 分钟前',
    type: 'success'
  },
  {
    title: 'LLM 配置更新',
    desc: '切换到 GPT-4 模型',
    time: '15 分钟前',
    type: 'primary'
  },
  {
    title: 'MR #122 审查完成',
    desc: 'fix/user-auth 合并请求',
    time: '1 小时前',
    type: 'success'
  },
  {
    title: '钉钉通知发送',
    desc: '发送审查报告到开发群',
    time: '2 小时前',
    type: 'info'
  }
])

const getActivityColor = (type: string) => {
  const colorMap: Record<string, string> = {
    success: 'bg-green-500',
    primary: 'bg-apple-blue-500',
    info: 'bg-apple-400',
    warning: 'bg-orange-500'
  }
  return colorMap[type] || 'bg-apple-400'
}

const initLineChart = () => {
  if (!chartRef.value) return

  const chart = echarts.init(chartRef.value)
  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e8e8ed',
      borderWidth: 1,
      textStyle: { color: '#1d1d1f', fontSize: 12 },
      padding: 12,
      borderRadius: 12,
      shadowBlur: 20,
      shadowColor: 'rgba(0, 0, 0, 0.1)'
    },
    legend: {
      data: ['审查次数', 'LLM调用'],
      bottom: 0,
      itemGap: 20,
      textStyle: { color: '#86868b', fontSize: 12 }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '12%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: { lineStyle: { color: '#e8e8ed', width: 1 } },
      axisLabel: { color: '#86868b', fontSize: 11 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#86868b', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f5f5f7', type: 'dashed' } }
    },
    series: [
      {
        name: '审查次数',
        type: 'line',
        smooth: true,
        data: [12, 18, 15, 22, 28, 19, 24],
        lineStyle: { color: '#007aff', width: 3 },
        itemStyle: { color: '#007aff' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 122, 255, 0.2)' },
            { offset: 1, color: 'rgba(0, 122, 255, 0)' }
          ])
        }
      },
      {
        name: 'LLM调用',
        type: 'line',
        smooth: true,
        data: [45, 67, 58, 82, 95, 71, 87],
        lineStyle: { color: '#34c759', width: 3 },
        itemStyle: { color: '#34c759' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(52, 199, 89, 0.2)' },
            { offset: 1, color: 'rgba(52, 199, 89, 0)' }
          ])
        }
      }
    ]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

const initPieChart = () => {
  if (!pieChartRef.value) return

  const chart = echarts.init(pieChartRef.value)
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
      textStyle: { color: '#86868b', fontSize: 12 }
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 3
        },
        label: { show: false },
        labelLine: { show: false },
        data: [
          { value: 335, name: 'GPT-4', itemStyle: { color: '#007aff' } },
          { value: 234, name: 'DeepSeek', itemStyle: { color: '#34c759' } },
          { value: 154, name: 'Claude', itemStyle: { color: '#af52de' } },
          { value: 89, name: 'Gemini', itemStyle: { color: '#ff9500' } }
        ]
      }
    ]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

const initCategoryChart = () => {
  if (!categoryChartRef.value) return

  const chart = echarts.init(categoryChartRef.value)
  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
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
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: ['代码质量', '安全问题', '性能优化', '代码规范', '逻辑错误'],
      axisLine: { lineStyle: { color: '#e8e8ed' } },
      axisLabel: { color: '#86868b', interval: 0, fontSize: 11 },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#86868b', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f5f5f7', type: 'dashed' } }
    },
    series: [
      {
        type: 'bar',
        data: [
          { value: 45, itemStyle: { color: '#007aff' } },
          { value: 28, itemStyle: { color: '#ff3b30' } },
          { value: 32, itemStyle: { color: '#34c759' } },
          { value: 38, itemStyle: { color: '#ff9500' } },
          { value: 19, itemStyle: { color: '#af52de' } }
        ],
        barWidth: '50%',
        itemStyle: {
          borderRadius: [8, 8, 0, 0]
        }
      }
    ]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

onMounted(() => {
  initLineChart()
  initPieChart()
  initCategoryChart()
})

watch(chartType, () => {
  initLineChart()
})
</script>
