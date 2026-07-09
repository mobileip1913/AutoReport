<script setup lang="ts">
import { ref, watch } from 'vue'
import { NModal, NButton, NSpace, NInputNumber, NCheckbox } from 'naive-ui'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'

const props = defineProps<{ show: boolean; dataSourceId: number }>()
const emit = defineEmits<{ 'update:show': [boolean]; saved: [] }>()

const msg = useMessage()
const loading = ref(false)
const saving = ref(false)
const importHint = ref('')
const stats = ref({ rows: 0, orders: 0 })
const perOrder = ref(1)
const excludeSameDay = ref(true)
const summary = ref('')

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/api/data-sources/${props.dataSourceId}/settings`)
    perOrder.value = Number(data.review_logistics_per_order ?? 1)
    excludeSameDay.value = data.review_logistics_exclude_same_day_refund !== false
    stats.value = {
      rows: Number(data.review_order_count ?? 0),
      orders: Number(data.review_order_distinct ?? 0),
    }
    summary.value = String(data.review_logistics_rule_summary ?? '')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.show,
  (v) => {
    if (v) {
      importHint.value = ''
      load()
    }
  },
)

function close() {
  emit('update:show', false)
}

async function importFile(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  importHint.value = '导入中…'
  try {
    const { data } = await api.post(
      `/api/data-sources/${props.dataSourceId}/review-orders/import`,
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    stats.value.orders = Number(data.review_order_distinct ?? data.imported ?? 0)
    stats.value.rows = Number(data.review_order_count ?? data.imported ?? 0)
    importHint.value = `已导入 ${data.imported} 行 · ${stats.value.orders} 个刷单订单`
    msg.success('导入成功')
    emit('saved')
  } catch (e: unknown) {
    importHint.value = e instanceof Error ? e.message : '导入失败'
    msg.error(importHint.value)
  }
}

async function save() {
  saving.value = true
  try {
    const { data } = await api.put(`/api/data-sources/${props.dataSourceId}/settings`, {
      review_logistics_mode: 'per_order_fixed',
      review_logistics_per_order: perOrder.value,
      review_logistics_exclude_same_day_refund: excludeSameDay.value,
    })
    summary.value = String(data.review_logistics_rule_summary ?? '')
    msg.success('物流费设置已保存')
    emit('saved')
    close()
  } catch (e: unknown) {
    msg.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="刷单设置"
    style="width: min(520px, 96vw)"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="loading">加载中…</div>
    <template v-else>
      <section class="mb-4">
        <h3 class="text-sm font-medium mb-1">刷单数据 · Excel 导入</h3>
        <p class="text-xs text-slate-500 mb-2">
          模板列：Order ID、SKU ID、刷单金额、佣金、服务费、成本
        </p>
        <NSpace>
          <NButton tag="a" :href="`/api/data-sources/${dataSourceId}/review-orders/template`" target="_blank">
            下载模板
          </NButton>
          <label class="cursor-pointer">
            <NButton tag="span">导入刷单 Excel</NButton>
            <input
              type="file"
              accept=".xlsx"
              class="hidden"
              @change="(e) => { const f = (e.target as HTMLInputElement).files?.[0]; if (f) importFile(f); (e.target as HTMLInputElement).value = '' }"
            />
          </label>
        </NSpace>
        <p v-if="importHint" class="text-xs mt-2" :class="importHint.includes('失败') ? 'text-red-500' : 'text-emerald-600'">
          {{ importHint }}
        </p>
        <p class="text-xs text-slate-500 mt-2">
          当前 {{ stats.rows }} 行 · {{ stats.orders }} 个刷单订单
        </p>
      </section>
      <section class="border-t border-slate-100 pt-4">
        <h3 class="text-sm font-medium mb-1">刷单物流费用 · 每单固定</h3>
        <div class="flex items-center gap-2 mt-2">
          <NInputNumber v-model:value="perOrder" :min="0" :step="0.01" size="small" />
          <span class="text-sm text-slate-500">元 / 单</span>
        </div>
        <NCheckbox v-model:checked="excludeSameDay" class="mt-2">排除当日退单</NCheckbox>
        <p v-if="summary" class="text-xs text-slate-600 mt-2">{{ summary }}</p>
      </section>
    </template>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">取消</NButton>
        <NButton type="primary" :loading="saving" @click="save">保存物流费设置</NButton>
      </NSpace>
    </template>
  </NModal>
</template>
