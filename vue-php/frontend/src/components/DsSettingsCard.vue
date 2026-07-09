<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import { api } from '@/api/client'
import { useMessage } from '@/composables/useMessage'
import { useCatalog } from '@/composables/useCatalog'

declare global {
  interface Window {
    SelectField?: new (
      container: HTMLElement,
      opts: Record<string, unknown>,
    ) => {
      set: (v: string) => void
      setOpts: (opts: unknown[], placeholder?: string) => void
      setDisabled: (d: boolean) => void
      val: () => string
      destroy?: () => void
    }
    SearchCombo?: new (
      container: HTMLElement,
      options: string[],
      opts: Record<string, unknown>,
    ) => {
      set: (v: string) => void
      setOpts: (opts: string[]) => void
      val: () => string
      destroy?: () => void
    }
  }
}

const props = defineProps<{ dataSourceId: number }>()
const emit = defineEmits<{ saved: []; openSchedule: [] }>()

const msg = useMessage()
const settings = ref<Record<string, unknown>>({})
const loading = ref(true)
const saving = ref(false)

const fileHost = ref<HTMLElement | null>(null)
const sheetHost = ref<HTMLElement | null>(null)
const dateColHost = ref<HTMLElement | null>(null)

let fileSelect: InstanceType<NonNullable<typeof window.SelectField>> | null = null
let sheetSelect: InstanceType<NonNullable<typeof window.SelectField>> | null = null
let dateColCombo: InstanceType<NonNullable<typeof window.SearchCombo>> | null = null

const scheduleLabel = computed(() => {
  const t = String(settings.value.daily_generate_at ?? '')
  return t || '未设置'
})

const dsIdFn = () => props.dataSourceId
const { loadFiles, fileOptions, loadSheets: fetchSheetNames, loadColumns } = useCatalog(dsIdFn)

function loadScript(src: string): Promise<void> {
  if (document.querySelector(`script[src="${src}"]`)) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = src
    s.onload = () => resolve()
    s.onerror = () => reject(new Error(`load ${src} failed`))
    document.head.appendChild(s)
  })
}

async function loadSheets(fileKw: string, keepSheet = '') {
  if (!fileKw) {
    sheetSelect?.setOpts([], '请先选择来源文件')
    sheetSelect?.setDisabled(true)
    dateColCombo?.setOpts([])
    dateColCombo?.set('')
    return
  }
  const sheets = await fetchSheetNames(fileKw)
  sheetSelect?.setOpts(sheets, sheets.length ? '请选择 Sheet' : '该文件无 Sheet')
  sheetSelect?.setDisabled(!sheets.length)
  const sheet = keepSheet && sheets.includes(keepSheet) ? keepSheet : ''
  sheetSelect?.set(sheet)
}

async function loadCols(fileKw: string, sheet: string, keepCol = '') {
  if (!fileKw || !sheet) {
    dateColCombo?.setOpts([])
    dateColCombo?.set('')
    return
  }
  const cols = await loadColumns(fileKw, sheet)
  dateColCombo?.setOpts(cols)
  dateColCombo?.set(keepCol && cols.includes(keepCol) ? keepCol : '')
}

function initControls() {
  if (!fileHost.value || !sheetHost.value || !dateColHost.value) return
  if (!window.SelectField || !window.SearchCombo) return

  fileSelect?.destroy?.()
  sheetSelect?.destroy?.()
  dateColCombo?.destroy?.()

  fileSelect = new window.SelectField(fileHost.value, {
    placeholder: '请选择来源文件',
    options: fileOptions(),
    size: 'md',
    onChange: (fileKw: string) => {
      settings.value.order_file = fileKw
      loadSheets(fileKw, '')
      loadCols(fileKw, '', '')
    },
  })

  sheetSelect = new window.SelectField(sheetHost.value, {
    placeholder: '请先选择来源文件',
    options: [],
    size: 'md',
    onChange: (sheet: string) => {
      settings.value.order_sheet = sheet
      loadCols(String(settings.value.order_file ?? ''), sheet, '')
    },
  })
  sheetSelect.setDisabled(true)

  dateColCombo = new window.SearchCombo(dateColHost.value, [], {
    placeholder: '搜索列头，如 Time',
    emptyHint: '请先选择 Sheet',
    noMatchHint: '无匹配列头',
    size: 'md',
    onPick: (col: string) => {
      settings.value.order_date_col = col
    },
  })
}

async function applySettingsToControls() {
  const initial = settings.value
  const kw = String(initial.order_file ?? '')
  if (kw) fileSelect?.set(kw)
  await loadSheets(kw, String(initial.order_sheet ?? ''))
  await loadCols(kw, String(initial.order_sheet ?? ''), String(initial.order_date_col ?? ''))
}

async function loadSettings() {
  loading.value = true
  try {
    await loadScript('/static/form_controls.js')
    await loadFiles()
    const { data } = await api.get(`/api/data-sources/${props.dataSourceId}/settings`)
    settings.value = data
    loading.value = false
    await nextTick()
    initControls()
    await applySettingsToControls()
  } catch (e: unknown) {
    msg.error(e instanceof Error ? e.message : '加载失败')
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const body = {
      ...settings.value,
      order_file: fileSelect?.val() || null,
      order_sheet: sheetSelect?.val() || null,
      order_date_col: dateColCombo?.val() || null,
    }
    const { data } = await api.put(`/api/data-sources/${props.dataSourceId}/settings`, body)
    settings.value = data
    msg.success('数据源设置已保存')
    emit('saved')
  } catch (e: unknown) {
    msg.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

function onScheduleSaved(time: string) {
  settings.value.daily_generate_at = time
}

watch(
  () => props.dataSourceId,
  () => loadSettings(),
  { immediate: false },
)

onMounted(loadSettings)
onBeforeUnmount(() => {
  fileSelect?.destroy?.()
  sheetSelect?.destroy?.()
  dateColCombo?.destroy?.()
})

defineExpose({ onScheduleSaved, reload: loadSettings })
</script>

<template>
  <div
    class="ds-settings-card bg-white rounded-xl shadow border border-slate-200 mb-4"
    :data-ds-id="dataSourceId"
  >
    <div v-if="loading" class="px-4 py-6 text-sm text-slate-400">加载中…</div>
    <div v-else class="ds-settings-body px-4 py-3">
      <div class="ds-settings-main min-w-0">
        <div class="ds-settings-head flex flex-wrap items-start justify-between gap-3 mb-2">
          <div class="ds-settings-head-title">
            <span class="section-inline-title">主表与筛选时间</span>
            <span class="text-xs text-slate-500">跨表关联与样品/刷单排除均以此为准</span>
          </div>
          <div class="ds-settings-head-actions">
            <span class="ds-timezone-label">Asia/Shanghai</span>
            <button
              type="button"
              class="btn-open-schedule px-3 py-1.5 border border-slate-200 rounded-lg text-sm hover:bg-slate-50 text-slate-700 whitespace-nowrap"
              @click="emit('openSchedule')"
            >
              每日自动生成 · <span class="ds-schedule-label">{{ scheduleLabel }}</span>
            </button>
            <button
              type="button"
              class="btn-save-ds-settings px-4 py-1.5 btn-primary text-sm whitespace-nowrap"
              :disabled="saving"
              @click="save"
            >
              {{ saving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
        <div class="ds-baseline-grid">
          <div class="ds-field">
            <label class="ds-field-label">来源文件</label>
            <div ref="fileHost" class="ds-order-file-host" />
          </div>
          <div class="ds-field">
            <label class="ds-field-label">Sheet</label>
            <div ref="sheetHost" class="ds-order-sheet-host" />
          </div>
          <div class="ds-field">
            <label class="ds-field-label">日期列</label>
            <div ref="dateColHost" class="ds-order-date-col-host" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
