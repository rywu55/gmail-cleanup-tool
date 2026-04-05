import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Review from '../views/Review'

const mockCandidate = {
  email_id: 'm1',
  sender_address: 'promo@zillow.com',
  display_name: 'Zillow',
  subject: 'Homes near you',
  date: 1700000000,
  pre_selected: true,
  reason: 'Promotional signals',
}

describe('Review', () => {
  const noop = () => {}

  beforeEach(() => {
    server.use(
      http.get('/api/sync/status', () =>
        HttpResponse.json({ last_synced_at: 1700000000, total_fetched: 1, is_syncing: false })
      ),
      http.get('/api/review', () =>
        HttpResponse.json({ emails: [mockCandidate] })
      ),
    )
  })

  it('pre-selects promotional emails by default', async () => {
    render(<Review onNavigateToRules={noop} />)
    const checkbox = await screen.findByRole('checkbox')
    expect(checkbox).toBeChecked()
  })

  it('deselecting a row removes it from the pending count', async () => {
    render(<Review onNavigateToRules={noop} />)
    const checkbox = await screen.findByRole('checkbox')
    fireEvent.click(checkbox)
    await waitFor(() => {
      expect(screen.getByText(/0 selected for deletion/)).toBeInTheDocument()
    })
  })

  it('shows delete button with count of selected emails', async () => {
    render(<Review onNavigateToRules={noop} />)
    const btn = await screen.findByRole('button', { name: /delete 1 email/i })
    expect(btn).toBeInTheDocument()
  })

  it('shows confirmation dialog with exact count when delete clicked', async () => {
    render(<Review onNavigateToRules={noop} />)
    const btn = await screen.findByRole('button', { name: /delete 1 email/i })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(screen.getByText(/permanently delete 1 email/i)).toBeInTheDocument()
    })
  })

  it('disables re-sync button while deletion is in progress', async () => {
    server.use(
      http.post('/api/delete', async () => {
        await new Promise(r => setTimeout(r, 100))
        return HttpResponse.json({ deleted: 1, failed: [], rules_saved: true })
      })
    )

    render(<Review onNavigateToRules={noop} />)
    const deleteBtn = await screen.findByRole('button', { name: /delete 1 email/i })
    fireEvent.click(deleteBtn)
    const confirmBtn = await screen.findByRole('button', { name: /confirm delete/i })
    fireEvent.click(confirmBtn)

    const resyncBtn = screen.getByRole('button', { name: /re-sync/i })
    expect(resyncBtn).toBeDisabled()
  })

  it('shows result summary after deletion', async () => {
    server.use(
      http.post('/api/delete', () =>
        HttpResponse.json({ deleted: 1, failed: [], rules_saved: true })
      )
    )
    render(<Review onNavigateToRules={noop} />)
    const deleteBtn = await screen.findByRole('button', { name: /delete 1 email/i })
    fireEvent.click(deleteBtn)
    const confirmBtn = await screen.findByRole('button', { name: /confirm delete/i })
    fireEvent.click(confirmBtn)
    await screen.findByText(/1 email deleted/i)
  })

  it('shows re-sync button only after deletion completes', async () => {
    server.use(
      http.post('/api/delete', () =>
        HttpResponse.json({ deleted: 1, failed: [], rules_saved: true })
      )
    )
    render(<Review onNavigateToRules={noop} />)
    const deleteBtn = await screen.findByRole('button', { name: /delete 1 email/i })
    fireEvent.click(deleteBtn)
    const confirmBtn = await screen.findByRole('button', { name: /confirm delete/i })
    fireEvent.click(confirmBtn)
    const resync = await screen.findByRole('button', { name: /re-sync next batch/i })
    expect(resync).not.toBeDisabled()
  })

  it('shows empty state when no emails loaded', async () => {
    server.use(
      http.get('/api/review', () => HttpResponse.json({ emails: [] }))
    )
    render(<Review onNavigateToRules={noop} />)
    await screen.findByText(/no emails loaded/i)
  })

  it('shows failed IDs in result when batchDelete partially fails', async () => {
    server.use(
      http.post('/api/delete', () =>
        HttpResponse.json({ deleted: 0, failed: ['m1'], rules_saved: true })
      )
    )
    render(<Review onNavigateToRules={noop} />)
    const deleteBtn = await screen.findByRole('button', { name: /delete 1 email/i })
    fireEvent.click(deleteBtn)
    const confirmBtn = await screen.findByRole('button', { name: /confirm delete/i })
    fireEvent.click(confirmBtn)
    await screen.findByText(/1 failed to delete/i)
  })

  it('shows warning when rules_saved is false', async () => {
    server.use(
      http.post('/api/delete', () =>
        HttpResponse.json({ deleted: 1, failed: [], rules_saved: false })
      )
    )
    render(<Review onNavigateToRules={noop} />)
    const deleteBtn = await screen.findByRole('button', { name: /delete 1 email/i })
    fireEvent.click(deleteBtn)
    const confirmBtn = await screen.findByRole('button', { name: /confirm delete/i })
    fireEvent.click(confirmBtn)
    await screen.findByText(/sender rules could not be saved/i)
  })
})
