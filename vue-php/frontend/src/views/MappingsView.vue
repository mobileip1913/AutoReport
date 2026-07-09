<script setup lang="ts">
import { computed, onMounted, ref, h } from 'vue'
import { NAlert, NButton, NDataTable, NSpin } from 'naive-ui'
import { api } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import DsSettingsCard from '@/components/DsSettingsCard.vue'
import FieldTypeTag from '@/components/FieldTypeTag.vue'
import RuleSummary from '@/components/RuleSummary.vue'
import MappingModal from '@/components/MappingModal.vue'

const session = useSessionStore()
const loading = ref(true)
const error = ref('')
const bootstrap = ref<Record<string, unknown> | null>(null)
const modalShow = ref(false)
const mappingModal = ref<InstanceType<typeof MappingModal> | null>(null)

const dsId = computed(() => {
  const cur = session.data?.current_store?.data_source_id
  if (cur) return cur
  const sources = bootstrap.value?.data_sources as Array<{ id: number }> | undefined
  return sources?.[0]?.id ?? null
})

const rows = computed(() => {
  if (!bootstrap.value || !dsId.value) return []
  const cfg =
    (bootstrap.value.excel_config as Record<number, Array<Record<string, unknown>>>)?.[dsId.value] ??
    []
  return cfg
})

const fileLabels = computed(() => {
  if (!dsId.value) return {}
  return (
    (bootstrap.value?.file_labels_by_ds as Record<number, Record<string, string>>)?.[dsId.value] ?? {}
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

const reviewImportCodes = computed(
  () => (bootstrap.value?.review_import_codes as string[]) ?? [],
)
const reviewLogisticsCodes = computed(
  () => (bootstrap.value?.review_logistics_codes as string[]) ?? [],
)

const columns = [
  { title: '列', key: 'col', width: 56 },
  {
    title: '类型',
    key: 'field_type',
    width: 88,
    render: (row: { field_type: string }) => h(FieldTypeTag, { type: row.field_type }),
  },
  { title: '指标名称', key: 'label', minWidth: 120 },
  {
    title: '取数规则',
    key: 'mapping',
    minWidth: 200,
    render: (row: Record<string, unknown>) =>
      h(RuleSummary, {
        row,
        mapping: (row.mapping as Record<string, unknown>) ?? {},
        dsId: dsId.value!,
        fileLabels: fileLabels.value,
        fieldLabels: fieldLabels.value,
        dsSettings: dsSettings.value,
        reviewImportCodes: reviewImportCodes.value,
        reviewLogisticsCodes: reviewLogisticsCodes.value,
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row: Record<string, unknown>) =>
      h(
        NButton,
        {
          size: 'small',
          quaternary: true,
          type: 'primary',
          onClick: () => openEdit(row),
        },
        { default: () => '编辑' },
      ),
  },
]

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

function openEdit(row: Record<string, unknown>) {
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

function openNew() {
  if (!dsId.value) return
  modalShow.value = true
  mappingModal.value?.open({ dataSourceId: dsId.value })
}

function exportJson() {
  if (!dsId.value) return
  window.open(`/api/data-sources/${dsId.value}/config/export`, '_blank')
}
</script>

<template>
  <div>
    <div class="page-toolbar">
      <h1 class="page-toolbar__title">报表配置</h1>
      <div class="flex flex-wrap items-center gap-2">
        <NButton v-if="dsId" @click="exportJson">导出 JSON</NButton>
        <NButton type="primary" @click="openNew">日报字段</NButton>
      </div>
    </div>

    <NSpin v-if="loading" />
    <NAlert v-else-if="error" type="error" :title="error" />
    <template v-else-if="dsId">
      <DsSettingsCard :data-source-id="dsId" class="mb-6" @saved="load" />

      <div class="section-table-card bg-white rounded-xl shadow border border-slate-200 overflow-x-auto mb-4">
        <div class="section-table-header px-4 py-3 border-b border-slate-100 flex justify-between">
          <div>
            <span class="section-table-title font-medium">日报字段</span>
            <span class="section-table-count ml-2 text-xs text-slate-400">{{ rows.length }}</span>
          </div>
          <span class="text-xs text-slate-400">顺序与日报页同步</span>
        </div>
        <NDataTable :columns="columns" :data="rows" :bordered="false" size="small" />
      </div>
    </template>

    <MappingModal ref="mappingModal" v-model:show="modalShow" @saved="load" />
  </div>
</template>
