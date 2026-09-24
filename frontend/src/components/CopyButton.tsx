import { useState } from 'react'

/** Copies a fix command to the clipboard, with a graceful fallback when the
 *  Clipboard API is unavailable (non-HTTPS origins, older browsers). */
export default function CopyButton({ text }: { text: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')

  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setState('copied')
    } catch {
      setState('failed')
    }
    window.setTimeout(() => setState('idle'), 1800)
  }

  const label =
    state === 'copied' ? 'Copied' : state === 'failed' ? 'Select manually' : 'Copy'

  return (
    <button
      type="button"
      onClick={copy}
      className="shrink-0 rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
    >
      {label}
    </button>
  )
}
