import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App } from './App'
import { AppProviders } from './AppProviders'

function renderApp(path = '/incidents') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppProviders>
        <App />
      </AppProviders>
    </MemoryRouter>,
  )
}

describe('App foundation', () => {
  it('renders incidents returned by the API', async () => {
    renderApp()

    expect(screen.getByRole('heading', { level: 1, name: 'Incidents' })).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Checkout latency increase' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/filters apply only to this loaded page/i)).toBeInTheDocument()
  })

  it('navigates to manual incident intake', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(screen.getByRole('link', { name: /new incident/i }))

    expect(screen.getByRole('heading', { level: 1, name: 'Create incident' })).toBeInTheDocument()
    expect(screen.getByText(/automatic anomaly detection is outside/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create incident' })).toBeInTheDocument()
  })

  it('loads authoritative investigation state for a deep link', async () => {
    renderApp('/investigations/investigation-123')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'General incident investigation' }),
    ).toBeInTheDocument()
    expect(screen.getByText('investigation-123')).toBeInTheDocument()
    expect(screen.getByText('QUEUED')).toBeInTheDocument()
    expect(screen.getByText(/shows no generated cause/i)).toBeInTheDocument()
  })
})
