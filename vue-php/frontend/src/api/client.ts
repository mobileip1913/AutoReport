import axios from 'axios'

/** 同源部署时 baseURL 为空；开发期 Vite proxy 转发 /api */
export const api = axios.create({
  baseURL: '',
  withCredentials: true,
  headers: { Accept: 'application/json' },
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') {
      err.message = detail
    }
    return Promise.reject(err)
  },
)

export interface SessionPayload {
  current_account: { id: number; display_name: string }
  account_menu: Array<{ id: number; display_name: string; initial: string; store_hint: string }>
  accessible_stores: Array<{ id: number; name: string; platform: string; data_source_id: number }>
  current_store: { id: number; name: string; data_source_id: number } | null
  accessible_data_sources: Array<{ id: number; name: string }>
}

export async function fetchSession() {
  const { data } = await api.get<SessionPayload>('/api/session')
  return data
}

export async function switchAccount(accountId: number) {
  const { data } = await api.post<{ ok: boolean; session: SessionPayload }>('/api/session/account', {
    account_id: accountId,
  })
  return data.session
}

export async function switchStore(storeId: number) {
  const { data } = await api.post<{ ok: boolean; session: SessionPayload }>('/api/session/store', {
    store_id: storeId,
  })
  return data.session
}
