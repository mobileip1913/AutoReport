<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { NCard, NForm, NFormItem, NSelect, NButton, NSpace, NStatistic } from 'naive-ui'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'
import { useCatalog } from '@/composables/useCatalog'

const props = defineProps<{ dataSourceId: number }>()
const emit = defineEmits<{ saved: [] }>()

const msg = useMessage()
const settings = ref<Record<string, unknown>>({})
const loading = ref(false)
const saving = ref(false)

const dsIdFn = () => props.dataSourceId
const { files, loadFiles, loadSheets, loadColumns } = useCatalog(dsIdFn)

const fileOptions = computed(() =>
  files.value.map((f) => ({
    label: f.label ?? f.file_label ?? f.keyword,
    value: f.keyword,
  })),
)

const sheetOptions = ref<{ label: string; value: string }[]>([])
const dateColOptions = ref<{ label: string; value: string }[]>([])

async function loadSettings() {
  loading.value = true
  try {
    await loadFiles()
    const { data } = await api.get(`/api/data-sources/${props.dataSourceId}/settings`)
    settings.value = data
    await refreshSheets()
    await refreshDateCols()
  } finally {
    loading.value = false
  }
}

async function refreshSheets() {
  const kw = String(settings.value.order_file ?? '')
  if (!kw) {
    sheetOptions.value = []
    return
  }
  const sheets = await loadSheets(kw)
  sheetOptions.value = sheets.map((s) => ({ label: s, value: s }))
}

async function refreshDateCols() {
  const kw = String(settings.value.order_file ?? '')
  const sh = String(settings.value.order_sheet ?? '')
  if (!kw || !sh) {
    dateColOptions.value = []
    return
  }
  const cols = await loadColumns(kw, sh)
  dateColOptions.value = cols.map((c) => ({ label: c, value: c }))
}

async function onFileChange(v: string) {
  settings.value.order_file = v
  settings.value.order_sheet = ''
  settings.value.order_date_col = ''
  await refreshSheets()
}

async function onSheetChange(v: string) {
  settings.value.order_sheet = v
  settings.value.order_date_col = ''
  await refreshDateCols()
}

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/api/data-sources/${props.dataSourceId}/settings`, settings.value)
    settings.value = data
    msg.success('数据源设置已保存')
    emit('saved')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    msg.error(err.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

watch(
  () => props.dataSourceId,
  () => loadSettings(),
  { immediate: true },
)
</script>

<template>
  <NCard title="数据源设置" size="small" :loading="loading">
    <NForm label-placement="left" label-width="120">
      <NFormItem label="订单文件">
        <NSelect
          :value="String(settings.order_file ?? '')"
          :options="fileOptions"
          filterable
          placeholder="选择订单文件"
          @update:value="onFileChange"
        />
      </NFormItem>
      <NFormItem label="订单 Sheet">
        <NSelect
          :value="String(settings.order_sheet ?? '')"
          :options="sheetOptions"
          filterable
          placeholder="选择 Sheet"
          @update:value="onSheetChange"
        />
      </NFormItem>
      <NFormItem label="日期列">
        <NSelect
          :value="String(settings.order_date_col ?? '')"
          :options="dateColOptions"
          filterable
          placeholder="选择日期列"
          @update:value="(v) => (settings.order_date_col = v)"
        />
      </NFormItem>
      <NFormItem label="日期格式">
        <NSelect
          :value="String(settings.order_date_format ?? '')"
          :options="[
            { label: 'MM/DD/YYYY', value: 'MM/DD/YYYY' },
            { label: 'YYYY-MM-DD', value: 'YYYY-MM-DD' },
            { label: 'M/D/YYYY', value: 'M/D/YYYY' },
          ]"
          @update:value="(v) => (settings.order_date_format = v)"
        />
      </NFormItem>
    </NForm>
    <NSpace>
      <NStatistic label="刷单单数" :value="Number(settings.review_order_distinct ?? 0)" />
      <NStatistic label="样品单数" :value="Number(settings.sample_order_distinct ?? 0)" />
    </NSpace>
    <template #action>
      <NButton type="primary" :loading="saving" @click="save">保存设置</NButton>
    </template>
  </NCard>
</template>
