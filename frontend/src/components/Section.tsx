import { useEffect, useRef, useState, type ReactNode } from 'react'

interface SectionProps {
  /** Anchor id, e.g. "zones" — the Prompt page deep-links to /settings#zones. */
  id: string
  title: string
  description?: string
  /** When set, the section renders the "Available after Phase N" placeholder. */
  availableAfterPhase?: number
  children?: ReactNode
}

/** A collapsible Settings section with a stable anchor.
 *  Sections for phases not yet built say so — they never show fake content
 *  (CLAUDE.md hard rule #1). */
export default function Section({
  id,
  title,
  description,
  availableAfterPhase,
  children,
}: SectionProps) {
  const locked = availableAfterPhase !== undefined
  const [open, setOpen] = useState(!locked)
  const ref = useRef<HTMLElement>(null)

  // Open and scroll to this section when the URL hash points at it.
  useEffect(() => {
    function syncWithHash() {
      if (window.location.hash.replace('#', '').split('?')[0] === id) {
        setOpen(true)
        ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
    syncWithHash()
    window.addEventListener('hashchange', syncWithHash)
    return () => window.removeEventListener('hashchange', syncWithHash)
  }, [id])

  return (
    <section
      id={id}
      ref={ref}
      className="scroll-mt-20 rounded-lg border border-slate-200 bg-white"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
      >
        <span>
          <span className="text-base font-semibold text-slate-900">{title}</span>
          <span className="ml-2 font-mono text-xs text-slate-400">#{id}</span>
          {description && (
            <span className="mt-0.5 block text-sm text-slate-500">{description}</span>
          )}
        </span>
        <span className="flex shrink-0 items-center gap-3">
          {locked && (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
              Phase {availableAfterPhase}
            </span>
          )}
          <span aria-hidden className="text-slate-400">
            {open ? '−' : '+'}
          </span>
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-5 py-4">
          {locked ? (
            <p className="text-sm text-slate-500">
              Available after Phase {availableAfterPhase}. Nothing is built here yet.
            </p>
          ) : (
            children
          )}
        </div>
      )}
    </section>
  )
}
