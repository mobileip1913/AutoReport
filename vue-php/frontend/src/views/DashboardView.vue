<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="hub">
    <p class="eyebrow">快速开始</p>
    <h1>配置一次，每日自动出报</h1>
    <p class="lead">Vue 前端 + PHP API 独立工程。本目录与仓库内 Twig 版 <code>php-backend</code>、Python <code>app/</code> 并行，互不影响。</p>
    <div class="steps">
      <RouterLink to="/mappings" class="step-card">
        <h2>01 · 报表配置</h2>
        <p>绑定店铺、数据基准表与取数规则。</p>
      </RouterLink>
      <RouterLink to="/daily" class="step-card">
        <h2>02 · 日报输出</h2>
        <p>选择日期生成日报，导出 Excel。</p>
      </RouterLink>
    </div>
  </section>
</template>
