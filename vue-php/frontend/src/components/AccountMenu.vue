<script setup lang="ts">
import { computed } from 'vue'
import { NDropdown, NButton } from 'naive-ui'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()

const accountOptions = computed(() =>
  (session.data?.account_menu ?? []).map((a) => ({
    label: a.display_name,
    key: String(a.id),
  })),
)

async function onAccount(key: string) {
  await session.setAccount(Number(key))
}
</script>

<template>
  <div v-if="accountOptions.length > 1" class="account-menu">
    <NDropdown trigger="click" :options="accountOptions" @select="onAccount">
      <NButton quaternary size="small">
        {{ session.data?.current_account?.display_name ?? '账号' }}
      </NButton>
    </NDropdown>
  </div>
</template>

<style scoped>
.account-menu {
  display: flex;
  gap: 0.25rem;
  align-items: center;
}
</style>
