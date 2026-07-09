<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  NModal,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NButton,
  NSpace,
  NCheckbox,
} from 'naive-ui'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'

const props = defineProps<{ show: boolean; dataSourceId: number }>()
const emit = defineEmits<{ 'update:show': [boolean]; saved: [] }>()

const msg = useMessage()
const mappingId = ref<number | null>(null)
const loading = ref(false)
const saving = ref(false)
const reuseFields = ref<Array<{ code: string; name: string }>>([])

const form = ref({
  label: '',
  report_group: '',
  sort_order: 0,
  expression: '=',
  format_type: 'usd',
  is_highlight: false,
})

const fieldTokens = computed(() =>
  reuseFields.value.map((f) => ({ code: f.code, name: f.name })),
)

async function loadReuse() {
  const { data } = await api.get('/api/mappings/bootstrap')
  const byDs = data.reuse_fields as Record<string, Array<{ code: string; name: string }>>
  reuseFields.value = byDs[String(props.dataSourceId)] ?? byDs[props.dataSourceId] ?? []
}

async function openEdit(id: number) {
  mappingId.value = id
  emit('update:show', true)
  loading.value = true
  try {
    await loadReuse()
    const { data } = await api.get(`/api/mappings/${id}`)
    form.value = {
      label: String(data.label ?? ''),
      report_group: String(data.report_group ?? ''),
      sort_order: Number(data.sort_order ?? 0),
      expression: String(data.expression ?? '='),
      format_type: String(data.format_type ?? 'usd'),
      is_highlight: !!data.is_highlight,
    }
  } finally {
    loading.value = false
  }
}

function openCreate() {
  mappingId.value = null
  emit('update:show', true)
  form.value = {
    label: '',
    report_group: '报表字段',
    sort_order: 0,
    expression: '=',
    format_type: 'usd',
    is_highlight: false,
  }
  loadReuse()
}

function close() {
  emit('update:show', false)
}

function insertToken(code: string) {
  form.value.expression += `{field:${code}}`
}

async function save() {
  if (!form.value.label.trim()) {
    msg.error('请填写名称')
    return
  }
  saving.value = true
  try {
    const body = { ...form.value, data_source_id: props.dataSourceId }
    if (mappingId.value) {
      await api.put(`/api/formula-lines/${mappingId.value}`, body)
    } else {
      await api.post('/api/formula-lines', body)
    }
    msg.success('公式行已保存')
    emit('saved')
    close()
  } catch (e: unknown) {
    msg.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

watch(
  () => props.show,
  (v) => {
    if (!v) mappingId.value = null
  },
)

defineExpose({ openEdit, openCreate })
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="mappingId ? '编辑公式行' : '新增公式行'"
    style="width: min(640px, 96vw)"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="loading">加载中…</div>
    <NForm v-else label-placement="left" label-width="80">
      <NFormItem label="名称">
        <NInput v-model:value="form.label" />
      </NFormItem>
      <NFormItem label="分组">
        <NInput v-model:value="form.report_group" />
      </NFormItem>
      <NFormItem label="排序">
        <NInputNumber v-model:value="form.sort_order" :min="0" class="w-full" />
      </NFormItem>
      <NFormItem label="公式">
        <NInput v-model:value="form.expression" type="textarea" :rows="3" />
      </NFormItem>
      <div class="flex flex-wrap gap-1 mb-3 ml-20">
        <NButton
          v-for="f in fieldTokens"
          :key="f.code"
          size="tiny"
          @click="insertToken(f.code)"
        >
          {{ f.name }}
        </NButton>
      </div>
      <NFormItem label="格式">
        <NSelect
          v-model:value="form.format_type"
          :options="[
            { label: '美元', value: 'usd' },
            { label: '整数', value: 'int' },
            { label: '百分比', value: 'pct' },
          ]"
        />
      </NFormItem>
      <NFormItem label="高亮">
        <NCheckbox v-model:checked="form.is_highlight">导出时高亮</NCheckbox>
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
