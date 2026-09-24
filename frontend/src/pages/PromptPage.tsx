import { Link } from 'react-router-dom'
import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import type { Metrics } from '../models/api'

/** Page 1 — Prompt (SPEC §17). Phase 0 shows the empty state only: the live view
 *  arrives in Phase 1 and the natural-language box becomes usable in Phase 4. */
export default function PromptPage() {
  const { data: metrics } = useAsync<Metrics>(() => api.metrics())

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Prompt</h1>
        <p className="mt-1 text-sm text-slate-500">
          Describe what you want captured, in plain language.
        </p>
      </div>

      <section className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <h2 className="text-base font-semibold text-slate-900">No camera yet</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
          Camera sources and the live view arrive in Phase 1. Once a webcam is added,
          this page shows the live view with boxes and track ids.
        </p>
        <Link
          to="/settings#cameras"
          className="mt-4 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Go to camera settings
        </Link>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <label
          htmlFor="nl-prompt"
          className="block text-sm font-medium text-slate-900"
        >
          What event should I capture?
        </label>
        <textarea
          id="nl-prompt"
          disabled
          rows={3}
          placeholder="Available after Phase 4 — e.g. “Alert me if nobody is at my desk for 10 seconds”"
          className="mt-2 w-full cursor-not-allowed rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-400"
        />
        <p className="mt-2 text-xs text-slate-500">
          The natural-language parser lands in Phase 4. The structured plan builder
          lands in Phase 2.
        </p>
      </section>

      {metrics && (
        <p className="text-xs text-slate-500">
          Backend RSS {metrics.process_rss_mb.toFixed(0)} MB · system RAM{' '}
          {metrics.system_ram_percent.toFixed(0)}% of{' '}
          {(metrics.system_ram_total_mb / 1024).toFixed(1)} GB
        </p>
      )}
    </div>
  )
}
