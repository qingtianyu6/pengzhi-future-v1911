import { create } from 'zustand'
import { getHealth } from '../api/systemApi'

type ServiceStatus = 'checking' | 'online' | 'offline'

interface SystemState {
  status: ServiceStatus
  version?: string
  checkHealth: () => Promise<void>
}

export const useSystemStore = create<SystemState>((set) => ({
  status: 'checking',
  checkHealth: async () => {
    set({ status: 'checking' })
    try {
      const health = await getHealth()
      set({ status: 'online', version: health.version })
    } catch {
      set({ status: 'offline', version: undefined })
    }
  },
}))
