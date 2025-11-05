<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-bold text-gray-900">项目信息</h2>

    <!-- System Info -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="card">
        <div class="p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-lg font-semibold text-gray-800">系统信息</h3>
            <span class="badge-success">运行中</span>
          </div>

          <dl class="space-y-3">
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600">项目名称</dt>
              <dd class="text-sm font-medium text-gray-900">Code Review GPT</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600">版本</dt>
              <dd class="text-sm font-medium text-gray-900">v1.0.0</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-600">Python 版本</dt>
              <dd class="text-sm font-medium text-gray-900">3.9.18</dd>
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
import { ref } from 'vue'
import { Zap, GitBranch, Bell, Settings } from 'lucide-vue-next'

const systemInfo = ref({
  uptime: '5天 12小时 35分钟',
  cpu: 45,
  memory: 62,
  memoryUsed: '2.4 GB',
  memoryTotal: '4 GB'
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
