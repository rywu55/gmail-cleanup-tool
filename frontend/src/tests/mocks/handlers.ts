import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/auth/status', () =>
    HttpResponse.json({ authenticated: true })
  ),

  http.get('/api/sync/status', () =>
    HttpResponse.json({ last_synced_at: null, total_fetched: 0, is_syncing: false })
  ),

  http.post('/api/sync', () =>
    HttpResponse.json({ last_synced_at: null, total_fetched: 0, is_syncing: true })
  ),

  http.get('/api/review', () =>
    HttpResponse.json({ emails: [] })
  ),

  http.post('/api/delete', () =>
    HttpResponse.json({ deleted: 0, failed: [], rules_saved: true })
  ),

  http.get('/api/rules', () =>
    HttpResponse.json({ rules: [] })
  ),

  http.post('/api/rules', () =>
    HttpResponse.json({
      sender_address: 'test@example.com',
      sender_domain: 'example.com',
      display_name: null,
      rule: 'delete',
      source: 'manual',
      created_at: 0,
      updated_at: 0,
    })
  ),

  http.delete('/api/rules/:senderAddress', () =>
    new HttpResponse(null, { status: 204 })
  ),
]
