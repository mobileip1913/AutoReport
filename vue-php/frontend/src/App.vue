<script setup lang="ts">
import { NDialogProvider, NMessageProvider } from 'naive-ui'
import AppLayout from '@/layouts/AppLayout.vue'
</script>

<template>
  <NMessageProvider>
    <NDialogProvider>
      <AppLayout />
    </NDialogProvider>
  </NMessageProvider>
</template>
