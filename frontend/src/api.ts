export interface SyncStatus {
  last_synced_at: number | null
  total_fetched: number
  is_syncing: boolean
}

export interface ReviewRow {
  email_id: string
  sender_address: string
  display_name: string | null
  subject: string
  date: number
  pre_selected: boolean
  reason: string | null
}

export interface ReviewResponse {
  emails: ReviewRow[]
}

export interface DeleteRequest {
  deleted_ids: string[]
  protected_ids: string[]
}

export interface DeleteResponse {
  deleted: number
  failed: string[]
  rules_saved: boolean
}

export interface SenderRule {
  sender_address: string
  sender_domain: string
  display_name: string | null
  rule: 'delete' | 'protect'
  source: 'auto' | 'manual'
  created_at: number
  updated_at: number
}

export interface SenderRulesListResponse {
  rules: SenderRule[]
}

export interface SenderRuleRequest {
  sender_address: string
  rule: 'delete' | 'protect'
  display_name?: string | null
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, options)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  auth: {
    status: () => request<{ authenticated: boolean }>('/api/auth/status'),
    start: () => request<{ authenticated: boolean }>('/api/auth/start'),
    revoke: () => request<{ revoked: boolean }>('/api/auth', { method: 'DELETE' }),
  },

  sync: {
    start: () => request<SyncStatus>('/api/sync', { method: 'POST' }),
    status: () => request<SyncStatus>('/api/sync/status'),
  },

  review: {
    get: () => request<ReviewResponse>('/api/review'),
  },

  delete: {
    execute: (body: DeleteRequest) =>
      request<DeleteResponse>('/api/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
  },

  rules: {
    list: () => request<SenderRulesListResponse>('/api/rules'),
    add: (body: SenderRuleRequest) =>
      request<SenderRule>('/api/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    remove: (senderAddress: string) =>
      request<void>(`/api/rules/${encodeURIComponent(senderAddress)}`, { method: 'DELETE' }),
  },
}
