import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 开发：Vue 5173，API 代理到 PHP 8091（不与 php-backend:8090 / Python:8081 冲突）
export default defineConfig({
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
    },
  },
  build: {
    outDir: '../backend/public/app',
    emptyOutDir: true,
  },
})
