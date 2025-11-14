/**
 * Toast notification utility
 * 使用Preline UI风格的轻量级提示
 */

export type ToastType = 'success' | 'error' | 'warning' | 'info'

interface ToastOptions {
  message: string
  type?: ToastType
  duration?: number
}

const icons = {
  success: `<svg class="flex-shrink-0 w-4 h-4 text-green-500" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path><path d="m9 12 2 2 4-4"></path></svg>`,
  error: `<svg class="flex-shrink-0 w-4 h-4 text-red-500" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path><path d="m15 9-6 6"></path><path d="m9 9 6 6"></path></svg>`,
  warning: `<svg class="flex-shrink-0 w-4 h-4 text-yellow-500" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><path d="M12 9v4"></path><path d="M12 17h.01"></path></svg>`,
  info: `<svg class="flex-shrink-0 w-4 h-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg>`
}

const colorClasses = {
  success: 'bg-white border-green-200 text-gray-800',
  error: 'bg-white border-red-200 text-gray-800',
  warning: 'bg-white border-yellow-200 text-gray-800',
  info: 'bg-white border-blue-200 text-gray-800'
}

export function showToast({ message, type = 'info', duration = 3000 }: ToastOptions) {
  // 创建toast容器（如果不存在）
  let container = document.getElementById('toast-container')
  if (!container) {
    container = document.createElement('div')
    container.id = 'toast-container'
    container.className = 'fixed top-4 right-4 z-[100] space-y-3'
    document.body.appendChild(container)
  }

  // 创建toast元素
  const toast = document.createElement('div')
  toast.className = `${colorClasses[type]} max-w-xs border shadow-lg rounded-xl pointer-events-auto transition-all duration-300 ease-out transform translate-x-0 opacity-100`
  toast.style.animation = 'slideInRight 0.3s ease-out'

  toast.innerHTML = `
    <div class="flex p-4">
      <div class="flex-shrink-0">
        ${icons[type]}
      </div>
      <div class="ms-3">
        <p class="text-sm font-medium">${message}</p>
      </div>
      <div class="ms-auto">
        <button type="button" class="inline-flex flex-shrink-0 justify-center items-center h-5 w-5 rounded-lg text-gray-400 hover:text-gray-500 focus:outline-none" data-toast-close>
          <span class="sr-only">Close</span>
          <svg class="flex-shrink-0 w-4 h-4" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>
        </button>
      </div>
    </div>
  `

  // 添加关闭按钮事件
  const closeButton = toast.querySelector('[data-toast-close]')
  closeButton?.addEventListener('click', () => removeToast(toast))

  // 添加到容器
  container.appendChild(toast)

  // 自动移除
  if (duration > 0) {
    setTimeout(() => removeToast(toast), duration)
  }

  return toast
}

function removeToast(toast: HTMLElement) {
  toast.style.animation = 'slideOutRight 0.3s ease-out'
  setTimeout(() => {
    toast.remove()

    // 如果容器为空，也移除容器
    const container = document.getElementById('toast-container')
    if (container && container.children.length === 0) {
      container.remove()
    }
  }, 300)
}

// 便捷方法
export const toast = {
  success: (message: string, duration?: number) => showToast({ message, type: 'success', duration }),
  error: (message: string, duration?: number) => showToast({ message, type: 'error', duration }),
  warning: (message: string, duration?: number) => showToast({ message, type: 'warning', duration }),
  info: (message: string, duration?: number) => showToast({ message, type: 'info', duration })
}
