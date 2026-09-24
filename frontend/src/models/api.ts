/** Types mirroring the backend Pydantic schemas (app/schemas/api.py). */

export interface FeatureStatus {
  name: string
  available: boolean
  detail: string
  fix_command: string | null
}

export interface ModelStatus {
  name: string
  loaded: boolean
  device: string | null
  group: string | null
  model_id: string | null
  model_version: string | null
  load_time_s: number | null
  loaded_at: number | null
  last_used: number | null
  load_error: string | null
}

export interface Health {
  status: 'ok' | 'degraded'
  version: string
  phase: number
  device: string
  device_reason: string
  database: boolean
  storage: boolean
  models: ModelStatus[]
  features: FeatureStatus[]
}

export interface Metrics {
  process_rss_mb: number
  process_cpu_percent: number
  system_ram_total_mb: number
  system_ram_available_mb: number
  system_ram_percent: number
  gpu: Record<string, unknown> | null
}

export interface SetupItem {
  key: string
  label: string
  ok: boolean
  detail: string
  fix_command: string | null
}

export interface SetupStatus {
  ok: boolean
  items: SetupItem[]
}

export type SettingSource = 'env' | 'override'

export interface SettingValue {
  key: string
  value: string | number | boolean
  source: SettingSource
  type: string
}

export interface SettingsResponse {
  settings: SettingValue[]
}
