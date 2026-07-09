<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/session'

const props = withDefaults(
  defineProps<{ variant?: 'default' | 'daily-hub' | 'compact' }>(),
  { variant: 'default' },
)

const session = useSessionStore()
const stores = computed(() => session.data?.accessible_stores ?? [])
const currentId = computed(() => session.data?.current_store?.id ?? '')

async function onChange(ev: Event) {
  const id = Number((ev.target as HTMLSelectElement).value)
  if (id) await session.setStore(id)
}
</script>

<template>
  <form
    v-if="stores.length"
    :class="
      variant === 'daily-hub'
        ? 'daily-hub__store-form'
        : 'flex flex-wrap items-center gap-2 min-w-0'
    "
    @submit.prevent
  >
    <span v-if="variant === 'default'" class="text-xs font-medium text-slate-500 shrink-0">店铺</span>
    <label v-else-if="variant === 'daily-hub'" class="daily-hub__store-label" for="dailyStoreSelect">当前店铺</label>
    <select
      id="dailyStoreSelect"
      :class="
        variant === 'daily-hub'
          ? 'daily-hub__store-select store-bind-select'
          : 'store-bind-select border rounded-lg px-3 py-2 text-sm min-w-[220px] max-w-full'
      "
      :aria-label="variant === 'compact' ? '选择店铺' : undefined"
      :value="currentId"
      @change="onChange"
    >
      <option v-for="s in stores" :key="s.id" :value="s.id">{{ s.name }} · {{ s.platform }}</option>
    </select>
  </form>
</template>
