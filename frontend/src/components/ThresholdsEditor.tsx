import { useEffect, useState } from 'react'
import { api } from '../services/api'
import type { SettingValue } from '../models/api'

/** Grouping from SPEC §17: detection / events / evidence / quality.
 *  Anything not listed falls into "other" so no setting is ever hidden. */
const GROUPS: { id: string; label: string; keys: string[] }[] = [
  {
    id: 'detection',
    label: 'Detection',
    keys: [
      'CAMERA_FPS',
      'DETECTION_FPS',
      'DETECT_IMGSZ',
      'DETECTOR_MODEL',
      'DETECTOR_CONF',
      'DETECTOR_CLASSES',
      'TRACK_BUFFER_FRAMES',
      'TRAJECTORY_MAX_POINTS',
      'SPEED_WINDOW_SECONDS',
      'WEBCAM_INDEX',
      'WEBCAM_WIDTH',
      'WEBCAM_HEIGHT',
      'WEBCAM_MAX_PROBE',
    ],
  },
  {
    id: 'events',
    label: 'Events',
    keys: [
      'CONDITION_GRACE_SECONDS',
      'EVENT_COOLDOWN_SECONDS',
      'MAX_EVENTS_PER_PLAN_PER_MINUTE',
      'SCENE_CHANGE_THRESHOLD',
    ],
  },
  {
    id: 'evidence',
    label: 'Evidence',
    keys: [
      'EVIDENCE_FPS',
      'EVIDENCE_WIDTH',
      'EVIDENCE_PRE_SECONDS',
      'EVIDENCE_POST_SECONDS',
      'EVIDENCE_RETENTION_DAYS',
    ],
  },
  {
    id: 'quality',
    label: 'Quality',
    keys: [
      'MIN_TRACK_AGE_FRAMES',
      'MIN_DET_CONF',
      'QUALITY_WEIGHTS',
      'VLM_BOOST',
      'VLM_PENALTY',
      'ALERT_THRESHOLD',
      'REVIEW_THRESHOLD',
    ],
  },
]

function groupFor(key: string): string {
  return GROUPS.find((g) => g.keys.includes(key))?.id ?? 'other'
}

/** Parse the edited string back into the type the backend expects.
 *  The backend validates authoritatively; this just avoids sending "0.7" as a
 *  string where a float is wanted. */
function coerce(raw: string, type: string): unknown {
  if (type === 'bool') return raw === 'true'
  if (type === 'int') {
    const n = Number(raw)
    return Number.isFinite(n) ? Math.trunc(n) : raw
  }
  if (type === 'float') {
    const n = Number(raw)
    return Number.isFinite(n) ? n : raw
  }
  return raw
}

export default function ThresholdsEditor() {
  const [settings, setSettings] = useState<SettingValue[] | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function apply(list: SettingValue[]) {
    setSettings(list)
    setDrafts(Object.fromEntries(list.map((s) => [s.key, String(s.value)])))
  }

  useEffect(() => {
    api
      .getSettings()
      .then((r) => apply(r.settings))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  async function save(key: string) {
    const setting = settings?.find((s) => s.key === key)
    if (!setting) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const response = await api.patchSettings({
        [key]: coerce(drafts[key] ?? '', setting.type),
      })
      apply(response.settings)
      setNotice(`${key} saved. It persists across a backend restart.`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function reset(key: string) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const response = await api.resetSettings([key])
      apply(response.settings)
      setNotice(`${key} reset to the .env value.`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (error && !settings) {
    return (
      <p className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {error}
      </p>
    )
  }
  if (!settings) return <p className="text-sm text-slate-500">Loading settings…</p>

  const groups = [...GROUPS, { id: 'other', label: 'Other', keys: [] as string[] }]

  return (
    <div className="space-y-6">
      {notice && (
        <p className="rounded border border-emerald-200 bg-emerald-50 p-2 text-sm text-emerald-800">
          {notice}
        </p>
      )}
      {error && (
        <p className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {groups.map((group) => {
        const rows = settings.filter((s) => groupFor(s.key) === group.id)
        if (rows.length === 0) return null
        return (
          <div key={group.id}>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
              {group.label}
            </h4>
            <div className="space-y-2">
              {rows.map((setting) => {
                const dirty = (drafts[setting.key] ?? '') !== String(setting.value)
                return (
                  <div
                    key={setting.key}
                    className="flex flex-wrap items-center gap-2 rounded border border-slate-200 px-3 py-2"
                  >
                    <label
                      htmlFor={`setting-${setting.key}`}
                      className="min-w-[16rem] font-mono text-xs text-slate-700"
                    >
                      {setting.key}
                    </label>

                    {setting.type === 'bool' ? (
                      <select
                        id={`setting-${setting.key}`}
                        value={drafts[setting.key] ?? 'false'}
                        onChange={(e) =>
                          setDrafts((d) => ({ ...d, [setting.key]: e.target.value }))
                        }
                        className="rounded border border-slate-300 px-2 py-1 text-sm"
                      >
                        <option value="true">true</option>
                        <option value="false">false</option>
                      </select>
                    ) : (
                      <input
                        id={`setting-${setting.key}`}
                        value={drafts[setting.key] ?? ''}
                        onChange={(e) =>
                          setDrafts((d) => ({ ...d, [setting.key]: e.target.value }))
                        }
                        className="w-48 rounded border border-slate-300 px-2 py-1 text-sm"
                      />
                    )}

                    <span
                      className={[
                        'rounded-full px-2 py-0.5 text-xs',
                        setting.source === 'override'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-600',
                      ].join(' ')}
                    >
                      {setting.source}
                    </span>

                    <div className="ml-auto flex gap-2">
                      <button
                        type="button"
                        disabled={!dirty || busy}
                        onClick={() => void save(setting.key)}
                        className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-40"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        disabled={setting.source !== 'override' || busy}
                        onClick={() => void reset(setting.key)}
                        className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 disabled:opacity-40"
                      >
                        Reset to .env
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
