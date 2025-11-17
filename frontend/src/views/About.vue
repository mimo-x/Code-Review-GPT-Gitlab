<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-bold text-gray-900">项目信息</h2>

    <!-- System Info -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="card">
        <div class="p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-lg font-semibold text-gray-800">系统信息</h3>
            <span :class="systemInfo.serverStatus === 'running' ? 'badge-success' : 'badge-error'">
              {{ systemInfo.serverStatus === 'running' ? '运行中' : '离线' }}
            </span>
          </div>

          <dl class="space-y-3">
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600">项目名称</dt>
              <dd class="text-sm font-medium text-gray-900">{{ systemInfo.projectName }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600">版本</dt>
              <dd class="text-sm font-medium text-gray-900">{{ systemInfo.projectVersion }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600">Python 版本</dt>
              <dd class="text-sm font-medium text-gray-900">{{ systemInfo.pythonVersion }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600">Django 版本</dt>
              <dd class="text-sm font-medium text-gray-900">{{ systemInfo.djangoVersion }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600">运行时间</dt>
              <dd class="text-sm font-medium text-gray-900">{{ systemInfo.uptime }}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div class="card">
        <div class="p-6">
          <h3 class="text-lg font-semibold text-gray-800 mb-6">资源使用</h3>

          <div class="space-y-4">
            <div>
              <div class="flex justify-between mb-2">
                <span class="text-sm text-gray-600">CPU 使用率</span>
                <span class="text-sm font-medium">{{ systemInfo.cpu }}%</span>
              </div>
              <div class="w-full bg-gray-200 rounded-full h-2">
                <div :style="`width: ${systemInfo.cpu}%`" class="bg-blue-600 h-2 rounded-full"></div>
              </div>
            </div>

            <div>
              <div class="flex justify-between mb-2">
                <span class="text-sm text-gray-600">内存使用</span>
                <span class="text-sm font-medium">{{ systemInfo.memoryUsed }} / {{ systemInfo.memoryTotal }}</span>
              </div>
              <div class="w-full bg-gray-200 rounded-full h-2">
                <div :style="`width: ${systemInfo.memory}%`" class="bg-green-600 h-2 rounded-full"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Features -->
    <div class="card">
      <div class="p-6">
        <h3 class="text-lg font-semibold text-gray-800 mb-6">功能特性</h3>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div class="text-center p-4 bg-gray-50 rounded-lg">
            <Zap class="w-10 h-10 mx-auto text-blue-600 mb-3" />
            <h4 class="font-semibold text-gray-900 mb-2">智能审查</h4>
            <p class="text-sm text-gray-600">基于LLM的智能代码审查</p>
          </div>

          <div class="text-center p-4 bg-gray-50 rounded-lg">
            <GitBranch class="w-10 h-10 mx-auto text-green-600 mb-3" />
            <h4 class="font-semibold text-gray-900 mb-2">GitLab 集成</h4>
            <p class="text-sm text-gray-600">无缝集成GitLab Webhook</p>
          </div>

          <div class="text-center p-4 bg-gray-50 rounded-lg">
            <Bell class="w-10 h-10 mx-auto text-orange-600 mb-3" />
            <h4 class="font-semibold text-gray-900 mb-2">多渠道通知</h4>
            <p class="text-sm text-gray-600">支持钉钉、GitLab评论</p>
          </div>

          <div class="text-center p-4 bg-gray-50 rounded-lg">
            <Settings class="w-10 h-10 mx-auto text-purple-600 mb-3" />
            <h4 class="font-semibold text-gray-900 mb-2">灵活配置</h4>
            <p class="text-sm text-gray-600">可定制审查规则</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Tech Stack -->
    <div class="card">
      <div class="p-6">
        <h3 class="text-lg font-semibold text-gray-800 mb-6">技术栈</h3>

        <div class="flex flex-wrap gap-2">
          <span v-for="tech in techStack" :key="tech.name" class="badge-info">
            {{ tech.name }} {{ tech.version }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Zap, GitBranch, Bell, Settings } from 'lucide-vue-next'
import { getSystemInfo } from '@/api'

const systemInfo = ref({
  uptime: '加载中...',
  cpu: 0,
  memory: 0,
  memoryUsed: '0 GB',
  memoryTotal: '0 GB',
  projectName: 'Code Review GPT',
  projectVersion: '加载中...',
  pythonVersion: '加载中...',
  djangoVersion: '加载中...',
  osInfo: '加载中...',
  serverStatus: 'running'
})

// 获取系统信息
const fetchSystemInfo = async () => {
  try {
    const response = await getSystemInfo()
    const data = response.data || response
    if (data.status === 'ok') {
      systemInfo.value = {
        uptime: data.uptime,
        cpu: data.cpu,
        memory: data.memory,
        memoryUsed: data.memoryUsed,
        memoryTotal: data.memoryTotal,
        projectName: data.projectName,
        projectVersion: data.projectVersion,
        pythonVersion: data.pythonVersion,
        djangoVersion: data.djangoVersion,
        osInfo: data.osInfo,
        serverStatus: data.serverStatus
      }
    }
  } catch (error) {
    console.error('获取系统信息失败:', error)
    systemInfo.value.serverStatus = 'offline'
  }
}

// 组件挂载时获取数据
onMounted(() => {
  fetchSystemInfo()
  // 每30秒更新一次系统信息
  setInterval(fetchSystemInfo, 30000)
})

const techStack = ref([
  { name: 'Python', version: '3.9+' },
  { name: 'Flask', version: '2.3.2' },
  { name: 'UnionLLM', version: '0.1.23' },
  { name: 'Vue', version: '3.4' },
  { name: 'Tailwind CSS', version: '3.4' },
  { name: 'Preline', version: '2.0' },
  { name: 'ECharts', version: '5.4' }
])
</script>
