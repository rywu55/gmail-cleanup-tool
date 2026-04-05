import { useEffect, useState } from 'react'
import { api } from '../api'
import type { SenderRule } from '../api'

export default function SenderRules() {
  const [rules, setRules] = useState<SenderRule[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()

  const [newAddress, setNewAddress] = useState('')
  const [newRule, setNewRule] = useState<'delete' | 'protect'>('delete')
  const [newName, setNewName] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function loadRules() {
    try {
      const data = await api.rules.list()
      setRules(data.rules)
    } catch {
      setError('Failed to load sender rules.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadRules() }, [])

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!newAddress.trim()) return
    setSubmitting(true)
    try {
      await api.rules.add({
        sender_address: newAddress.trim().toLowerCase(),
        rule: newRule,
        display_name: newName.trim() || null,
      })
      setNewAddress('')
      setNewName('')
      setNewRule('delete')
      await loadRules()
    } catch {
      setError('Failed to add rule.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleToggle(rule: SenderRule) {
    try {
      await api.rules.add({
        sender_address: rule.sender_address,
        rule: rule.rule === 'delete' ? 'protect' : 'delete',
        display_name: rule.display_name,
      })
      await loadRules()
    } catch {
      setError('Failed to update rule.')
    }
  }

  async function handleRemove(senderAddress: string) {
    if (!confirm(`Remove rule for ${senderAddress}?`)) return
    try {
      await api.rules.remove(senderAddress)
      await loadRules()
    } catch {
      setError('Failed to remove rule.')
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-xl font-semibold mb-6">Sender Rules</h1>

      {error && (
        <div className="mb-4 text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      {/* Add rule form */}
      <form onSubmit={handleAdd} className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-8">
        <h2 className="text-sm font-medium text-gray-300 mb-4">Add Sender Rule</h2>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            placeholder="sender@example.com"
            value={newAddress}
            onChange={e => setNewAddress(e.target.value)}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          <input
            type="text"
            placeholder="Display name (optional)"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          <select
            value={newRule}
            onChange={e => setNewRule(e.target.value as 'delete' | 'protect')}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="delete">Delete</option>
            <option value="protect">Protect</option>
          </select>
          <button
            type="submit"
            disabled={submitting || !newAddress.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            Add
          </button>
        </div>
      </form>

      {/* Rules list */}
      {loading ? (
        <div className="text-gray-500 text-sm">Loading rules…</div>
      ) : rules.length === 0 ? (
        <div className="text-center py-12 text-gray-600 text-sm">
          No sender rules yet. Rules are created automatically after each deletion pass, or you can add them manually above.
        </div>
      ) : (
        <div className="rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-900 text-gray-500 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 text-left">Sender</th>
                <th className="px-4 py-3 text-left">Rule</th>
                <th className="px-4 py-3 text-left">Source</th>
                <th className="px-4 py-3 text-left">Updated</th>
                <th className="px-4 py-3 text-left"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {rules.map(rule => (
                <tr key={rule.sender_address} className="bg-gray-950 hover:bg-gray-900 transition-colors">
                  <td className="px-4 py-3">
                    <div className="text-white font-medium">{rule.display_name || rule.sender_address}</div>
                    <div className="text-gray-500 text-xs">{rule.sender_address}</div>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggle(rule)}
                      className={`text-xs px-2 py-1 rounded-full font-medium transition-colors ${
                        rule.rule === 'delete'
                          ? 'bg-red-900/40 text-red-300 hover:bg-red-900/60'
                          : 'bg-green-900/40 text-green-300 hover:bg-green-900/60'
                      }`}
                    >
                      {rule.rule === 'delete' ? 'Delete' : 'Protect'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      rule.source === 'manual'
                        ? 'bg-blue-900/40 text-blue-300'
                        : 'bg-gray-800 text-gray-400'
                    }`}>
                      {rule.source}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                    {new Date(rule.updated_at * 1000).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleRemove(rule.sender_address)}
                      className="text-gray-600 hover:text-red-400 text-xs transition-colors"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
