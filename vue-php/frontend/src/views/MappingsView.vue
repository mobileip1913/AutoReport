<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useDialog } from 'naive-ui'
import { api } from '@/api/client'
import StoreSelect from '@/components/StoreSelect.vue'
import DsSettingsCard from '@/components/DsSettingsCard.vue'
import ReportFieldsTable from '@/components/ReportFieldsTable.vue'
import AuxFieldsTable from '@/components/AuxFieldsTable.vue'
import MappingModal from '@/components/MappingModal.vue'
import FormulaModal from '@/components/FormulaModal.vue'
import ReviewSettingsModal from '@/components/ReviewSettingsModal.vue'
import ScheduleSettingsModal from '@/components/ScheduleSettingsModal.vue'
import { useSessionStore } from '@/stores/session'

const dialog = useDialog()
const session = useSessionStore()
const loading = ref(true)
const error = ref('')
const bootstrap = ref<Record<string, unknown> | null>(null)
const modalShow = ref(false)
const formulaShow = ref(false)
const reviewShow = ref(false)
const scheduleShow = ref(false)
const mappingModal = ref<InstanceType<typeof MappingModal> | null>(null)
const formulaModal = ref<InstanceType<typeof FormulaModal> | null>(null)
const dsSettingsCard = ref<InstanceType<typeof DsSettingsCard> | null>(null)

const dsId = computed(() => {
  const sources = bootstrap.value?.data_sources as Array<{ id: number }> | undefined
  return sources?.[0]?.id ?? null
})

const rows = computed(() => {
  if (!bootstrap.value || !dsId.value) return []
  return (
    (bootstrap.value.excel_config as Record<number, Array<Record<string, unknown>>>)?.[dsId.value] ??
    []
  )
})

const auxItems = computed(() => {
  if (!bootstrap.value || !dsId.value) return []
  return (
    (bootstrap.value.auxiliary as Record<number, Array<Record<string, unknown>>>)?.[dsId.value] ?? []
  )
})

const fileLabels = computed(() => {
  if (!dsId.value) return {}
  return (
    (bootstrap.value?.file_labels_by_ds as Record<number, Record<string, string>>)?.[dsId.value] ??
    {}
  )
})

const fieldLabels = computed(() => {
  if (!dsId.value) return {}
  return (
    (bootstrap.value?.field_labels_by_ds as Record<number, Record<string, string>>)?.[dsId.value] ??
    {}
  )
})

const dsSettings = computed(() => {
  if (!dsId.value) return {}
  return (
    (bootstrap.value?.ds_settings as Record<number, Record<string, unknown>>)?.[dsId.value] ?? {}
  )
})

const reviewImportCodes = computed(() => (bootstrap.value?.review_import_codes as string[]) ?? [])
const reviewLogisticsCodes = computed(
  () => (bootstrap.value?.review_logistics_codes as string[]) ?? [],
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/api/mappings/bootstrap')
    bootstrap.value = data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)

watch(
  () => session.data?.current_store?.id,
  () => load(),
)

function openEdit(row: Record<string, unknown>) {
  if (row.field_type === 'formula') {
    openFormula(row)
    return
  }
  const mapping = row.mapping as Record<string, unknown> | undefined
  if (!dsId.value) return
  modalShow.value = true
  mappingModal.value?.open({
    mappingId: mapping?.id ? Number(mapping.id) : undefined,
    dataSourceId: dsId.value,
    lineCode: String(row.line_code ?? ''),
    label: String(row.label ?? ''),
  })
}

function openEditItem(item: Record<string, unknown>) {
  const mapping = item.mapping as Record<string, unknown> | undefined
  if (!dsId.value || !mapping?.id) return
  modalShow.value = true
  mappingModal.value?.open({
    mappingId: Number(mapping.id),
    dataSourceId: dsId.value,
    label: String(item.label ?? ''),
  })
}

function openFormula(row: Record<string, unknown>) {
  if (!dsId.value) return
  formulaShow.value = true
  const mapping = row.mapping as Record<string, unknown> | undefined
  if (mapping?.id) formulaModal.value?.openEdit(Number(mapping.id))
}

function openNew() {
  if (!dsId.value) return
  modalShow.value = true
  mappingModal.value?.open({ dataSourceId: dsId.value })
}

function exportJson() {
  if (!dsId.value) return
  window.open(`/api/data-sources/${dsId.value}/config/export`, '_blank')
}

function confirmDelete(row: Record<string, unknown>) {
  const mapping = row.mapping as Record<string, unknown> | undefined
  const id = mapping?.id ? Number(mapping.id) : 0
  if (!id) return
  dialog.warning({
    title: '删除字段',
    content: `确定删除「${row.label}」？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      await api.delete(`/api/mappings/${id}`)
      await load()
    },
  })
}

function confirmDeleteAux(id: number) {
  const item = auxItems.value.find((i) => Number((i.mapping as Record<string, unknown>)?.id) === id)
  confirmDelete({ mapping: { id }, label: item?.label ?? '字段' })
}

function onScheduleSaved(time: string) {
  dsSettingsCard.value?.onScheduleSaved(time)
  load()
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-center justify-between mb-6 gap-3">
      <div class="flex flex-wrap items-center gap-3 min-w-0">
        <h1 class="text-2xl font-bold shrink-0">报表配置</h1>
        <StoreSelect variant="compact" />
      </div>
      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <button
          v-if="dsId"
          type="button"
          class="btn-export-config px-4 py-2 border border-slate-200 rounded-lg text-sm hover:bg-slate-50 text-slate-700"
          @click="exportJson"
        >
          导出 JSON
        </button>
        <button
          type="button"
          class="btn-new-mapping btn-primary text-sm font-medium px-4 py-2 rounded-lg"
          @click="openNew"
        >
          增加日报字段
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-sm text-slate-400 py-8">加载中…</div>
    <div v-else-if="error" class="text-sm text-red-600 py-4">{{ error }}</div>
    <section v-else-if="dsId" class="mb-8">
      <DsSettingsCard
        ref="dsSettingsCard"
        :data-source-id="dsId"
        @saved="load"
        @open-schedule="scheduleShow = true"
      />

      <ReportFieldsTable
        v-if="rows.length"
        :rows="rows"
        :data-source-id="dsId"
        :file-labels="fileLabels"
        :field-labels="fieldLabels"
        :ds-settings="dsSettings"
        :review-import-codes="reviewImportCodes"
        :review-logistics-codes="reviewLogisticsCodes"
        @edit="openEdit"
        @delete="confirmDelete"
      />

      <AuxFieldsTable
        v-if="auxItems.length"
        :items="auxItems"
        :data-source-id="dsId"
        :file-labels="fileLabels"
        :field-labels="fieldLabels"
        :ds-settings="dsSettings"
        :review-import-codes="reviewImportCodes"
        :review-logistics-codes="reviewLogisticsCodes"
        @edit="openEditItem"
        @delete="confirmDeleteAux"
      />
    </section>

    <MappingModal ref="mappingModal" v-model:show="modalShow" @saved="load" />
    <FormulaModal ref="formulaModal" v-model:show="formulaShow" :data-source-id="dsId ?? 0" @saved="load" />
    <ReviewSettingsModal v-model:show="reviewShow" :data-source-id="dsId ?? 0" @saved="load" />
    <ScheduleSettingsModal
      v-model:show="scheduleShow"
      :data-source-id="dsId ?? 0"
      @saved="onScheduleSaved"
    />
  </div>
</template>
