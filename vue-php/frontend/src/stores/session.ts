import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchSession, switchAccount, switchStore, type SessionPayload } from '@/api/client'

export const useSessionStore = defineStore('session', () => {
  const data = ref<SessionPayload | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      data.value = await fetchSession()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '加载会话失败'
      data.value = null
    } finally {
      loading.value = false
    }
  }

  async function setAccount(accountId: number) {
    data.value = await switchAccount(accountId)
  }

  async function setStore(storeId: number) {
    data.value = await switchStore(storeId)
  }

  return { data, loading, error, load, setAccount, setStore }
})
