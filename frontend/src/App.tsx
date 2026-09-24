import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import EventsPage from './pages/EventsPage'
import PromptPage from './pages/PromptPage'
import SettingsPage from './pages/SettingsPage'
import BackendStatus from './components/BackendStatus'

/** Exactly three pages (SPEC §17). New features become Settings sections,
 *  never a fourth page. */
const NAV = [
  { to: '/', label: 'Prompt', end: true },
  { to: '/events', label: 'Events', end: false },
  { to: '/settings', label: 'Settings', end: false },
]

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
          <span className="text-sm font-semibold tracking-tight text-slate-900">
            Vision VMS
          </span>
          <nav className="flex gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  [
                    'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-slate-900 text-white'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                  ].join(' ')
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <BackendStatus />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<PromptPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
