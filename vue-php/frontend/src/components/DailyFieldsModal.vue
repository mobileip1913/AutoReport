<script setup lang="ts">
import { ref } from 'vue'
import { NModal } from 'naive-ui'
import DailyEditor from '@/components/DailyEditor.vue'

const props = defineProps<{
  show: boolean
  dataSourceId: number
  runId?: number | null
  rows: Array<Record<string, unknown>>
  fileLabels?: Record<string, string>
  fieldLabels?: Record<string, string>
  dsSettings?: Record<string, unknown>
  reviewImportCodes?: string[]
  reviewLogisticsCodes?: string[]
}>()

const emit = defineEmits<{ 'update:show': [boolean]; changed: [] }>()

const localRows = ref<Array<Record<string, unknown>>>([])

function openWith(rows: Array<Record<string, unknown>>) {
  localRows.value = rows.map((r) => ({ ...r }))
}

defineExpose({ openWith })
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="日报字段"
    style="width: min(960px, 98vw)"
    @update:show="emit('update:show', $event)"
  >
    <p class="text-xs text-slate-500 mb-3">
      拖柄或 ▲▼ 排序 · 点击名称或报表值可编辑
    </p>
    <DailyEditor
      :rows="localRows.length ? localRows : rows"
      :data-source-id="dataSourceId"
      :run-id="runId"
      compact
      :file-labels="fileLabels"
      :field-labels="fieldLabels"
      :ds-settings="dsSettings"
      :review-import-codes="reviewImportCodes"
      :review-logistics-codes="reviewLogisticsCodes"
      @changed="emit('changed')"
    />
  </NModal>
</template>
