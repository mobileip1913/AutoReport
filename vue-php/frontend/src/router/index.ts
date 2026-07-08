import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/mappings', name: 'mappings', component: () => import('@/views/MappingsView.vue') },
    { path: '/daily', name: 'daily', component: () => import('@/views/DailyView.vue') },
  ],
})

export default router
