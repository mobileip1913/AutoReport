<script setup lang="ts">
import FieldTypeTag from '@/components/FieldTypeTag.vue'
import RuleSummary from '@/components/RuleSummary.vue'

defineProps<{
  rows: Array<Record<string, unknown>>
  dataSourceId: number
  fileLabels?: Record<string, string>
  fieldLabels?: Record<string, string>
  dsSettings?: Record<string, unknown>
  reviewImportCodes?: string[]
  reviewLogisticsCodes?: string[]
}>()

const emit = defineEmits<{
  edit: [Record<string, unknown>]
  delete: [Record<string, unknown>]
}>()
</script>

<template>
  <div class="section-table-card bg-white rounded-xl shadow border border-slate-200 overflow-x-auto mb-4">
    <div class="section-table-header">
      <div class="section-table-header-main">
        <span class="section-table-title">日报字段</span>
        <span class="section-table-count">{{ rows.length }}</span>
      </div>
      <span class="section-table-hint" title="在日报输出页可拖动调整列顺序">可在日报输出页修改顺序</span>
    </div>
    <table class="w-full text-sm min-w-[860px] app-table">
      <thead class="bg-slate-50 text-left text-slate-500 text-xs">
        <tr>
          <th class="px-4 py-2 w-14">Excel</th>
          <th class="px-4 py-2 w-16">类型</th>
          <th class="px-4 py-2">指标名称</th>
          <th class="px-4 py-2">规则摘要</th>
          <th class="px-4 py-2 w-36"></th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="String((row.mapping as Record<string, unknown>)?.id ?? row.line_code)"
          :id="`report-field-${(row.mapping as Record<string, unknown>)?.id}`"
          class="border-t border-slate-100 hover:bg-slate-50 transition-colors"
        >
          <td class="px-4 py-3 font-mono text-xs text-slate-500">{{ row.col }}</td>
          <td class="px-4 py-3">
            <FieldTypeTag :type="String(row.field_type ?? 'fetch')" />
          </td>
          <td class="px-4 py-3">
            <div class="font-medium">{{ row.label }}</div>
            <div class="field-code-hint" :title="`{field:${row.line_code}}`">
              {field:{{ row.line_code }}}
            </div>
          </td>
          <td class="px-4 py-3 text-xs max-w-[320px]">
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
          <td class="px-4 py-3">
            <div class="report-rule-actions">
              <button type="button" class="btn-edit text-link hover:underline text-xs" @click="emit('edit', row)">
                配置
              </button>
              <button
                type="button"
                class="btn-delete-mapping text-link-danger hover:underline text-xs"
                @click="emit('delete', row)"
              >
                删除
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
