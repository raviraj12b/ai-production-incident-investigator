import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { App } from '../app/App'
import { AppProviders } from '../app/AppProviders'
import { RouteErrorPage } from '../pages/RouteErrorPage'
import { ErrorState, LoadingState } from './ApiState'

function renderApp(path = '/incidents') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppProviders>
        <App />
      </AppProviders>
    </MemoryRouter>,
  )
}

describe('responsive and accessibility hardening', () => {
  it('moves focus into the mobile navigation and restores it when Escape closes the panel', async () => {
    const user = userEvent.setup()
    renderApp()
    const menuButton = screen.getByRole('button', { name: 'Open navigation' })

    await user.click(menuButton)
    const panel = screen.getByRole('complementary', { name: 'Mobile navigation panel' })
    const mobileLink = within(panel).getByRole('link', { name: 'Incidents' })
    await waitFor(() => expect(mobileLink).toHaveFocus())

    await user.keyboard('{Escape}')

    expect(
      screen.queryByRole('complementary', { name: 'Mobile navigation panel' }),
    ).not.toBeInTheDocument()
    expect(menuButton).toHaveFocus()
    expect(menuButton).toHaveAttribute('aria-expanded', 'false')
  })

  it('focuses and announces main content after client-side route navigation', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(screen.getByRole('link', { name: 'New incident' }))

    expect(screen.getByRole('heading', { level: 1, name: 'Create incident' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('main')).toHaveFocus())
    expect(screen.getByText('Create incident page loaded')).toHaveAttribute('aria-live', 'polite')
    expect(document.title).toBe('Create incident | Incident Investigator')
  })

  it('announces loading and exposes narrow-screen error recovery', async () => {
    const retry = vi.fn()
    const view = render(<LoadingState label="Loading evidence…" />)

    const loading = screen.getByRole('status')
    expect(loading).toHaveAttribute('aria-live', 'polite')
    expect(loading).toHaveAttribute('aria-busy', 'true')

    view.rerender(<ErrorState error={new Error('failed')} onRetry={retry} />)
    const retryButton = screen.getByRole('button', { name: 'Retry' })
    expect(retryButton).toHaveClass('w-full', 'sm:w-auto')
    await userEvent.click(retryButton)
    expect(retry).toHaveBeenCalledOnce()
  })

  it('renders a safe route-level recovery boundary without exposing error details', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    function BrokenRoute(): never {
      throw new Error('sensitive internal failure detail')
    }
    const router = createMemoryRouter([
      { path: '/', element: <BrokenRoute />, errorElement: <RouteErrorPage /> },
    ])

    render(<RouterProvider router={router} />)

    expect(
      await screen.findByRole('heading', { name: 'This page could not be displayed' }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/sensitive internal failure detail/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Return to incidents' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload page' })).toBeInTheDocument()
    consoleError.mockRestore()
  })

  it('keeps the hardened normal-text token above AA contrast and preserves reduced motion', () => {
    const styles = readFileSync(resolve(process.cwd(), 'src/styles.css'), 'utf8')

    expect(contrastRatio('#94a3b8', '#020617')).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio('#94a3b8', '#0f172a')).toBeGreaterThanOrEqual(4.5)
    expect(contrastRatio('#67e8f9', '#020617')).toBeGreaterThanOrEqual(3)
    expect(styles).toContain('placeholder:text-slate-400')
    expect(styles).toContain('.metadata-label')
    expect(styles).toContain('text-slate-400')
    expect(styles).toContain('@media (prefers-reduced-motion: reduce)')
    expect(styles).toContain('animation-duration: 0.01ms !important')
  })
})

function contrastRatio(foreground: string, background: string): number {
  const foregroundLuminance = relativeLuminance(foreground)
  const backgroundLuminance = relativeLuminance(background)
  return (
    (Math.max(foregroundLuminance, backgroundLuminance) + 0.05) /
    (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
  )
}

function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => Number.parseInt(hex.slice(start, start + 2), 16) / 255)
  const [red = 0, green = 0, blue = 0] = channels.map((channel) =>
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  )
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue
}
