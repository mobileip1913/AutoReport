<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  NModal,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NButton,
  NSpace,
  NDynamicInput,
} from 'naive-ui'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'
import { useCatalog } from '@/composables/useCatalog'

export interface MappingModalOpen {
  mappingId?: number
  dataSourceId: number
  lineCode?: string
  label?: string
}

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [boolean]; saved: [] }>()

const msg = useMessage()
const openCtx = ref<MappingModalOpen | null>(null)
const loading = ref(false)
const saving = ref(false)

const form = ref({
  line_label: '',
  line_code: '',
  format_type: 'usd',
  parts: [] as Array<{
    source_file_keyword: string
    sheet_name: string
    column_header: string
    aggregation: string
    combine_op: string
  }>,
})

const dataSourceId = computed(() => openCtx.value?.dataSourceId ?? 0)
const { files, loadFiles } = useCatalog(() => dataSourceId.value)

const fileOptions = computed(() =>
  files.value.map((f) => ({ label: f.label ?? f.file_label ?? f.keyword, value: f.keyword })),
)

const aggOptions = [
  { label: '求和', value: 'sum' },
  { label: '计数', value: 'count' },
  { label: '去重计数', value: 'count_distinct' },
  { label: '去重求和', value: 'sum_dedup' },
  { label: '平均值', value: 'avg' },
]

function defaultPart() {
  return {
    source_file_keyword: '',
    sheet_name: '',
    column_header: '',
    aggregation: 'sum',
    combine_op: 'add',
  }
}

async function open(ctx: MappingModalOpen) {
  openCtx.value = ctx
  emit('update:show', true)
  loading.value = true
  try {
    await loadFiles()
    if (ctx.mappingId) {
      const { data } = await api.get(`/api/mappings/${ctx.mappingId}`)
      form.value = {
        line_label: String(data.line_label ?? ''),
        line_code: String(data.line_code ?? ''),
        format_type: String(data.format_type ?? 'usd'),
        parts: (data.parts ?? []).map((p: Record<string, unknown>) => ({
          source_file_keyword: String(p.source_file_keyword ?? ''),
          sheet_name: String(p.sheet_name ?? ''),
          column_header: String(p.column_header ?? ''),
          aggregation: String(p.aggregation ?? 'sum'),
          combine_op: String(p.combine_op ?? 'add'),
        })),
      }
    } else {
      form.value = {
        line_label: ctx.label ?? '',
        line_code: ctx.lineCode ?? '',
        format_type: 'usd',
        parts: [defaultPart()],
      }
    }
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:show', false)
}

async function save() {
  if (!openCtx.value) return
  if (!form.value.parts.length) {
    msg.error('至少配置一条取数规则')
    return
  }
  saving.value = true
  try {
    const body = {
      line_label: form.value.line_label,
      line_code: form.value.line_code,
      format_type: form.value.format_type,
      parts: form.value.parts,
    }
    if (openCtx.value.mappingId) {
      await api.put(`/api/mappings/${openCtx.value.mappingId}`, body)
    } else {
      await api.post('/api/mappings', { ...body, data_source_id: openCtx.value.dataSourceId })
    }
    msg.success('映射已保存')
    emit('saved')
    close()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    msg.error(err.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

watch(
  () => props.show,
  (v) => {
    if (!v) openCtx.value = null
  },
)

defineExpose({ open })
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="字段映射"
    style="width: min(720px, 96vw)"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="loading">加载中…</div>
    <NForm v-else label-placement="left" label-width="100">
      <NFormItem label="显示名">
        <NInput v-model:value="form.line_label" />
      </NFormItem>
      <NFormItem label="行代码">
        <NInput v-model:value="form.line_code" :disabled="!!openCtx?.mappingId" />
      </NFormItem>
      <NFormItem label="格式">
        <NSelect
          v-model:value="form.format_type"
          :options="[
            { label: '美元', value: 'usd' },
            { label: '整数', value: 'int' },
            { label: '百分比', value: 'pct' },
            { label: '文本', value: 'text' },
          ]"
        />
      </NFormItem>
      <NFormItem label="取数规则">
        <NDynamicInput v-model:value="form.parts" :on-create="defaultPart">
          <template #default="{ value: part }">
            <NSpace vertical style="width: 100%">
              <NSelect
                v-model:value="part.source_file_keyword"
                :options="fileOptions"
                filterable
                placeholder="文件"
              />
              <NInput v-model:value="part.sheet_name" placeholder="Sheet 名称" />
              <NInput v-model:value="part.column_header" placeholder="列名" />
              <NSelect v-model:value="part.aggregation" :options="aggOptions" />
            </NSpace>
          </template>
        </NDynamicInput>
      </NFormItem>
    </NForm>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">取消</NButton>
        <NButton type="primary" :loading="saving" @click="save">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
