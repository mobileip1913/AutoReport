<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api/client'

const reportDate = ref(new Date().toISOString().slice(0, 10))
const dataSourceId = ref(1)
const message = ref('')
const busy = ref(false)

async function generate() {
  busy.value = true
  message.value = ''
  try {
    const { data } = await api.post('/api/generate', {
      data_source_id: dataSourceId.value,
      report_date: reportDate.value,
      store_name: '',
      is_test: true,
    })
    message.value = `已生成 run #${data.id}，后续将在此页展示编辑器`
  } catch (e: unknown) {
    message.value = e instanceof Error ? e.message : '生成失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1>日报输出</h1>
    <div class="toolbar">
      <label>
        数据源 ID
        <input v-model.number="dataSourceId" type="number" min="1" class="input" />
      </label>
      <label>
        报表日期
        <input v-model="reportDate" type="date" class="input" />
      </label>
      <button type="button" class="btn-primary" :disabled="busy" @click="generate">
        {{ busy ? '生成中…' : '生成日报（API）' }}
      </button>
    </div>
    <p v-if="message" class="muted">{{ message }}</p>
    <p class="hint">完整表格编辑 UI 待迁移；当前可先验证 Vue → PHP API 链路。</p>
  </div>
</template>
