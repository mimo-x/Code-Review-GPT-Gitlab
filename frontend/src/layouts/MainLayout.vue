<template>
  <div class="min-h-screen bg-apple-50">
    <!-- Sidebar - Apple Style -->
    <aside
      id="hs-application-sidebar"
      class="hs-overlay [--auto-close:lg] hs-overlay-open:translate-x-0 -translate-x-full transition-all duration-300 transform fixed top-0 start-0 bottom-0 z-[60] w-72 bg-white/80 backdrop-blur-2xl border-r border-apple-200/50 lg:block lg:translate-x-0 lg:end-auto lg:bottom-0"
    >
      <div class="flex flex-col h-full">
        <!-- Logo -->
        <div class="flex items-center h-20 px-6 border-b border-apple-200/50">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-apple-blue-500 to-apple-blue-600 flex items-center justify-center shadow-lg">
              <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
              </svg>
            </div>
            <div>
              <div class="text-base font-semibold text-apple-900 tracking-tight">Code Review</div>
              <div class="text-2xs text-apple-500">AI-Powered</div>
            </div>
          </div>
        </div>

        <!-- Navigation -->
        <nav class="flex-1 px-4 py-6 overflow-y-auto">
          <ul class="space-y-1">
            <li>
              <router-link
                to="/projects"
                class="group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200"
                :class="isActiveRoute('/projects')
                  ? 'bg-apple-blue-500 text-white shadow-lg shadow-apple-blue-500/30'
                  : 'text-apple-600 hover:bg-apple-100 hover:text-apple-900'"
              >
                <FolderKanban class="w-5 h-5 transition-transform duration-200" :class="isActiveRoute('/projects') ? '' : 'group-hover:scale-110'" />
                <span>项目管理</span>
              </router-link>
            </li>
            <li>
              <router-link
                to="/reviews"
                class="group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200"
                :class="isActiveRoute('/reviews')
                  ? 'bg-apple-blue-500 text-white shadow-lg shadow-apple-blue-500/30'
                  : 'text-apple-600 hover:bg-apple-100 hover:text-apple-900'"
              >
                <FileText class="w-5 h-5 transition-transform duration-200" :class="isActiveRoute('/reviews') ? '' : 'group-hover:scale-110'" />
                <span>审查记录</span>
              </router-link>
            </li>
            <li>
              <router-link
                to="/config"
                class="group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200"
                :class="isActiveRoute('/config')
                  ? 'bg-apple-blue-500 text-white shadow-lg shadow-apple-blue-500/30'
                  : 'text-apple-600 hover:bg-apple-100 hover:text-apple-900'"
              >
                <Settings class="w-5 h-5 transition-transform duration-200" :class="isActiveRoute('/config') ? '' : 'group-hover:scale-110'" />
                <span>配置管理</span>
              </router-link>
            </li>
            <li>
              <router-link
                to="/logs"
                class="group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200"
                :class="isActiveRoute('/logs')
                  ? 'bg-apple-blue-500 text-white shadow-lg shadow-apple-blue-500/30'
                  : 'text-apple-600 hover:bg-apple-100 hover:text-apple-900'"
              >
                <ScrollText class="w-5 h-5 transition-transform duration-200" :class="isActiveRoute('/logs') ? '' : 'group-hover:scale-110'" />
                <span>日志监控</span>
              </router-link>
            </li>
            <li>
              <router-link
                to="/about"
                class="group flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200"
                :class="isActiveRoute('/about')
                  ? 'bg-apple-blue-500 text-white shadow-lg shadow-apple-blue-500/30'
                  : 'text-apple-600 hover:bg-apple-100 hover:text-apple-900'"
              >
                <Info class="w-5 h-5 transition-transform duration-200" :class="isActiveRoute('/about') ? '' : 'group-hover:scale-110'" />
                <span>项目信息</span>
              </router-link>
            </li>
          </ul>
        </nav>

        <!-- Footer -->
        <div class="p-4 border-t border-apple-200/50">
          <div class="flex items-center gap-3 px-4 py-3 rounded-xl bg-green-50">
            <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <div class="flex-1">
              <div class="text-xs font-medium text-green-700">系统运行中</div>
              <div class="text-2xs text-green-600">All systems operational</div>
            </div>
          </div>
        </div>
      </div>
    </aside>

    <!-- Content -->
    <div class="lg:ps-72">
      <!-- Header -->
      <header class="sticky top-0 z-40 bg-white/80 backdrop-blur-2xl border-b border-apple-200/50">
        <div class="flex items-center justify-between h-16 px-6">
          <div class="flex items-center gap-4">
            <!-- Mobile Menu Toggle -->
            <button
              type="button"
              class="lg:hidden p-2 text-apple-600 hover:bg-apple-100 rounded-xl transition-all duration-200 active:scale-95"
              data-hs-overlay="#hs-application-sidebar"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            <!-- Title -->
            <div>
              <h1 class="text-lg font-semibold text-apple-900 tracking-tight">{{ currentTitle }}</h1>
              <p class="text-2xs text-apple-500">{{ getCurrentTime() }}</p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <button
              @click="handleRefresh"
              class="p-2.5 text-apple-600 hover:bg-apple-100 rounded-xl transition-all duration-200 active:scale-95"
              title="刷新"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      <!-- Main Content -->
      <main class="p-6 lg:p-8">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  FileText,
  Settings,
  ScrollText,
  Info,
  FolderKanban
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

// Kept for future dynamic menu if needed
// const menuRoutes = computed(() => {
//   const routes = router.getRoutes()
//   const mainRoute = routes.find(r => r.path === '/')
//   if (!mainRoute?.children) return []
//   return mainRoute.children
//     .filter(r => !r.meta?.hidden)
//     .map(r => ({
//       ...r,
//       meta: {
//         ...r.meta,
//         icon: iconMap[r.meta?.icon as string] || FolderKanban
//       }
//     }))
// })

const currentTitle = computed(() => {
  return route.meta.title || '项目管理'
})

const isActiveRoute = (path: string) => {
  return route.path === path
}

const getCurrentTime = () => {
  const now = new Date()
  return now.toLocaleString('zh-CN', {
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const handleRefresh = () => {
  router.go(0)
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
