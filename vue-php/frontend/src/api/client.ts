import axios from 'axios'

/** 与 PHP Slim 错误格式对齐：{ detail: string } */
export const api = axios.create({
  baseURL: '/',
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
