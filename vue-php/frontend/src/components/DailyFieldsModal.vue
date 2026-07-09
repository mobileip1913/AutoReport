<script setup lang="ts">
import { ref } from 'vue'
import { NModal, NButton, NSpace, NInputNumber, NTable } from 'naive-ui'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'

const props = defineProps<{
  show: boolean
  dataSourceId: number
  runId?: number | null
  rows: Array<Record<string, unknown>>
}>()

const emit = defineEmits<{ 'update:show': [boolean]; changed: [] }>()

const msg = useMessage()
const localRows = ref<Array<Record<string, unknown>>>([])
const saving = ref(false)

function openWith(rows: Array<Record<string, unknown>>) {
  localRows.value = rows.map((r) => ({ ...r }))
}

function close() {
  emit('update:show', false)
}

async function saveValue(row: Record<string, unknown>, raw: number | null) {
  if (!props.runId || !row.value_id) return
  saving.value = true
  try {
    await api.patch(`/api/report-runs/${props.runId}/values/${row.value_id}`, {
      raw_value: raw,
    })
    msg.success('已保存')
    emit('changed')
  } catch (e: unknown) {
    const err = e as { message?: string }
    msg.error(err.message ?? '保存失败')
  } finally {
    saving.value = false
  }
}

async function move(idx: number, dir: -1 | 1) {
  const next = idx + dir
  if (next < 0 || next >= localRows.value.length) return
  const copy = [...localRows.value]
  const a = copy[idx]
  const b = copy[next]
  if (!a || !b) return
  copy[idx] = b
  copy[next] = a
  localRows.value = copy
  const ids = copy.map((r) => Number(r.mapping_id)).filter(Boolean)
  saving.value = true
  try {
    await api.put(`/api/data-sources/${props.dataSourceId}/report-fields/order`, {
      mapping_ids: ids,
      run_id: props.runId ?? undefined,
    })
    msg.success('顺序已更新')
    emit('changed')
  } catch (e: unknown) {
    const err = e as { message?: string }
    msg.error(err.message ?? '排序失败')
  } finally {
    saving.value = false
  }
}

defineExpose({ openWith })
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="日报字段"
    style="width: min(920px, 96vw)"
    @update:show="emit('update:show', $event)"
  >
    <NTable :bordered="false" size="small">
      <thead>
        <tr>
          <th>列</th>
          <th>指标</th>
          <th>数值</th>
          <th>排序</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, idx) in localRows" :key="String(row.mapping_id ?? row.line_code)">
          <td>{{ row.col }}</td>
          <td>{{ row.label }}</td>
          <td>
            <template v-if="runId && row.value_id">
              <NInputNumber
                size="small"
                :value="row.raw_value != null ? Number(row.raw_value) : null"
                :show-button="false"
                style="width: 120px"
                @update:value="(v) => saveValue(row, v)"
              />
              <span v-if="row.display_value" class="text-xs text-slate-400 ml-1">{{
                row.display_value
              }}</span>
            </template>
            <span v-else class="text-slate-400 text-xs">生成日报后可编辑</span>
          </td>
          <td>
            <NSpace size="small">
              <NButton size="tiny" :disabled="idx === 0 || saving" @click="move(idx, -1)">↑</NButton>
              <NButton
                size="tiny"
                :disabled="idx === localRows.length - 1 || saving"
                @click="move(idx, 1)"
                >↓</NButton
              >
            </NSpace>
          </td>
        </tr>
      </tbody>
    </NTable>
    <template #footer>
      <NButton @click="close">关闭</NButton>
    </template>
  </NModal>
</template>
