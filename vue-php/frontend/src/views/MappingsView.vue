<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api/client'

const loading = ref(true)
const error = ref('')
const note = ref('页面骨架已就绪；报表配置业务组件将按迁移计划逐步接入。')

onMounted(async () => {
  try {
    // 探活：后续替换为 GET /api/mappings/bootstrap
    await api.get('/api/data-sources/1/settings').catch(() => null)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'API 不可用，请确认 PHP 后端已在 8091 启动'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <h1>报表配置</h1>
    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else class="muted">{{ note }}</p>
  </div>
</template>
