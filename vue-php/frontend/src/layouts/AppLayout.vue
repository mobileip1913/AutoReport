<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { NSpin } from 'naive-ui'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const session = useSessionStore()

onMounted(() => {
  if (!session.data) session.load()
})

function navClass(prefix: string) {
  const p = route.path
  const active = p === prefix || (prefix !== '/' && p.startsWith(prefix))
  return ['app-nav-link', active ? 'is-active' : ''].filter(Boolean).join(' ')
}
</script>

<template>
  <div class="min-h-screen">
    <nav class="app-nav">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
        <RouterLink to="/" class="app-nav-brand shrink-0">AutoReport</RouterLink>
        <div class="app-nav-links ml-auto flex items-center gap-2">
          <RouterLink to="/" :class="navClass('/')">概览</RouterLink>
          <RouterLink to="/mappings" :class="navClass('/mappings')">报表配置</RouterLink>
          <RouterLink to="/daily" :class="navClass('/daily')">日报输出</RouterLink>
        </div>
      </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-8">
      <NSpin v-if="session.loading && !session.data" description="加载中…" />
      <RouterView v-else />
    </main>
  </div>
</template>
