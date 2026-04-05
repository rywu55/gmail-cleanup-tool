import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import SenderRules from '../views/SenderRules'

const mockRule = {
  sender_address: 'promo@zillow.com',
  sender_domain: 'zillow.com',
  display_name: 'Zillow',
  rule: 'delete',
  source: 'auto',
  created_at: 1700000000,
  updated_at: 1700000000,
}

describe('SenderRules', () => {
  it('renders list of rules ordered by updated_at desc', async () => {
    const rules = [
      { ...mockRule, sender_address: 'a@x.com', updated_at: 1700000002 },
      { ...mockRule, sender_address: 'b@x.com', updated_at: 1700000001 },
    ]
    server.use(
      http.get('/api/rules', () => HttpResponse.json({ rules }))
    )
    render(<SenderRules />)
    const rows = await screen.findAllByText(/@x\.com/)
    expect(rows[0].textContent).toContain('a@x.com')
  })

  it('shows rule type badge for each rule', async () => {
    server.use(
      http.get('/api/rules', () => HttpResponse.json({ rules: [mockRule] }))
    )
    render(<SenderRules />)
    await screen.findByText('Delete')
  })

  it('shows source badge (auto/manual)', async () => {
    server.use(
      http.get('/api/rules', () => HttpResponse.json({ rules: [mockRule] }))
    )
    render(<SenderRules />)
    await screen.findByText('auto')
  })

  it('shows empty state when no rules', async () => {
    render(<SenderRules />)
    await screen.findByText(/no sender rules yet/i)
  })

  it('adds a new rule on form submit', async () => {
    const user = userEvent.setup()
    let addCalled = false
    server.use(
      http.post('/api/rules', async ({ request }) => {
        addCalled = true
        const body = await request.json() as { sender_address: string; rule: string }
        return HttpResponse.json({
          ...mockRule,
          sender_address: body.sender_address,
          source: 'manual',
        })
      }),
      http.get('/api/rules', () => HttpResponse.json({ rules: [] }))
    )

    render(<SenderRules />)
    const input = await screen.findByPlaceholderText(/sender@example\.com/i)
    await user.type(input, 'new@example.com')
    await user.click(screen.getByRole('button', { name: /add/i }))

    await waitFor(() => expect(addCalled).toBe(true))
  })

  it('removes a rule with confirmation', async () => {
    let deleteCalled = false
    server.use(
      http.get('/api/rules', () => HttpResponse.json({ rules: [mockRule] })),
      http.delete('/api/rules/:addr', () => {
        deleteCalled = true
        return new HttpResponse(null, { status: 204 })
      })
    )

    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<SenderRules />)
    const removeBtn = await screen.findByRole('button', { name: /remove/i })
    fireEvent.click(removeBtn)
    await waitFor(() => expect(deleteCalled).toBe(true))
  })

  it('does not remove rule if confirm is cancelled', async () => {
    let deleteCalled = false
    server.use(
      http.get('/api/rules', () => HttpResponse.json({ rules: [mockRule] })),
      http.delete('/api/rules/:addr', () => {
        deleteCalled = true
        return new HttpResponse(null, { status: 204 })
      })
    )

    vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<SenderRules />)
    const removeBtn = await screen.findByRole('button', { name: /remove/i })
    fireEvent.click(removeBtn)
    await waitFor(() => expect(deleteCalled).toBe(false))
  })

  it('toggles rule type when badge is clicked', async () => {
    let updatedRule: string | null = null
    server.use(
      http.get('/api/rules', () => HttpResponse.json({ rules: [mockRule] })),
      http.post('/api/rules', async ({ request }) => {
        const body = await request.json() as { rule: string }
        updatedRule = body.rule
        return HttpResponse.json({ ...mockRule, rule: body.rule, source: 'manual' })
      })
    )

    render(<SenderRules />)
    const badge = await screen.findByRole('button', { name: /delete/i })
    fireEvent.click(badge)
    await waitFor(() => expect(updatedRule).toBe('protect'))
  })
})
