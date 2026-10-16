import axios from 'axios'
import { createGuestDemoAdapter } from './guestDemoApi'
import { isGuestMode } from './guestMode'

const fallbackAdapter = axios.getAdapter(axios.defaults.adapter)

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 5000,
  headers: { 'Content-Type': 'application/json' },
  adapter: createGuestDemoAdapter(fallbackAdapter),
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('pengzhi_auth_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use((response) => response, (error) => {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    localStorage.removeItem('pengzhi_auth_token')
    localStorage.removeItem('pengzhi_auth_user')
    if (!isGuestMode() && window.location.pathname.startsWith('/platform')) {
      window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`)
    }
  }
  return Promise.reject(error)
})

interface ApiErrorBody {
  message?: string
}

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data?.message || error.message || '请求失败，请稍后重试'
  }
  return error instanceof Error ? error.message : '请求失败，请稍后重试'
}
