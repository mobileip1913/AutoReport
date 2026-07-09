<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  parseIsoDate,
  formatIsoDate,
  formatDateDisplay,
  calendarDays,
  DATE_FIELD_WEEKDAYS,
} from '@/utils/dateField'

const model = defineModel<string>({ default: '' })
const emit = defineEmits<{ change: [string] }>()

const open = ref(false)
const view = ref(new Date())
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const panelStyle = ref<Record<string, string>>({})

const display = computed(() => formatDateDisplay(model.value))
const monthLabel = computed(() => {
  const y = view.value.getFullYear()
  const m = view.value.getMonth()
  return `${y}年${String(m + 1).padStart(2, '0')}月`
})

const days = computed(() => {
  const y = view.value.getFullYear()
  const m = view.value.getMonth()
  const todayIso = formatIsoDate(new Date())
  return calendarDays(y, m).map((d) => {
    const iso = formatIsoDate(d)
    return {
      iso,
      day: d.getDate(),
      outside: d.getMonth() !== m,
      selected: iso === model.value,
      today: iso === todayIso,
    }
  })
})

watch(
  () => model.value,
  (v) => {
    const d = parseIsoDate(v)
    if (d) view.value = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  },
  { immediate: true },
)

function positionPanel() {
  if (!trigger.value) return
  const rect = trigger.value.getBoundingClientRect()
  const panelW = 280
  const margin = 10
  const left = Math.max(margin, Math.min(rect.left, window.innerWidth - panelW - margin))
  const spaceBelow = window.innerHeight - rect.bottom - margin
  const spaceAbove = rect.top - margin
  const openDown = spaceBelow >= 300 || spaceBelow >= spaceAbove
  panelStyle.value = {
    width: `${panelW}px`,
    left: `${left}px`,
    top: openDown ? `${rect.bottom + 6}px` : 'auto',
    bottom: openDown ? 'auto' : `${window.innerHeight - rect.top + 6}px`,
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) {
    const selected = parseIsoDate(model.value)
    if (selected) view.value = new Date(selected.getFullYear(), selected.getMonth(), selected.getDate())
    requestAnimationFrame(positionPanel)
  }
}

function pick(iso: string) {
  model.value = iso
  emit('change', iso)
  open.value = false
}

function prevMonth() {
  const y = view.value.getFullYear()
  const m = view.value.getMonth()
  view.value = new Date(y, m - 1, 1)
}

function nextMonth() {
  const y = view.value.getFullYear()
  const m = view.value.getMonth()
  view.value = new Date(y, m + 1, 1)
}

function onOutside(e: MouseEvent) {
  if (!open.value) return
  const t = e.target as Node
  if (root.value?.contains(t)) return
  const panel = document.getElementById('report-date-panel')
  if (panel?.contains(t)) return
  open.value = false
}

onMounted(() => document.addEventListener('mousedown', onOutside))
onUnmounted(() => document.removeEventListener('mousedown', onOutside))
</script>

<template>
  <div ref="root" class="date-field">
    <input type="hidden" name="report_date" :value="model" />
    <button
      ref="trigger"
      type="button"
      class="date-field__trigger form-control form-control--md"
      :class="{ 'is-open': open, 'date-field__trigger--placeholder': !model }"
      aria-haspopup="dialog"
      :aria-expanded="open ? 'true' : 'false'"
      @click="toggle"
    >
      <span class="date-field__value tabular-nums">{{ display }}</span>
      <span class="date-field__icon" aria-hidden="true">
        <svg viewBox="0 0 20 20" fill="none">
          <path
            d="M6 2.5v1.5M14 2.5v1.5M4.25 4.75h11.5M5.5 3.75h9a1.25 1.25 0 0 1 1.25 1.25v10.5A1.25 1.25 0 0 1 14.5 16.75h-5A1.25 1.25 0 0 1 8.25 15.5V5a1.25 1.25 0 0 1 1.25-1.25Z"
            stroke="currentColor"
            stroke-width="1.35"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
    </button>
    <Teleport to="body">
      <div
        v-show="open"
        id="report-date-panel"
        class="date-field__panel"
        :class="{ 'is-open': open }"
        :style="panelStyle"
        role="dialog"
        aria-label="选择日期"
      >
        <header class="date-field__header">
          <button type="button" class="date-field__nav" aria-label="上个月" @click="prevMonth">
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path
                d="M12.5 5 7.5 10l5 5"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </button>
          <span class="date-field__month tabular-nums">{{ monthLabel }}</span>
          <button type="button" class="date-field__nav" aria-label="下个月" @click="nextMonth">
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path
                d="M7.5 5 12.5 10l-5 5"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </button>
        </header>
        <div class="date-field__weekdays">
          <span v-for="w in DATE_FIELD_WEEKDAYS" :key="w">{{ w }}</span>
        </div>
        <div class="date-field__grid" role="grid">
          <button
            v-for="d in days"
            :key="d.iso"
            type="button"
            class="date-field__day"
            :class="{
              'is-outside': d.outside,
              'is-selected': d.selected,
              'is-today': d.today && !d.selected,
            }"
            role="gridcell"
            @click="pick(d.iso)"
          >
            {{ d.day }}
          </button>
        </div>
        <footer class="date-field__footer">
          <button type="button" class="date-field__footer-btn" @click="pick('')">清除</button>
          <button
            type="button"
            class="date-field__footer-btn date-field__footer-btn--primary"
            @click="pick(formatIsoDate(new Date()))"
          >
            今天
          </button>
        </footer>
      </div>
    </Teleport>
  </div>
</template>
