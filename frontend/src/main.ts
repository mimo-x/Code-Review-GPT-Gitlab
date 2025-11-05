import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/main.css'

// Preline 需要在路由变化后重新初始化
import 'preline/preline'
import { IStaticMethods } from 'preline/preline'
declare global {
  interface Window {
    HSStaticMethods: IStaticMethods
  }
}

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 路由变化后重新初始化 Preline
router.afterEach(() => {
  setTimeout(() => {
    if (window.HSStaticMethods) {
      window.HSStaticMethods.autoInit()
    }
  }, 100)
})

app.mount('#app')
