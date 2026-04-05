import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { ReviewRow, SyncStatus } from '../api'

interface Props {
  onNavigateToRules: () => void
}

type Phase = 'idle' | 'syncing' | 'ready' | 'confirming' | 'deleting' | 'done'

export default function Review({ onNavigateToRules }: Props) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [emails, setEmails] = useState<ReviewRow[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<{ deleted: number; failed: string[]; rules_saved: boolean } | null>(null)
  const [error, setError] = useState<string>()
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadReview = useCallback(async () => {
    try {
      const data = await api.review.get()
      setEmails(data.emails)
      setSelected(new Set(data.emails.filter(e => e.pre_selected).map(e => e.email_id)))
      setPhase('ready')
    } catch {
      setError('Failed to load emails.')
      setPhase('idle')
    }
  }, [])

  const startSync = useCallback(async () => {
    setPhase('syncing')
    setError(undefined)
    setResult(null)
    try {
      await api.sync.start()
    } catch {
      setError('Failed to start sync.')
      setPhase('idle')
      return
    }

    pollRef.current = setInterval(async () => {
      const status: SyncStatus = await api.sync.status()
      if (!status.is_syncing) {
        clearInterval(pollRef.current!)
        loadReview()
      }
    }, 1500)
  }, [loadReview])

  useEffect(() => {
    api.sync.status().then(s => {
      if (s.last_synced_at) loadReview()
      else startSync()
    })
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [loadReview, startSync])

  function toggleRow(emailId: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(emailId)) next.delete(emailId)
      else next.add(emailId)
      return next
    })
  }

  const selectedIds = [...selected]
  const protectedIds = emails.filter(e => !selected.has(e.email_id)).map(e => e.email_id)
  const isActionBlocked = phase === 'syncing' || phase === 'deleting' || phase === 'confirming'
  const selectedCount = selected.size
  const totalCount = emails.length

  async function confirmDelete() {
    setPhase('deleting')
    try {
      const res = await api.delete.execute({ deleted_ids: selectedIds, protected_ids: protectedIds })
      setResult(res)
      setPhase('done')
    } catch {
      setError('Deletion failed. Please try again.')
      setPhase('ready')
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Review &amp; Delete</h1>
          {phase === 'ready' && totalCount > 0 && (
            <p className="text-gray-500 text-sm mt-1">
              {totalCount} emails loaded · {selectedCount} selected for deletion
            </p>
          )}
        </div>
        <button
          onClick={startSync}
          disabled={isActionBlocked}
          className="text-sm px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {phase === 'syncing' ? 'Syncing…' : 'Re-sync'}
        </button>
      </div>

      {error && (
        <div className="mb-4 text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      {phase === 'syncing' && (
        <div className="text-gray-400 text-sm">Fetching your most recent 1,000 emails…</div>
      )}

      {(phase === 'ready' || phase === 'confirming') && emails.length === 0 && (
        <div className="text-center py-16 text-gray-500">
          <p className="mb-3">No emails loaded. Try syncing.</p>
        </div>
      )}

      {(phase === 'ready' || phase === 'confirming') && emails.length > 0 && (
        <>
          <div className="rounded-xl border border-gray-800 overflow-hidden mb-6">
            <table className="w-full text-sm">
              <thead className="bg-gray-900 text-gray-500 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 text-left w-8"></th>
                  <th className="px-4 py-3 text-left">Sender</th>
                  <th className="px-4 py-3 text-left">Subject</th>
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Tag</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {emails.map(row => {
                  const isSelected = selected.has(row.email_id)
                  return (
                    <tr
                      key={row.email_id}
                      onClick={() => toggleRow(row.email_id)}
                      className={`cursor-pointer transition-colors ${
                        isSelected ? 'bg-gray-900 hover:bg-gray-800' : 'bg-gray-950 hover:bg-gray-900/50'
                      }`}
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleRow(row.email_id)}
                          onClick={e => e.stopPropagation()}
                          className="accent-blue-500"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-white truncate max-w-[180px]">
                          {row.display_name || row.sender_address}
                        </div>
                        <div className="text-gray-500 text-xs truncate max-w-[180px]">
                          {row.sender_address}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-300 truncate max-w-[260px]">
                        {row.subject}
                      </td>
                      <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                        {new Date(row.date * 1000).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        {row.reason && (
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            row.reason === 'Learned rule'
                              ? 'bg-purple-900/40 text-purple-300'
                              : 'bg-yellow-900/40 text-yellow-300'
                          }`}>
                            {row.reason}
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {phase === 'ready' && (
            <button
              onClick={() => setPhase('confirming')}
              disabled={selectedCount === 0}
              className="bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium px-6 py-3 rounded-lg transition-colors"
            >
              Delete {selectedCount} email{selectedCount !== 1 ? 's' : ''}
            </button>
          )}

          {phase === 'confirming' && (
            <div className="bg-gray-900 border border-red-800 rounded-xl p-6">
              <p className="text-white font-medium mb-1">
                Permanently delete {selectedCount} email{selectedCount !== 1 ? 's' : ''}?
              </p>
              <p className="text-gray-400 text-sm mb-5">This cannot be undone.</p>
              <div className="flex gap-3">
                <button
                  onClick={confirmDelete}
                  className="bg-red-600 hover:bg-red-500 text-white font-medium px-5 py-2 rounded-lg transition-colors"
                >
                  Confirm delete
                </button>
                <button
                  onClick={() => setPhase('ready')}
                  className="bg-gray-800 hover:bg-gray-700 text-white px-5 py-2 rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {phase === 'deleting' && (
        <div className="text-gray-400 text-sm">Deleting {selectedCount} emails…</div>
      )}

      {phase === 'done' && result && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <p className="text-white font-medium mb-1">
            {result.deleted} email{result.deleted !== 1 ? 's' : ''} deleted
          </p>
          {result.failed.length > 0 && (
            <p className="text-red-400 text-sm mb-2">
              {result.failed.length} failed to delete.
            </p>
          )}
          {!result.rules_saved && (
            <p className="text-yellow-400 text-sm mb-2">
              Sender rules could not be saved. You can add them manually in{' '}
              <button onClick={onNavigateToRules} className="underline">Sender Rules</button>.
            </p>
          )}
          <button
            onClick={startSync}
            disabled={isActionBlocked}
            className="mt-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium px-5 py-2 rounded-lg transition-colors"
          >
            Re-sync next batch
          </button>
        </div>
      )}
    </div>
  )
}
