<script setup lang="ts">
import { NModal, NButton, NSpace } from 'naive-ui'

defineProps<{ show: boolean; dataSourceId: number }>()
const emit = defineEmits<{ 'update:show': [boolean] }>()

function close() {
  emit('update:show', false)
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="下载导入模板"
    style="width: min(480px, 96vw)"
    @update:show="emit('update:show', $event)"
  >
    <p class="text-sm text-slate-500 mb-4">选择要下载的 Excel 模板，填写后回到日报页导入。</p>
    <NSpace vertical>
      <NButton
        tag="a"
        :href="`/api/data-sources/${dataSourceId}/review-orders/template`"
        target="_blank"
        block
      >
        刷单清单模板
      </NButton>
      <NButton
        tag="a"
        :href="`/api/data-sources/${dataSourceId}/review-logistics/template`"
        target="_blank"
        block
      >
        运费模板
      </NButton>
      <NButton
        tag="a"
        :href="`/api/data-sources/${dataSourceId}/sample-orders/template`"
        target="_blank"
        block
      >
        样品单模板
      </NButton>
    </NSpace>
    <template #footer>
      <NButton @click="close">关闭</NButton>
    </template>
  </NModal>
</template>
