import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 生产 build → backend/public/app/，base=/app/ 单端口部署
// 开发：5173 代理 API 到 8091
export default defineConfig({
  base: '/app/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8091', changeOrigin: true },
      '/demo': { target: 'http://127.0.0.1:8091', changeOrigin: true },
      '/daily': { target: 'http://127.0.0.1:8091', changeOrigin: true },
      '/static': { target: 'http://127.0.0.1:8091', changeOrigin: true },
    },
  },
  build: {
    outDir: '../backend/public/app',
    emptyOutDir: true,
  },
})
