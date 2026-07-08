<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()

function navClass(prefix: string) {
  const active = route.path === prefix || route.path.startsWith(prefix + '/')
  return ['nav-link', active ? 'is-active' : ''].filter(Boolean).join(' ')
}
</script>

<template>
  <div class="app-shell">
    <header class="app-nav">
      <div class="app-nav-inner">
        <RouterLink to="/" class="brand">AutoReport</RouterLink>
        <nav class="nav-links">
          <RouterLink to="/" :class="navClass('/')">概览</RouterLink>
          <RouterLink to="/mappings" :class="navClass('/mappings')">报表配置</RouterLink>
          <RouterLink to="/daily" :class="navClass('/daily')">日报输出</RouterLink>
        </nav>
        <span class="badge">Vue + PHP</span>
      </div>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
