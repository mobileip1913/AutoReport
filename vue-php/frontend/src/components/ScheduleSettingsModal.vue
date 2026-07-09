<script setup lang="ts">
import { ref, watch } from 'vue'
import { NModal, NButton, NSpace } from 'naive-ui'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'

const props = defineProps<{ show: boolean; dataSourceId: number }>()
const emit = defineEmits<{ 'update:show': [boolean]; saved: [string] }>()

const msg = useMessage()
const hour = ref('')
const minute = ref('')
const display = ref('未设置')
const saving = ref(false)

const hours = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'))
const minutes = Array.from({ length: 12 }, (_, i) => String(i * 5).padStart(2, '0'))

function applyTime(val: string) {
  if (val && /^\d{1,2}:\d{1,2}/.test(val)) {
    const [h, m] = val.split(':')
    hour.value = String(parseInt(h, 10)).padStart(2, '0')
    minute.value = String(parseInt(m, 10)).padStart(2, '0')
    display.value = `${hour.value}:${minute.value}`
  } else {
    hour.value = ''
    minute.value = ''
    display.value = '未设置'
  }
}

watch(
  () => props.show,
  async (v) => {
    if (!v) return
    const { data } = await api.get(`/api/data-sources/${props.dataSourceId}/settings`)
    applyTime(String(data.daily_generate_at ?? ''))
  },
)

watch([hour, minute], () => {
  if (hour.value && minute.value) display.value = `${hour.value}:${minute.value}`
})

function clear() {
  hour.value = ''
  minute.value = ''
  display.value = '未设置'
}

function close() {
  emit('update:show', false)
}

async function save() {
  saving.value = true
  try {
    const time = hour.value && minute.value ? `${hour.value}:${minute.value}` : ''
    const { data } = await api.put(`/api/data-sources/${props.dataSourceId}/settings`, {
      daily_generate_at: time || null,
    })
    const saved = String(data.daily_generate_at ?? '')
    applyTime(saved)
    msg.success('定时设置已保存')
    emit('saved', saved)
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
    title="每日自动生成"
    style="width: min(420px, 96vw)"
    @update:show="emit('update:show', $event)"
  >
    <p class="text-xs text-slate-500 mb-3">Asia/Shanghai 时区；未设置则不自动生成</p>
    <div class="flex justify-between items-center mb-3">
      <span class="text-lg font-mono font-semibold tabular-nums">{{ display }}</span>
      <NButton size="tiny" quaternary @click="clear">清除</NButton>
    </div>
    <div class="mb-2 text-xs text-slate-500">小时</div>
    <div class="flex flex-wrap gap-1 mb-4">
      <button
        v-for="h in hours"
        :key="h"
        type="button"
        class="ds-time-option px-2 py-1 text-xs rounded border"
        :class="{ 'is-active bg-sky-100 border-sky-300': hour === h }"
        @click="hour = h"
      >
        {{ h }}
      </button>
    </div>
    <div class="mb-2 text-xs text-slate-500">分钟</div>
    <div class="flex flex-wrap gap-1">
      <button
        v-for="m in minutes"
        :key="m"
        type="button"
        class="ds-time-option px-2 py-1 text-xs rounded border"
        :class="{ 'is-active bg-sky-100 border-sky-300': minute === m }"
        @click="minute = m"
      >
        {{ m }}
      </button>
    </div>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">取消</NButton>
        <NButton type="primary" :loading="saving" @click="save">保存</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped>
.ds-time-option.is-active {
  font-weight: 600;
}
</style>
