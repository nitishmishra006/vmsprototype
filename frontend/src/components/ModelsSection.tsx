import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import type { Health } from '../models/api'
import CopyButton from './CopyButton'

/** Settings #models — model/feature status straight from /api/health.
 *  A feature whose model is missing is shown as unavailable, never as working. */
export default function ModelsSection() {
  const { data, error, loading, reload } = useAsync<Health>(() => api.health())

  if (loading) return <p className="text-sm text-slate-500">Loading…</p>
  if (error)
    return (
      <p className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {error}
      </p>
    )
  if (!data) return null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <span className="text-slate-600">
          Device: <span className="font-medium text-slate-900">{data.device}</span>
        </span>
        <span className="text-slate-500">{data.device_reason}</span>
        <button
          type="button"
          onClick={reload}
          className="ml-auto rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      <div>
        <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Features
        </h4>
        <ul className="space-y-2">
          {data.features.map((feature) => (
            <li
              key={feature.name}
              className="rounded border border-slate-200 px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <span
                  aria-hidden
                  className={[
                    'h-2.5 w-2.5 rounded-full',
                    feature.available ? 'bg-emerald-500' : 'bg-slate-300',
                  ].join(' ')}
                />
                <span className="font-medium text-slate-900">{feature.name}</span>
                <span
                  className={[
                    'rounded-full px-2 py-0.5 text-xs',
                    feature.available
                      ? 'bg-emerald-50 text-emerald-700'
                      : 'bg-slate-100 text-slate-600',
                  ].join(' ')}
                >
                  {feature.available ? 'available' : 'unavailable'}
                </span>
              </div>
              <p className="mt-1 break-words text-slate-500">{feature.detail}</p>
              {!feature.available && feature.fix_command && (
                <div className="mt-2 flex items-center gap-2">
                  <code className="min-w-0 flex-1 overflow-x-auto rounded bg-slate-900 px-2 py-1 text-xs text-slate-100">
                    {feature.fix_command}
                  </code>
                  <CopyButton text={feature.fix_command} />
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Loaded models
        </h4>
        {data.models.length === 0 ? (
          <p className="text-sm text-slate-500">
            No models are registered yet — the detector arrives in Phase 1.
          </p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="py-1">Name</th>
                <th className="py-1">Loaded</th>
                <th className="py-1">Device</th>
                <th className="py-1">Version</th>
                <th className="py-1">Load time</th>
              </tr>
            </thead>
            <tbody>
              {data.models.map((model) => (
                <tr key={model.name} className="border-t border-slate-100">
                  <td className="py-1 font-mono text-xs">{model.name}</td>
                  <td className="py-1">{model.loaded ? 'yes' : 'no'}</td>
                  <td className="py-1">{model.device ?? '—'}</td>
                  <td className="py-1">{model.model_version ?? '—'}</td>
                  <td className="py-1">
                    {model.load_time_s != null ? `${model.load_time_s.toFixed(2)}s` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
