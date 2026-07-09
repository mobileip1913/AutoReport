<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NSpin } from 'naive-ui'
import { api } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { useMessage } from '@/composables/useMessage'
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
          <div v-if="showRunStatus" class="daily-hub__status">
            <span class="daily-status-pill">
              <span class="daily-status-pill__dot" aria-hidden="true"></span>
              <span class="tabular-nums">已生成 {{ run!.report_date }} · #{{ run!.id }}</span>
            </span>
            <span class="daily-hub__sync">已同步</span>
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
                <input v-model="reportDate" type="date" class="border rounded-lg px-3 py-2 text-sm" />
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
                    <span class="daily-import-tile__label">下载模板</span>
                  </button>
                  <label class="daily-import-tile">
                    <span class="daily-import-tile__label">导入刷单</span>
                    <input type="file" accept=".xlsx" class="hidden" @change="onFile('review', $event)" />
                  </label>
                  <label class="daily-import-tile">
                    <span class="daily-import-tile__label">导入运费</span>
                    <input
                      type="file"
                      accept=".xlsx"
                      class="hidden"
                      @change="onFile('logistics', $event)"
                    />
                  </label>
                  <label class="daily-import-tile">
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
                <button type="submit" class="daily-generate-btn btn-primary" :disabled="busy">
                  <span v-if="!busy" class="daily-generate-btn__idle">生成日报</span>
                  <span v-else class="daily-generate-btn__busy">
                    <span class="daily-generate-spinner" aria-hidden="true"></span>
                    生成中…
                  </span>
                </button>
                <div class="daily-action-row">
                  <button
                    v-if="excelRows.length"
                    type="button"
                    class="daily-action-chip"
                    @click="openFieldsModal"
                  >
                    设置日报字段
                  </button>
                  <button type="button" class="daily-action-chip" @click="exportSku">导出 SKU 销量</button>
                  <a
                    v-if="run"
                    :href="`/daily/${run.id}/export`"
                    class="daily-action-chip no-underline"
                    target="_blank"
                  >
                    导出 Excel
                  </a>
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
        @changed="loadBootstrap"
      />
    </template>
    <NAlert v-else type="warning" title="暂无已配置日报的数据源" />
  </div>
</template>
