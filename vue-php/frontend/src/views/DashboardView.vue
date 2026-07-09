<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/api/client'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const recentRuns = ref<Array<{ id: number; report_date: string }>>([])

onMounted(async () => {
  const { data } = await api.get('/api/dashboard/bootstrap')
  recentRuns.value = data.recent_runs ?? []
})
</script>

<template>
  <section class="home-hub" aria-labelledby="home-hub-title">
    <div class="home-hub__ambient" aria-hidden="true">
      <span class="home-hub__orb home-hub__orb--a"></span>
      <span class="home-hub__orb home-hub__orb--b"></span>
      <span class="home-hub__orb home-hub__orb--c"></span>
    </div>

    <header class="home-hub__hero">
      <p class="home-hub__eyebrow">快速开始</p>
      <h1 id="home-hub-title" class="home-hub__title">配置一次，每日自动出报</h1>
      <p class="home-hub__lead">
        在报表配置里定义取数规则，再到日报输出生成并导出 Excel。
        <span v-if="session.data?.current_store" class="home-hub__store">
          当前店铺：<strong>{{ session.data.current_store.name }}</strong>
        </span>
      </p>
    </header>

    <div class="home-hub__steps">
      <RouterLink to="/mappings" class="home-step home-step--config">
        <div class="home-step__head">
          <span class="home-step__badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M10.5 6h9.75M10.5 12h9.75M10.5 18h9.75M4.5 6h.008v.008H4.5V6zm0 6h.008v.008H4.5V12zm0 6h.008v.008H4.5V18z"
              />
            </svg>
          </span>
          <span class="home-step__index">01</span>
        </div>
        <h2 class="home-step__title">报表配置</h2>
        <p class="home-step__desc">绑定店铺、设置数据基准表与取数规则，定义日报字段与计算口径。</p>
        <ul class="home-step__tags">
          <li>取数规则</li>
          <li>跨表关联</li>
          <li>导出 JSON</li>
        </ul>
        <span class="home-step__cta">
          进入配置
          <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path
              fill-rule="evenodd"
              d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
              clip-rule="evenodd"
            />
          </svg>
        </span>
      </RouterLink>

      <div class="home-hub__bridge" aria-hidden="true">
        <span class="home-hub__bridge-line"></span>
        <span class="home-hub__bridge-dot"></span>
        <span class="home-hub__bridge-line"></span>
      </div>

      <RouterLink to="/daily" class="home-step home-step--daily">
        <div class="home-step__head">
          <span class="home-step__badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M6.75 3v2.25M17.25 3v2.25M3 9.75h18M4.5 6.75h15a1.5 1.5 0 011.5 1.5v12a1.5 1.5 0 01-1.5 1.5h-15a1.5 1.5 0 01-1.5-1.5v-12a1.5 1.5 0 011.5-1.5z"
              />
            </svg>
          </span>
          <span class="home-step__index">02</span>
        </div>
        <h2 class="home-step__title">日报输出</h2>
        <p class="home-step__desc">选择日期生成日报，核对数值、填写手工项，一键导出 Excel 或 SKU 明细。</p>
        <ul class="home-step__tags">
          <li>生成日报</li>
          <li>刷单导入</li>
          <li>导出 Excel</li>
        </ul>
        <span class="home-step__cta">
          开始出报
          <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path
              fill-rule="evenodd"
              d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
              clip-rule="evenodd"
            />
          </svg>
        </span>
      </RouterLink>
    </div>

    <div v-if="recentRuns.length" class="mt-6 px-1">
      <p class="text-sm text-slate-500 mb-2">最近生成</p>
      <div class="flex flex-wrap gap-2">
        <RouterLink
          v-for="r in recentRuns.slice(0, 6)"
          :key="r.id"
          :to="`/daily?run_id=${r.id}`"
          class="daily-status-pill no-underline"
        >
          {{ r.report_date }} · #{{ r.id }}
        </RouterLink>
      </div>
    </div>

    <p class="home-hub__footnote">
      数据由 ETL 脚本同步至数据库；列头变更时在报表配置中调整取数规则即可。
    </p>
  </section>
</template>

<style scoped>
a.home-step {
  text-decoration: none;
  color: inherit;
}
</style>
