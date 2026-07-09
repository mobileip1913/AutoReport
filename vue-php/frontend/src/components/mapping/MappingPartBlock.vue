<script setup lang="ts">
import { ref, watch } from 'vue'
import { NSelect, NInput, NSpace, NButton, NCheckbox } from 'naive-ui'
import type { MappingPart } from '@/utils/mappingConstants'
import { AGG_OPTIONS } from '@/utils/mappingConstants'
import { useCatalog } from '@/composables/useCatalog'

const props = defineProps<{
  part: MappingPart
  dataSourceId: number
  index: number
  mode: 'fetch' | 'reuse'
  reuseOptions: Array<{ label: string; value: string }>
}>()

const emit = defineEmits<{ remove: [] }>()

const sheetOpts = ref<{ label: string; value: string }[]>([])
const colOpts = ref<{ label: string; value: string }[]>([])

const { fileOptions, sheetOptions, columnOptions, loadFiles } = useCatalog(() => props.dataSourceId)

watch(
  () => props.dataSourceId,
  () => loadFiles(),
  { immediate: true },
)

watch(
  () => props.part.source_file_keyword,
  async (kw) => {
    if (!kw) {
      sheetOpts.value = []
      return
    }
    sheetOpts.value = await sheetOptions(kw)
  },
  { immediate: true },
)

watch(
  () => [props.part.source_file_keyword, props.part.sheet_name] as const,
  async ([kw, sh]) => {
    if (!kw || !sh) {
      colOpts.value = []
      return
    }
    colOpts.value = await columnOptions(kw, sh)
  },
  { immediate: true },
)

function toggleOp() {
  props.part.combine_op = props.part.combine_op === 'subtract' ? 'add' : 'subtract'
}
</script>

<template>
  <div class="mapping-part-block border border-slate-200 rounded-lg p-3 mb-2 bg-slate-50">
    <div class="flex items-center gap-2 mb-2">
      <NButton v-if="index > 0" size="tiny" quaternary @click="toggleOp">
        {{ part.combine_op === 'subtract' ? '−' : '+' }}
      </NButton>
      <span class="text-xs text-slate-500">规则 {{ index + 1 }}</span>
      <NButton size="tiny" type="error" quaternary class="ml-auto" @click="emit('remove')">删除</NButton>
    </div>

    <template v-if="mode === 'reuse'">
      <NSelect
        v-model:value="part.ref_field_code"
        :options="reuseOptions"
        filterable
        placeholder="选择要复用的字段"
      />
    </template>

    <NSpace v-else vertical>
      <NSelect
        v-model:value="part.source_file_keyword"
        :options="fileOptions()"
        filterable
        placeholder="来源文件"
        @update:value="
          () => {
            part.sheet_name = ''
            part.column_header = ''
          }
        "
      />
      <NSelect
        v-model:value="part.sheet_name"
        :options="sheetOpts"
        filterable
        placeholder="Sheet"
        @update:value="() => (part.column_header = '')"
      />
      <NSelect
        v-model:value="part.column_header"
        :options="colOpts"
        filterable
        tag
        placeholder="列名"
      />
      <NSelect v-model:value="part.aggregation" :options="AGG_OPTIONS" />
      <NCheckbox v-model:checked="part.join_to_orders">关联到订单主表</NCheckbox>
      <NInput
        v-if="part.join_to_orders"
        :value="(part.join_keys || []).join(', ')"
        placeholder="匹配键，逗号分隔，如 Order ID"
        @update:value="(v) => (part.join_keys = v.split(',').map((s) => s.trim()).filter(Boolean))"
      />
    </NSpace>
  </div>
</template>
