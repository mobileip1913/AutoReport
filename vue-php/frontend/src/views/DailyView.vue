<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NSpin } from 'naive-ui'
import { api } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { useMessage } from '@/composables/useMessage'
import ReportDateField from '@/components/ReportDateField.vue'
import StoreSelect from '@/components/StoreSelect.vue'
import DailyFieldsModal from '@/components/DailyFieldsModal.vue'
import TemplateDownloadModal from '@/components/TemplateDownloadModal.vue'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const msg = useMessage()

const loading = ref(true)
const error = ref('')
const busy = ref(false)
const bootstrap = ref<Record<string, unknown> | null>(null)
const reportDate = ref('')
const importHint = ref('')
const fieldsModalShow = ref(false)
const templateModalShow = ref(false)
const fieldsModal = ref<InstanceType<typeof DailyFieldsModal> | null>(null)

const activeDsId = computed(() => {
  const id = bootstrap.value?.active_ds_id as number | undefined
  if (id) return id
  return session.data?.current_store?.data_source_id ?? 0
})

const storeName = computed(() => {
  const cfg = bootstrap.value?.ds_settings as Record<number, { store_name?: string }> | undefined
  const sid = activeDsId.value
  if (cfg && sid && cfg[sid]?.store_name) return cfg[sid].store_name!
  return session.data?.current_store?.name ?? ''
})

const run = computed(
  () => bootstrap.value?.run as { id: number; report_date: string } | null | undefined,
)

const excelRows = computed(
  () => (bootstrap.value?.excel_rows as Array<Record<string, unknown>> | undefined) ?? [],
)

const fileLabels = computed(() => {
  const id = activeDsId.value
  if (!id) return {}
  return (
    (bootstrap.value?.file_labels_by_ds as Record<number, Record<string, string>>)?.[id] ?? {}
  )
})

const fieldLabels = computed(() => {
  const id = activeDsId.value
  if (!id) return {}
  return (
    (bootstrap.value?.field_labels_by_ds as Record<number, Record<string, string>>)?.[id] ?? {}
  )
})

const dsSettingsEntry = computed(() => {
  const id = activeDsId.value
  if (!id) return {}
  return (
    (bootstrap.value?.ds_settings as Record<number, Record<string, unknown>>)?.[id] ?? {}
  )
})

const reviewImportCodes = computed(
  () => (bootstrap.value?.review_import_codes as string[]) ?? [],
)
const reviewLogisticsCodes = computed(
  () => (bootstrap.value?.review_logistics_codes as string[]) ?? [],
)

const defaultReportDate = computed(() => String(bootstrap.value?.default_report_date ?? ''))

const showRunStatus = computed(
  () => run.value && run.value.report_date === (reportDate.value || defaultReportDate.value),
)

async function loadBootstrap() {
  loading.value = true
  error.value = ''
  const runId = route.query.run_id
  const q = runId ? `?run_id=${runId}` : ''
  try {
    const { data } = await api.get(`/api/daily/bootstrap${q}`)
    bootstrap.value = data
    const d = (data.default_report_date as string) || ''
    reportDate.value = run.value?.report_date ?? d
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadBootstrap)
watch(() => route.query.run_id, loadBootstrap)
watch(
  () => session.data?.current_store?.id,
  () => loadBootstrap(),
)

async function generate(e: Event) {
  e.preventDefault()
  if (!reportDate.value || !activeDsId.value) return
  busy.value = true
  try {
    const { data } = await api.post('/api/generate', {
      data_source_id: activeDsId.value,
      report_date: reportDate.value,
      store_name: storeName.value,
      is_test: true,
    })
    const runId = data.run_id ?? data.id
    msg.success(`已生成 run #${runId}`)
    router.push({ path: '/daily', query: { run_id: String(runId) } })
    window.open(`/daily/${runId}/export`, '_blank')
  } catch (e: unknown) {
    msg.error(e instanceof Error ? e.message : '生成失败')
  } finally {
    busy.value = false
  }
}

async function importFile(kind: 'review' | 'logistics' | 'sample', file: File) {
  if (!activeDsId.value) return
  const paths = {
    review: `/api/data-sources/${activeDsId.value}/review-orders/import`,
    logistics: `/api/data-sources/${activeDsId.value}/review-logistics/import`,
    sample: `/api/data-sources/${activeDsId.value}/sample-orders/import`,
  }
  const fd = new FormData()
  fd.append('file', file)
  try {
    const { data } = await api.post(paths[kind], fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    importHint.value = data.message ?? `已导入 ${data.imported ?? ''} 条`
    msg.success('导入成功')
    await loadBootstrap()
  } catch (e: unknown) {
    msg.error(e instanceof Error ? e.message : '导入失败')
  }
}

function onFile(kind: 'review' | 'logistics' | 'sample', ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) importFile(kind, file)
  input.value = ''
}

function openFieldsModal() {
  fieldsModalShow.value = true
  fieldsModal.value?.openWith(excelRows.value)
}

function syncRunStatus(iso?: string) {
  void (iso ?? reportDate.value)
}

function exportSku() {
  if (run.value) {
    window.open(`/daily/${run.value.id}/export-sku`, '_blank')
  } else {
    msg.info('请先生成日报')
  }
}
</script>

<template>
  <div>
    <NSpin v-if="loading" />
    <NAlert v-else-if="error" type="error" :title="error" class="mb-4" />
    <template v-else-if="activeDsId">
      <section class="daily-hub" aria-labelledby="daily-hub-title">
        <div class="daily-hub__ambient" aria-hidden="true">
          <span class="daily-hub__orb daily-hub__orb--a"></span>
          <span class="daily-hub__orb daily-hub__orb--b"></span>
          <span class="daily-hub__orb daily-hub__orb--c"></span>
        </div>

        <header class="daily-hub__hero">
          <h1 id="daily-hub-title" class="daily-hub__title">日报输出</h1>
          <StoreSelect variant="daily-hub" />
          <div
            v-if="run && showRunStatus"
            id="dailyRunStatus"
            class="daily-hub__status"
            :data-run-date="run.report_date"
          >
            <span class="daily-status-pill">
              <span class="daily-status-pill__dot" aria-hidden="true"></span>
              <span class="tabular-nums">已生成 {{ run.report_date }} · #{{ run.id }}</span>
            </span>
            <span id="saveStatus" class="daily-hub__sync">已同步</span>
          </div>
        </header>

        <form class="daily-workflow" @submit="generate">
          <input type="hidden" name="data_source_id" :value="activeDsId" />

          <div class="daily-workflow__track">
            <article class="daily-flow-step daily-flow-step--date daily-flow-step--enter-1">
              <div class="daily-flow-step__head">
                <span class="daily-flow-step__badge" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M6.75 3v2.25M17.25 3v2.25M3 9.75h18M4.5 6.75h15a1.5 1.5 0 011.5 1.5v12a1.5 1.5 0 01-1.5 1.5h-15a1.5 1.5 0 01-1.5-1.5v-12a1.5 1.5 0 011.5-1.5z"
                    />
                  </svg>
                </span>
                <span class="daily-flow-step__index" aria-hidden="true">01</span>
              </div>
              <h2 class="daily-flow-step__title">选择日期</h2>
              <p class="daily-flow-step__desc">指定要汇总的报表日期，后续导入与导出均以此为准。</p>
              <div class="daily-flow-step__body">
                <ReportDateField v-model="reportDate" @change="syncRunStatus" />
              </div>
            </article>

            <div class="daily-workflow__bridge" aria-hidden="true">
              <span class="daily-workflow__bridge-line"></span>
              <span class="daily-workflow__bridge-dot"></span>
              <span class="daily-workflow__bridge-line"></span>
            </div>

            <article class="daily-flow-step daily-flow-step--import daily-flow-step--enter-2">
              <div class="daily-flow-step__head">
                <span class="daily-flow-step__badge" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M7.5 10.5L12 15m0 0l4.5-4.5M12 15V3"
                    />
                  </svg>
                </span>
                <span class="daily-flow-step__index" aria-hidden="true">02</span>
              </div>
              <h2 class="daily-flow-step__title">辅助数据</h2>
              <p class="daily-flow-step__desc">下载模板后导入刷单、运费或样品单，再重新生成日报。</p>
              <div class="daily-flow-step__body">
                <div class="daily-import-grid">
                  <button
                    type="button"
                    class="daily-import-tile daily-import-tile--template"
                    @click="templateModalShow = true"
                  >
                    <span class="daily-import-tile__icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M7.5 10.5L12 15m0 0l4.5-4.5M12 15V3"/>
                      </svg>
                    </span>
                    <span class="daily-import-tile__label">下载模板</span>
                  </button>
                  <label class="daily-import-tile">
                    <span class="daily-import-tile__icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9.75m3 0h3.75m-3.75 0v-3.375m0 3.375h3.75m-9.75 0H5.625c-.621 0-1.125-.504-1.125-1.125V5.25c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125v3.75m0 9.75h3.75"/>
                      </svg>
                    </span>
                    <span class="daily-import-tile__label">导入刷单</span>
                    <input type="file" accept=".xlsx" class="hidden" @change="onFile('review', $event)" />
                  </label>
                  <label class="daily-import-tile">
                    <span class="daily-import-tile__icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9m9 9H18.375a1.125 1.125 0 011.125 1.125v3.375c0 .621-.504 1.125-1.125 1.125H14.25"/>
                      </svg>
                    </span>
                    <span class="daily-import-tile__label">导入运费</span>
                    <input type="file" accept=".xlsx" class="hidden" @change="onFile('logistics', $event)" />
                  </label>
                  <label class="daily-import-tile">
                    <span class="daily-import-tile__icon" aria-hidden="true">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M21 11.25v8.25a1.5 1.5 0 01-1.5 1.5H4.5a1.5 1.5 0 01-1.5-1.5v-8.25M12 4.875A2.625 2.625 0 109.375 7.5H12m0-2.625V7.5m0-2.625A2.625 2.625 0 1114.625 7.5H12m0 0V21m-8.625-9.75h18c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125h-18c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"/>
                      </svg>
                    </span>
                    <span class="daily-import-tile__label">导入样品单</span>
                    <input type="file" accept=".xlsx" class="hidden" @change="onFile('sample', $event)" />
                  </label>
                </div>
                <p v-if="importHint" class="daily-import-hint">{{ importHint }}</p>
              </div>
            </article>

            <div class="daily-workflow__bridge" aria-hidden="true">
              <span class="daily-workflow__bridge-line"></span>
              <span class="daily-workflow__bridge-dot"></span>
              <span class="daily-workflow__bridge-line"></span>
            </div>

            <article class="daily-flow-step daily-flow-step--actions daily-flow-step--enter-3">
              <div class="daily-flow-step__head">
                <span class="daily-flow-step__badge" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-2.25v3.75"
                    />
                  </svg>
                </span>
                <span class="daily-flow-step__index" aria-hidden="true">03</span>
              </div>
              <h2 class="daily-flow-step__title">生成与导出</h2>
              <p class="daily-flow-step__desc">生成完成后将自动下载 Excel，也可提前设置字段或导出 SKU 销量。</p>
              <div class="daily-flow-step__body daily-flow-step__body--actions">
                <button
                  type="submit"
                  id="btnGenerateDaily"
                  class="daily-generate-btn btn-primary"
                  :class="{ 'is-busy': busy }"
                  :disabled="busy"
                >
                  <span class="daily-generate-btn__idle" :hidden="busy">
                    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                      <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88A.75.75 0 008 11.25v1.5a.75.75 0 00.75.75h4.5a.75.75 0 00.53-.22l3-3a.75.75 0 00-1.06-1.06l-2.47 2.47-2.776-3.62zm-7.857 4.809a.75.75 0 01.75-.75h.008a.75.75 0 01.75.75v.008a.75.75 0 01-.75.75h-.008a.75.75 0 01-.75-.75v-.008z" clip-rule="evenodd"/>
                    </svg>
                    生成日报
                  </span>
                  <span class="daily-generate-btn__busy" :hidden="!busy">
                    <span class="daily-generate-spinner" aria-hidden="true"></span>
                    生成中…
                  </span>
                </button>
                <div class="daily-action-row">
                  <button
                    v-if="excelRows.length"
                    type="button"
                    id="btnOpenDailyFields"
                    class="daily-action-chip"
                    @click="openFieldsModal"
                  >
                    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M7.84 1.804A1 1 0 018.82 1h2.36a1 1 0 01.98.804l.331 1.652a6.993 6.993 0 011.929 1.115l1.598-.54a1 1 0 011.186.447l1.18 2.044a1 1 0 01-.205 1.251l-1.267 1.113a7.047 7.047 0 010 2.228l1.267 1.113a1 1 0 01.206 1.25l-1.18 2.045a1 1 0 01-1.187.447l-1.598-.54a6.993 6.993 0 01-1.929 1.115l-.33 1.652a1 1 0 01-.98.804H8.82a1 1 0 01-.98-.804l-.331-1.652a6.957 6.957 0 01-1.929-1.115l-1.598.54a1 1 0 01-1.186-.447l-1.18-2.044a1 1 0 01.205-1.251l1.267-1.114a7.05 7.05 0 010-2.227L1.821 7.773a1 1 0 01-.205-1.25l1.18-2.045a1 1 0 011.187-.447l1.598.54A6.993 6.993 0 017.51 3.456l.33-1.652zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd"/></svg>
                    设置日报字段
                  </button>
                  <button type="button" id="btnExportSkuSales" class="daily-action-chip" @click="exportSku">
                    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/></svg>
                    导出 SKU 销量
                  </button>
                </div>
              </div>
            </article>
          </div>
        </form>

        <p v-if="!run" class="daily-hub__footnote">
          选择日期后点击「生成日报」，完成后将自动下载 Excel。
        </p>
      </section>

      <TemplateDownloadModal v-model:show="templateModalShow" :data-source-id="activeDsId" />
      <DailyFieldsModal
        ref="fieldsModal"
        v-model:show="fieldsModalShow"
        :data-source-id="activeDsId"
        :run-id="run?.id"
        :rows="excelRows"
        :file-labels="fileLabels"
        :field-labels="fieldLabels"
        :ds-settings="dsSettingsEntry"
        :review-import-codes="reviewImportCodes"
        :review-logistics-codes="reviewLogisticsCodes"
        @changed="loadBootstrap"
      />
    </template>
    <NAlert v-else type="warning" title="暂无已配置日报的数据源" />
  </div>
</template>
