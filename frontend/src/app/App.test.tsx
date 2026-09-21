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
  it('renders the evidence-focused incidents workspace without claiming API connectivity', () => {
    renderApp()

    expect(screen.getByRole('heading', { level: 1, name: 'Incidents' })).toBeInTheDocument()
    expect(screen.getAllByText('Not checked').length).toBeGreaterThan(0)
    expect(screen.getByText(/does not fabricate incidents/i)).toBeInTheDocument()
  })

  it('navigates to the incident intake foundation', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(screen.getByRole('link', { name: /new incident/i }))

    expect(screen.getByRole('heading', { level: 1, name: 'Create incident' })).toBeInTheDocument()
    expect(screen.getByText(/automatic anomaly detection is outside/i)).toBeInTheDocument()
  })

  it('renders an honest investigation placeholder for a deep link', () => {
    renderApp('/investigations/investigation-123')

    expect(
      screen.getByRole('heading', { level: 1, name: 'Evidence workspace' }),
    ).toBeInTheDocument()
    expect(screen.getByText('investigation-123')).toBeInTheDocument()
    expect(screen.getByText(/shows no generated cause/i)).toBeInTheDocument()
  })
})
