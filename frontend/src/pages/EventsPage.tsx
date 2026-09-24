import { Link } from 'react-router-dom'

/** Page 2 — Events (SPEC §17). Phase 0 is the empty state; the live list, evidence
 *  view and feedback buttons arrive in Phase 2, the Improvements tab in Phase 8b. */
export default function EventsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Events</h1>
        <p className="mt-1 text-sm text-slate-500">
          Alerts and review items, with the evidence behind each one.
        </p>
      </div>

      <section className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <h2 className="text-base font-semibold text-slate-900">No events yet</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
          Event detection arrives in Phase 2 (Milestone 1). Events will appear here
          live, each with before / during / after evidence frames, a score breakdown
          and Correct / Wrong / Not sure feedback.
        </p>
        <Link
          to="/settings"
          className="mt-4 inline-block rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Check setup status
        </Link>
      </section>
    </div>
  )
}
