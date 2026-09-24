import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import type { Health } from '../models/api'

/** Small header badge: is the backend reachable, and on which device. */
export default function BackendStatus() {
  const { data, error } = useAsync<Health>(() => api.health())

  if (error) {
    return (
      <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-700">
        backend unreachable
      </span>
    )
  }
  if (!data) {
    return <span className="text-xs text-slate-400">checking…</span>
  }
  return (
    <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
      phase {data.phase} · {data.device}
    </span>
  )
}
