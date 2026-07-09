<script setup lang="ts">
import { ref } from 'vue'
import RuleSummary from '@/components/RuleSummary.vue'

defineProps<{
  items: Array<Record<string, unknown>>
  dataSourceId: number
  fileLabels?: Record<string, string>
  fieldLabels?: Record<string, string>
  dsSettings?: Record<string, unknown>
  reviewImportCodes?: string[]
  reviewLogisticsCodes?: string[]
}>()

const emit = defineEmits<{ edit: [Record<string, unknown>]; delete: [number] }>()

const expanded = ref(true)
const bannerDismissed = ref(false)
</script>

<template>
  <div
    :id="`aux-fields-${dataSourceId}`"
    class="section-table-card bg-white rounded-xl shadow border border-slate-200 overflow-hidden mb-4"
    :data-ds-id="dataSourceId"
  >
    <button
      type="button"
      class="section-table-header section-table-header--toggle aux-fields-toggle w-full text-left"
      :aria-expanded="expanded"
      :aria-controls="`aux-body-${dataSourceId}`"
      @click="expanded = !expanded"
    >
      <div class="section-table-header-main">
        <span class="section-table-title">基础取数字段</span>
        <span class="section-table-count">{{ items.length }}</span>
        <span class="field-type-tag field-type-tag--aux">基础取值数据</span>
      </div>
      <span class="section-table-chevron" aria-hidden="true">›</span>
    </button>
    <div v-if="!bannerDismissed" class="aux-first-use-banner" :data-ds-id="dataSourceId" role="note">
      <div class="aux-first-use-banner-body">
        <strong>初次配置？</strong>
        <span>组合指标（如实际支付金额）会引用此处的基础字段。请先配置基础取数，再编辑上方日报字段。</span>
      </div>
      <button type="button" class="aux-first-use-dismiss" aria-label="知道了" @click="bannerDismissed = true">
        知道了
      </button>
    </div>
    <div v-show="expanded" :id="`aux-body-${dataSourceId}`" class="aux-fields-body overflow-x-auto">
      <table class="w-full text-sm min-w-[720px] app-table">
        <thead class="bg-slate-50 text-left text-slate-500 text-xs">
          <tr>
            <th class="px-4 py-2">字段名称</th>
            <th class="px-4 py-2">规则摘要</th>
            <th class="px-4 py-2 w-36"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="String((item.mapping as Record<string, unknown>)?.id ?? item.line_code)"
            :id="`aux-field-${(item.mapping as Record<string, unknown>)?.id}`"
            class="border-t border-slate-100 hover:bg-slate-50 transition-colors"
          >
            <td class="px-4 py-3">
              <div class="font-medium">{{ item.label }}</div>
              <div class="field-code-hint" :title="`{field:${item.line_code}}`">
                {field:{{ item.line_code }}}
              </div>
            </td>
            <td class="px-4 py-3 text-xs max-w-[320px]">
              <RuleSummary
                :row="item"
                :mapping="(item.mapping as Record<string, unknown>) ?? {}"
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
                <button type="button" class="btn-edit text-link hover:underline text-xs" @click="emit('edit', item)">
                  配置
                </button>
                <button
                  type="button"
                  class="btn-delete-mapping text-link-danger hover:underline text-xs"
                  @click="emit('delete', Number((item.mapping as Record<string, unknown>).id))"
                >
                  删除
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
