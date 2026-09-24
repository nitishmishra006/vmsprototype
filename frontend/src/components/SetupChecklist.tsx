import { api } from '../services/api'
import { useAsync } from '../hooks/useAsync'
import type { SetupStatus } from '../models/api'
import CopyButton from './CopyButton'

/** The Setup checklist at the top of Settings (SPEC §17).
 *  Every unmet item shows the exact command that fixes it. */
export default function SetupChecklist() {
  const { data, error, loading, reload } = useAsync<SetupStatus>(() => api.setupStatus())

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Setup checklist</h2>
          <p className="text-sm text-slate-500">
            What this laptop still needs before the later phases can run.
          </p>
        </div>
        <button
          type="button"
          onClick={reload}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Re-check
        </button>
      </div>

      {loading && <p className="text-sm text-slate-500">Checking…</p>}

      {error && (
        <p className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      {data && (
        <>
          <p className="mb-3 text-sm font-medium">
            {data.ok ? (
              <span className="text-emerald-700">Everything needed is present.</span>
            ) : (
              <span className="text-amber-700">
                {data.items.filter((i) => !i.ok).length} item(s) still to set up.
              </span>
            )}
          </p>
          <ul className="divide-y divide-slate-100">
            {data.items.map((item) => (
              <li key={item.key} className="py-3">
                <div className="flex items-start gap-3">
                  <span
                    aria-hidden
                    className={[
                      'mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full',
                      item.ok ? 'bg-emerald-500' : 'bg-red-500',
                    ].join(' ')}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900">
                      {item.label}
                      <span className="sr-only">{item.ok ? ' — ok' : ' — missing'}</span>
                    </p>
                    <p className="break-words text-sm text-slate-500">{item.detail}</p>
                    {!item.ok && item.fix_command && (
                      <div className="mt-2 flex items-center gap-2">
                        <code className="min-w-0 flex-1 overflow-x-auto rounded bg-slate-900 px-2 py-1 text-xs text-slate-100">
                          {item.fix_command}
                        </code>
                        <CopyButton text={item.fix_command} />
                      </div>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
