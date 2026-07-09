<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { NSelect, NSpin } from 'naive-ui'
import { useSessionStore } from '@/stores/session'
import AccountMenu from '@/components/AccountMenu.vue'

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

async function onStoreChange(v: number | null) {
  if (v) await session.setStore(v)
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
        <div v-if="session.data" class="flex items-center gap-2 shrink-0">
          <AccountMenu />
          <NSelect
            v-if="session.data.accessible_stores.length > 1"
            :value="session.data.current_store?.id ?? null"
            :options="
              session.data.accessible_stores.map((s) => ({
                label: `${s.name} · ${s.platform}`,
                value: s.id,
              }))
            "
            size="small"
            class="daily-hub__store-select"
            style="min-width: 220px"
            @update:value="onStoreChange"
          />
          <span v-else class="text-sm text-slate-600">{{ session.data.current_store?.name }}</span>
        </div>
      </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-8">
      <NSpin v-if="session.loading && !session.data" description="加载中…" />
      <RouterView v-else />
    </main>
  </div>
</template>
