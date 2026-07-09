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
  NTabs,
  NTabPane,
} from 'naive-ui'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'
import MappingPartBlock from '@/components/mapping/MappingPartBlock.vue'
import {
  MAPPING_TABS,
  LINE_TYPE_BY_TAB,
  defaultSourcePart,
  defaultRefPart,
  flatPartsFromApi,
  partsToSaveBody,
  detectTabFromMapping,
  type MappingPart,
  type MappingTab,
} from '@/utils/mappingConstants'

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
const activeTab = ref<MappingTab>('fetch')
const reuseFields = ref<Array<{ code: string; name: string }>>([])

const form = ref({
  line_label: '',
  line_code: '',
  report_group: '',
  sort_order: 0,
  format_type: 'usd',
  per_order_amount: 1,
  per_order_basis: 'valid_orders',
  ratio_percent: 100,
  ratio_base_code: '',
})

const parts = ref<MappingPart[]>([defaultSourcePart()])

const dataSourceId = computed(() => openCtx.value?.dataSourceId ?? 0)
const title = computed(() => form.value.line_label || '字段映射')

const reuseOptions = computed(() =>
  reuseFields.value.map((f) => ({ label: `${f.name} (${f.code})`, value: f.code })),
)

const ratioBaseOptions = computed(() => reuseOptions.value)

async function loadReuseFields() {
  if (!dataSourceId.value) return
  const { data } = await api.get('/api/mappings/bootstrap')
  const byDs = data.reuse_fields as Record<string, Array<{ code: string; name: string }>>
  reuseFields.value = byDs[String(dataSourceId.value)] ?? byDs[dataSourceId.value] ?? []
}

async function open(ctx: MappingModalOpen) {
  openCtx.value = ctx
  emit('update:show', true)
  loading.value = true
  try {
    await loadReuseFields()
    if (ctx.mappingId) {
      const { data } = await api.get(`/api/mappings/${ctx.mappingId}`)
      form.value = {
        line_label: String(data.label ?? data.logical_field_name ?? ''),
        line_code: String(data.line_code ?? ''),
        report_group: String(data.report_group ?? ''),
        sort_order: Number(data.sort_order ?? 0),
        format_type: String(data.format_type ?? 'usd'),
        per_order_amount: Number(data.per_order_amount ?? 1),
        per_order_basis: String(data.per_order_basis ?? 'valid_orders'),
        ratio_percent: Number(data.ratio_percent ?? 100),
        ratio_base_code: String(data.ratio_base_code ?? ''),
      }
      activeTab.value = detectTabFromMapping(data)
      parts.value = flatPartsFromApi((data.parts as MappingPart[]) ?? [])
    } else {
      form.value = {
        line_label: ctx.label ?? '',
        line_code: ctx.lineCode ?? '',
        report_group: '报表字段',
        sort_order: 0,
        format_type: 'usd',
        per_order_amount: 1,
        per_order_basis: 'valid_orders',
        ratio_percent: 100,
        ratio_base_code: '',
      }
      activeTab.value = 'placeholder'
      parts.value = [defaultSourcePart()]
    }
  } finally {
    loading.value = false
  }
}

function close() {
  emit('update:show', false)
}

function addPart() {
  parts.value.push(activeTab.value === 'reuse' ? defaultRefPart() : defaultSourcePart())
}

function removePart(i: number) {
  parts.value.splice(i, 1)
}

async function save() {
  if (!openCtx.value) return
  const tab = activeTab.value
  const body: Record<string, unknown> = {
    label: form.value.line_label.trim() || null,
    report_group: form.value.report_group.trim() || null,
    sort_order: form.value.sort_order,
    format_type: form.value.format_type,
    line_type: LINE_TYPE_BY_TAB[tab],
    parts: [],
  }

  if (tab === 'per_order') {
    if (!(form.value.per_order_amount >= 0)) {
      msg.error('请填写每单金额（≥ 0）')
      return
    }
    body.per_order_amount = form.value.per_order_amount
    body.per_order_basis = form.value.per_order_basis
  } else if (tab === 'ratio') {
    if (!form.value.ratio_base_code) {
      msg.error('请选择基准字段')
      return
    }
    body.ratio_base_code = form.value.ratio_base_code
    body.ratio_percent = form.value.ratio_percent
  } else if (tab === 'fetch' || tab === 'reuse') {
    const saveParts = partsToSaveBody(parts.value, tab)
    if (!saveParts.length) {
      msg.error('至少配置一条取数规则')
      return
    }
    body.parts = saveParts
  }

  saving.value = true
  try {
    if (openCtx.value.mappingId) {
      await api.put(`/api/mappings/${openCtx.value.mappingId}`, body)
    } else {
      await api.post('/api/mappings', {
        ...body,
        data_source_id: openCtx.value.dataSourceId,
        line_code: form.value.line_code || undefined,
      })
    }
    msg.success('映射已保存')
    emit('saved')
    close()
  } catch (e: unknown) {
    msg.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function deleteMapping() {
  if (!openCtx.value?.mappingId) return
  if (!confirm('确定删除此字段映射？')) return
  try {
    await api.delete(`/api/mappings/${openCtx.value.mappingId}`)
    msg.success('已删除')
    emit('saved')
    close()
  } catch (e: unknown) {
    msg.error(e instanceof Error ? e.message : '删除失败')
  }
}

watch(activeTab, (tab) => {
  if (tab === 'reuse' && !parts.value.some((p) => p.ref_field_code !== undefined)) {
    parts.value = [defaultRefPart()]
  } else if (tab === 'fetch' && parts.value.every((p) => p.ref_field_code)) {
    parts.value = [defaultSourcePart()]
  }
})

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
    :title="title"
    style="width: min(760px, 96vw); max-height: 90vh"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="loading">加载中…</div>
    <template v-else>
      <NForm label-placement="left" label-width="88" size="small">
        <NFormItem label="显示名">
          <NInput v-model:value="form.line_label" />
        </NFormItem>
        <NFormItem v-if="!openCtx?.mappingId" label="行代码">
          <NInput v-model:value="form.line_code" placeholder="留空自动生成" />
        </NFormItem>
        <NFormItem label="分组">
          <NInput v-model:value="form.report_group" placeholder="报表字段" />
        </NFormItem>
        <NFormItem label="排序">
          <NInputNumber v-model:value="form.sort_order" :min="0" class="w-full" />
        </NFormItem>
      </NForm>

      <NTabs v-model:value="activeTab" type="line" size="small" class="mb-3">
        <NTabPane v-for="t in MAPPING_TABS" :key="t.key" :name="t.key" :tab="t.label" />
      </NTabs>

      <div v-if="activeTab === 'per_order'" class="space-y-3">
        <NFormItem label="每单金额">
          <NInputNumber v-model:value="form.per_order_amount" :min="0" :step="0.01" />
        </NFormItem>
        <NFormItem label="计算基准">
          <NSelect
            v-model:value="form.per_order_basis"
            :options="[
              { label: '当日有效订单数', value: 'valid_orders' },
              { label: '刷单单数', value: 'review_orders' },
            ]"
          />
        </NFormItem>
      </div>

      <div v-else-if="activeTab === 'ratio'" class="space-y-3">
        <NFormItem label="基准字段">
          <NSelect v-model:value="form.ratio_base_code" :options="ratioBaseOptions" filterable />
        </NFormItem>
        <NFormItem label="比例 %">
          <NInputNumber v-model:value="form.ratio_percent" :min="0" :step="0.01" />
        </NFormItem>
      </div>

      <div v-else-if="activeTab === 'placeholder'">
        <p class="text-sm text-slate-500">占位字段，导出后手工填写或上传文件。</p>
      </div>

      <div v-else>
        <MappingPartBlock
          v-for="(part, i) in parts"
          :key="i"
          :part="part"
          :index="i"
          :data-source-id="dataSourceId"
          :mode="activeTab === 'reuse' ? 'reuse' : 'fetch'"
          :reuse-options="reuseOptions"
          @remove="removePart(i)"
        />
        <NButton size="small" dashed block @click="addPart">+ 添加规则</NButton>
      </div>
    </template>

    <template #footer>
      <NSpace justify="space-between" style="width: 100%">
        <NButton v-if="openCtx?.mappingId" type="error" quaternary @click="deleteMapping">删除</NButton>
        <span v-else />
        <NSpace>
          <NButton @click="close">取消</NButton>
          <NButton type="primary" :loading="saving" @click="save">保存</NButton>
        </NSpace>
      </NSpace>
    </template>
  </NModal>
</template>
