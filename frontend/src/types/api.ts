export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface HealthData {
  service: string
  status: 'healthy'
  version: string
  database: 'connected'
}
