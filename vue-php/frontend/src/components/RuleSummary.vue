<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  row: { field_type?: string; line_code?: string }
  mapping: Record<string, unknown>
  dsId: number
  fileLabels?: Record<string, string>
  fieldLabels?: Record<string, string>
  dsSettings?: Record<string, unknown>
  reviewImportCodes?: string[]
  reviewLogisticsCodes?: string[]
}>()

const m = computed(() => props.mapping)
const fl = computed(() => props.fileLabels ?? {})
const fn = computed(() => props.fieldLabels ?? {})

function partBrief(part: Record<string, unknown>): string {
  const ref = String(part.ref_field_code ?? '').trim()
  if (ref) return fn.value[ref] ?? ref
  const kw = String(part.source_file_keyword ?? '')
  const col = String(part.column_header ?? '')
  const fileLabel = fl.value[kw] ?? kw
  const loc = fileLabel && col ? `${fileLabel}.${col}` : col || fileLabel || '未指定'
  const agg = String(part.aggregation ?? 'sum')
  const aggMap: Record<string, string> = {
    sum: '求和',
    count: '计数',
    count_distinct: '去重计数',
    sum_dedup: '去重求和',
    max_dedup: '去重取最大',
    avg: '平均值',
  }
  return `${loc} · ${aggMap[agg] ?? agg}`
}

const parts = computed(() => {
  const list = (m.value.parts as Array<Record<string, unknown>> | undefined) ?? []
  return [...list].sort((a, b) => ((a.sort_order as number) ?? 0) - ((b.sort_order as number) ?? 0))
})
</script>

<template>
  <template v-if="row.field_type === 'placeholder'">
    <span class="rule-summary-text">占位，导出后手工填写或上传文件</span>
  </template>
  <template v-else-if="row.field_type === 'per_order'">
    <span class="rule-summary-text">
      每单 ${{ m.per_order_amount ?? 0 }} ×
      {{ m.per_order_basis === 'review_orders' ? '刷单单数' : '当日有效订单数' }}
    </span>
  </template>
  <template v-else-if="row.field_type === 'ratio'">
    <span class="rule-summary-text">
      {{ fn[String(m.ratio_base_code)] ?? m.ratio_base_code ?? '基准字段' }} × {{ m.ratio_percent ?? 0 }}%
    </span>
  </template>
  <template v-else-if="row.field_type === 'formula'">
    <span class="rule-summary-text">{{ String(m.expression ?? '公式行').slice(0, 48) }}</span>
  </template>
  <template v-else-if="row.field_type === 'review' || (reviewImportCodes?.includes(row.line_code ?? ''))">
    <span
      v-if="reviewLogisticsCodes?.includes(row.line_code ?? '')"
      class="rule-summary-text"
    >{{ dsSettings?.review_logistics_rule_summary ?? '按单固定 $1/单' }}</span>
    <span v-else class="rule-summary-text">刷单 Excel 导入汇总</span>
  </template>
  <template v-else-if="row.field_type === 'sample'">
    <span class="rule-summary-text">样品单 Excel 导入汇总</span>
  </template>
  <template v-else-if="parts.length">
    <div v-for="(p, i) in parts" :key="i" class="rule-summary-line">
      <span class="rule-summary-text">
        <template v-if="i && p.combine_op === 'subtract'">− </template>
        <template v-else-if="i">＋ </template>
        {{ partBrief(p) }}
      </span>
    </div>
  </template>
  <template v-else>
    <span class="rule-summary-empty">未配置取数</span>
  </template>
</template>
