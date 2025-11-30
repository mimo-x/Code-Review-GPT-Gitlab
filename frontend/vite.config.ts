import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const rootDir = resolve(__dirname, '..')
  const env = loadEnv(mode, rootDir, '')

  const proxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://backend:8000'

  return {
    plugins: [vue()],
    envDir: rootDir,
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      host: '0.0.0.0',
      port: 3000,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true
        }
      }
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: false
    }
  }
})
