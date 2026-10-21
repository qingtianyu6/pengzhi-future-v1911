import axios from 'axios'
import { apiClient } from './client'
import { isGuestMode } from './guestMode'
export type Environment = { air_temperature: number; air_humidity: number; soil_temperature: number; soil_moisture: number; light_lux: number }
export type Actions = { fan: boolean; pump: boolean; lamp: boolean; led: boolean }
export type Mode = 'manual' | 'threshold' | 'predictive'
export interface Decision { reason: string; selected: Actions; requested: Actions; constraints: string[]; candidates: { action: Actions; score: number | null; predicted?: Environment }[]; next_evaluation_seconds: number }
export interface Snapshot {
  source: string; environment: Environment; target: Environment; scenario_id: string; simulation_time: number; mode: Mode
  humidity_baseline: number; running: boolean; emergency: boolean; planned: Actions; decision: Decision | null; error: string | null
  device: { mode: string; connected: boolean; status: string; confirmed: Actions | null; physical_verified: boolean; oled: Environment | null; fault: string; last_ack: { sequence: number; type: string; at: number } | null }
  history: (Environment & { time: number })[]
  events: { at: number; event: string; command_status: string; error: string | null; decision: Decision | null }[]
  wire_logs: { time: number; direction: string; frame: string }[]
}
export interface Scenario { id: string; name: string; environment: Environment }
export interface Comparison { label: string; parameters: { seed: number; steps: number }; results: { mode: Mode; mean_target_deviation: number; control_steps: number; on_seconds: { fan: number; pump: number; lamp: number }; switches: number; energy_proxy: number; irrigation_seconds: number; series: (Environment & { time: number })[] }[] }
function session() {
  let key = sessionStorage.getItem('greenhouse_sim_session')
  if (!key) { key = crypto.randomUUID(); sessionStorage.setItem('greenhouse_sim_session', key) }
  return key
}
export async function simulationRequest<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  // This feature always talks to FastAPI, including guests; bypass the existing in-browser demo adapter.
  const result = await apiClient.request<T>({ url: `${isGuestMode() ? '/greenhouse-demo' : '/greenhouse-control'}${path}`, method, data,
    adapter: axios.getAdapter(axios.defaults.adapter), timeout: 20000, headers: { 'X-Simulation-Session': session() } })
  return result.data
}
