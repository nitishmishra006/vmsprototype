/** Typed fetch wrapper around the backend API. */

import type {
  Health,
  Metrics,
  SettingsResponse,
  SetupStatus,
} from '../models/api'

export const API_BASE: string =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch (cause) {
    throw new ApiError(
      0,
      `Cannot reach the backend at ${API_BASE}. Is it running? (${String(cause)})`,
    )
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // response had no JSON body; keep the status line
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  health: () => request<Health>('/api/health'),
  metrics: () => request<Metrics>('/api/metrics'),
  setupStatus: () => request<SetupStatus>('/api/setup-status'),
  getSettings: () => request<SettingsResponse>('/api/settings'),
  patchSettings: (values: Record<string, unknown>) =>
    request<SettingsResponse>('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify({ values }),
    }),
  resetSettings: (keys: string[]) =>
    request<SettingsResponse>('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify({ reset: keys }),
    }),
}
