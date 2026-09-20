import { apiClient } from './client'
import type { ApiResponse } from '../types/api'

export interface AuthUser {
  id: number
  display_name: string
  phone: string
  organization: string | null
  created_at: string
}

interface AuthData {
  token: string
  token_type: string
  expires_at: string
  user: AuthUser
}

const TOKEN_KEY = 'pengzhi_auth_token'
const USER_KEY = 'pengzhi_auth_user'

function persistAuth(data: AuthData) {
  localStorage.setItem(TOKEN_KEY, data.token)
  localStorage.setItem(USER_KEY, JSON.stringify(data.user))
}

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getStoredUser(): AuthUser | null {
  const value = localStorage.getItem(USER_KEY)
  if (!value) return null
  try { return JSON.parse(value) as AuthUser } catch { return null }
}

export function clearStoredAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export async function registerAccount(payload: {
  display_name: string
  phone: string
  organization?: string
  password: string
}) {
  const response = await apiClient.post<ApiResponse<AuthData>>('/auth/register', payload)
  persistAuth(response.data.data)
  return response.data.data
}

export async function loginAccount(payload: { phone: string; password: string; remember_me: boolean }) {
  const response = await apiClient.post<ApiResponse<AuthData>>('/auth/login', payload)
  persistAuth(response.data.data)
  return response.data.data
}

export async function logoutAccount() {
  const token = getStoredToken()
  try {
    if (token) await apiClient.post('/auth/logout', undefined, { headers: { Authorization: `Bearer ${token}` } })
  } finally {
    clearStoredAuth()
  }
}
