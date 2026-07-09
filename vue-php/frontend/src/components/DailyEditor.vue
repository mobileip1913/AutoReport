<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import FieldTypeTag from '@/components/FieldTypeTag.vue'
import RuleSummary from '@/components/RuleSummary.vue'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'

const props = defineProps<{
  rows: Array<Record<string, unknown>>
  dataSourceId: number
  runId?: number | null
  compact?: boolean
  fileLabels?: Record<string, string>
  fieldLabels?: Record<string, string>
  dsSettings?: Record<string, unknown>
  reviewImportCodes?: string[]
  reviewLogisticsCodes?: string[]
}>()

const emit = defineEmits<{ changed: [] }>()

const msg = useMessage()
const localRows = ref<Array<Record<string, unknown>>>([])
const dragIdx = ref<number | null>(null)
const statusText = ref('已同步')
const editingLabelId = ref<number | null>(null)
const editingValueId = ref<number | null>(null)

const hasRun = computed(() => !!props.runId)

watch(
  () => props.rows,
  (r) => {
    localRows.value = r.map((row) => ({ ...row }))
  },
  { immediate: true, deep: true },
)

function colLetter(index: number): string {
  let n = 6 + index
  let s = ''
  while (n > 0) {
    const rem = (n - 1) % 26
    s = String.fromCharCode(65 + rem) + s
    n = Math.floor((n - 1) / 26)
  }
  return s
}

async function saveOrder() {
  const ids = localRows.value.map((r) => Number(r.mapping_id)).filter(Boolean)
  await api.put(`/api/data-sources/${props.dataSourceId}/report-fields/order`, {
    mapping_ids: ids,
    run_id: props.runId ?? undefined,
  })
  localRows.value.forEach((r, i) => {
    r.col = colLetter(i)
  })
  statusText.value = '顺序已保存'
  msg.success('顺序已保存')
  emit('changed')
}

function moveRow(idx: number, dir: -1 | 1) {
  const next = idx + dir
  if (next < 0 || next >= localRows.value.length) return
  const copy = [...localRows.value]
  const tmp = copy[idx]!
  copy[idx] = copy[next]!
  copy[next] = tmp
  localRows.value = copy
  saveOrder().catch((e) => msg.error(e instanceof Error ? e.message : '排序失败'))
}

function onDragStart(idx: number, e: DragEvent) {
  dragIdx.value = idx
  e.dataTransfer!.effectAllowed = 'move'
}

function onDragOver(idx: number, e: DragEvent) {
  e.preventDefault()
  if (dragIdx.value === null || dragIdx.value === idx) return
  const copy = [...localRows.value]
  const item = copy.splice(dragIdx.value, 1)[0]!
  copy.splice(idx, 0, item)
  localRows.value = copy
  dragIdx.value = idx
}

function onDragEnd() {
  if (dragIdx.value !== null) {
    saveOrder().catch((e) => msg.error(e instanceof Error ? e.message : '排序失败'))
  }
  dragIdx.value = null
}

async function saveLabel(row: Record<string, unknown>, label: string) {
  const id = Number(row.mapping_id)
  await api.patch(`/api/mappings/${id}/label`, {
    label,
    run_id: props.runId ?? undefined,
  })
  row.label = label
  editingLabelId.value = null
  statusText.value = '名称已保存'
  emit('changed')
}

async function saveValue(row: Record<string, unknown>, raw: string) {
  if (!props.runId || !row.value_id) return
  const n = parseFloat(raw.replace(/[$,¥\s]/g, ''))
  if (!Number.isFinite(n)) {
    msg.error('无效数值')
    return
  }
  const { data } = await api.patch(
    `/api/report-runs/${props.runId}/values/${row.value_id}`,
    { raw_value: n },
  )
  row.raw_value = data.raw_value
  row.display_value = data.display_value
  row.is_overridden = data.is_overridden
  editingValueId.value = null
  statusText.value = '已同步'
  emit('changed')
}
</script>

<template>
  <div class="daily-editor bg-white rounded-xl shadow border border-slate-200 overflow-hidden">
    <div
      class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 bg-slate-50 border-b border-slate-100"
    >
      <span class="text-sm text-slate-600">
        {{ localRows.length }} 个字段
        <span v-if="hasRun" class="text-xs text-slate-400 ml-2">{{ statusText }}</span>
      </span>
    </div>
    <div class="overflow-x-auto">
      <table
        class="w-full text-sm min-w-[720px] daily-excel-table"
        :class="{ 'daily-excel-table--compact': compact, 'daily-excel-table--preview': !hasRun }"
      >
        <thead class="bg-slate-50 text-left text-slate-500 text-xs">
          <tr>
            <th class="daily-th-drag w-16" aria-label="排序" />
            <th v-if="hasRun" class="px-3 py-2 w-12">列</th>
            <th v-if="hasRun" class="px-3 py-2 w-16">类型</th>
            <th class="px-3 py-2">指标名称</th>
            <th v-if="hasRun" class="px-3 py-2 w-28">系统计算</th>
            <th v-if="hasRun" class="px-3 py-2 w-32">报表值</th>
            <th v-if="!compact" class="px-3 py-2">规则摘要</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in localRows"
            :key="String(row.mapping_id)"
            class="daily-row border-t border-slate-100"
            :class="{
              'daily-row--overridden': row.is_overridden,
              'daily-row--manual': row.is_manual,
              'daily-row--dragging': dragIdx === idx,
            }"
            @dragover="onDragOver(idx, $event)"
          >
            <td class="daily-td-drag px-2 py-2">
              <div class="daily-row-order flex flex-col items-center gap-0.5">
                <button
                  type="button"
                  class="daily-order-btn daily-order-btn--up"
                  :disabled="idx === 0"
                  aria-label="上移"
                  @click="moveRow(idx, -1)"
                >
                  ▲
                </button>
                <span
                  class="drag-handle cursor-grab text-slate-400"
                  draggable="true"
                  title="拖动排序"
                  @dragstart="onDragStart(idx, $event)"
                  @dragend="onDragEnd"
                  >⋮⋮</span
                >
                <button
                  type="button"
                  class="daily-order-btn daily-order-btn--down"
                  :disabled="idx === localRows.length - 1"
                  aria-label="下移"
                  @click="moveRow(idx, 1)"
                >
                  ▼
                </button>
              </div>
            </td>
            <td v-if="hasRun" class="px-3 py-2 font-mono text-xs text-slate-400 tabular-nums">
              {{ row.col ?? colLetter(idx) }}
            </td>
            <td v-if="hasRun" class="px-3 py-2">
              <FieldTypeTag :type="String(row.field_type ?? 'fetch')" />
            </td>
            <td class="px-3 py-2">
              <template v-if="editingLabelId === row.mapping_id">
                <input
                  class="border rounded px-2 py-1 text-sm w-full"
                  :value="String(row.label ?? '')"
                  @keydown.enter="(e) => saveLabel(row, (e.target as HTMLInputElement).value.trim())"
                  @blur="(e) => saveLabel(row, (e.target as HTMLInputElement).value.trim())"
                />
              </template>
              <button
                v-else
                type="button"
                class="field-label-display text-left font-medium hover:text-sky-600"
                @click="editingLabelId = Number(row.mapping_id)"
              >
                {{ row.label }}
              </button>
              <div class="field-code-hint text-xs text-slate-400">{field:{{ row.line_code }}}</div>
            </td>
            <td v-if="hasRun" class="px-3 py-2 text-xs text-slate-500 tabular-nums">
              {{ row.computed_display ?? row.computed_raw ?? '—' }}
            </td>
            <td v-if="hasRun" class="px-3 py-2">
              <template v-if="row.is_manual">
                <span class="text-slate-400 text-xs">手工项</span>
              </template>
              <template v-else-if="row.value_id">
                <input
                  v-if="editingValueId === row.value_id"
                  class="border rounded px-2 py-1 text-sm w-24"
                  :value="String(row.raw_value ?? '')"
                  @keydown.enter="(e) => saveValue(row, (e.target as HTMLInputElement).value)"
                  @blur="(e) => saveValue(row, (e.target as HTMLInputElement).value)"
                />
                <button
                  v-else
                  type="button"
                  class="value-display tabular-nums"
                  :class="row.is_overridden ? 'text-amber-900' : 'text-slate-800'"
                  @click="editingValueId = Number(row.value_id)"
                >
                  {{ row.display_value || '—' }}
                </button>
              </template>
              <span v-else class="text-slate-300 text-xs">—</span>
            </td>
            <td v-if="!compact" class="px-3 py-2 text-xs max-w-xs">
              <RuleSummary
                :row="row"
                :mapping="(row.mapping as Record<string, unknown>) ?? {}"
                :ds-id="dataSourceId"
                :file-labels="fileLabels"
                :field-labels="fieldLabels"
                :ds-settings="dsSettings"
                :review-import-codes="reviewImportCodes"
                :review-logistics-codes="reviewLogisticsCodes"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.daily-row--dragging {
  opacity: 0.6;
  background: #f0f9ff;
}
.daily-order-btn {
  font-size: 10px;
  line-height: 1;
  color: #94a3b8;
  padding: 0 2px;
}
.daily-order-btn:disabled {
  opacity: 0.3;
}
</style>
