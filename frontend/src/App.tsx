import { useEffect, useState } from 'react'
import { api } from './api'
import Connect from './views/Connect'
import Review from './views/Review'
import SenderRules from './views/SenderRules'

type View = 'review' | 'rules'

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const [authError, setAuthError] = useState<string>()
  const [view, setView] = useState<View>('review')

  useEffect(() => {
    api.auth.status().then(r => setAuthenticated(r.authenticated))
  }, [])

  async function handleConnect() {
    try {
      await api.auth.start()
      setAuthenticated(true)
      setAuthError(undefined)
    } catch {
      setAuthError('Could not connect to Gmail. Please try again.')
    }
  }

  if (authenticated === null) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-950 text-gray-400">
        Loading…
      </div>
    )
  }

  if (!authenticated) {
    return <Connect onConnect={handleConnect} error={authError} />
  }

  return (
    <div className="flex min-h-screen bg-gray-950 text-white">
      <nav className="w-56 shrink-0 border-r border-gray-800 flex flex-col p-4 gap-1">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3 px-2">
          Gmail Cleanup
        </span>
        <NavButton active={view === 'review'} onClick={() => setView('review')}>
          Review &amp; Delete
        </NavButton>
        <NavButton active={view === 'rules'} onClick={() => setView('rules')}>
          Sender Rules
        </NavButton>
      </nav>

      <main className="flex-1 overflow-auto">
        {view === 'review' && <Review onNavigateToRules={() => setView('rules')} />}
        {view === 'rules' && <SenderRules />}
      </main>
    </div>
  )
}

function NavButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`text-left px-3 py-2 rounded-lg text-sm transition-colors ${
        active
          ? 'bg-blue-600 text-white'
          : 'text-gray-400 hover:bg-gray-800 hover:text-white'
      }`}
    >
      {children}
    </button>
  )
}
