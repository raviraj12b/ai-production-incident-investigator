import {
  Activity,
  ArrowRight,
  CircleDotDashed,
  FileSearch,
  Menu,
  Plus,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

import { api } from '../api/endpoints'
import { queryKeys } from '../api/queryKeys'

const navItems = [
  {
    label: 'Incidents',
    to: '/incidents',
    icon: Activity,
  },
]

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Primary navigation" className="space-y-2">
      {navItems.map((item) => {
        const Icon = item.icon

        return (
          <NavLink
            className={({ isActive }) =>
              `nav-link ${isActive ? 'nav-link-active' : 'nav-link-idle'}`
            }
            key={item.to}
            onClick={onNavigate}
            to={item.to}
          >
            <Icon aria-hidden="true" size={18} strokeWidth={1.8} />
            <span>{item.label}</span>
          </NavLink>
        )
      })}
    </nav>
  )
}

function Brand() {
  return (
    <NavLink
      aria-label="Incident Investigator home"
      className="group flex items-center gap-3"
      to="/"
    >
      <span className="brand-mark" aria-hidden="true">
        <FileSearch size={21} strokeWidth={1.8} />
      </span>
      <span>
        <span className="block text-sm font-semibold tracking-[-0.01em] text-slate-100">
          Incident Investigator
        </span>
        <span className="block text-[0.68rem] font-medium uppercase tracking-[0.18em] text-slate-500">
          Evidence console
        </span>
      </span>
    </NavLink>
  )
}

function ConnectionStatus() {
  const readinessQuery = useQuery({
    queryKey: queryKeys.system.readiness,
    queryFn: api.getReadiness,
    retry: false,
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
  })
  const ready = readinessQuery.data?.status === 'ready'

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/65 p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
        <CircleDotDashed aria-hidden="true" size={15} />
        API status
      </div>
      <p className={`mt-2 text-sm font-semibold ${ready ? 'text-emerald-300' : 'text-slate-200'}`}>
        {readinessQuery.isPending ? 'Checking…' : ready ? 'Ready' : 'Unavailable'}
      </p>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        {ready
          ? 'API process and product database are ready.'
          : readinessQuery.isPending
            ? 'Checking product and database readiness.'
            : 'The product API or database is not ready.'}
      </p>
    </div>
  )
}

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-slate-800/80 bg-slate-950/95 px-5 py-6 backdrop-blur lg:flex lg:flex-col">
        <Brand />
        <div className="mt-10">
          <p className="mb-3 px-3 text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-slate-600">
            Workspace
          </p>
          <Navigation />
        </div>

        <div className="mt-auto space-y-4">
          <ConnectionStatus />
          <div className="flex gap-3 rounded-2xl border border-cyan-400/10 bg-cyan-400/[0.04] p-4">
            <ShieldCheck className="mt-0.5 shrink-0 text-cyan-300" size={17} />
            <p className="text-xs leading-5 text-slate-400">
              Evidence stays primary. Hypotheses remain reviewable, uncertain, and traceable.
            </p>
          </div>
        </div>
      </aside>

      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-800/80 bg-slate-950/90 px-4 backdrop-blur lg:hidden">
        <Brand />
        <button
          aria-controls="mobile-navigation"
          aria-expanded={mobileOpen}
          aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
          className="icon-button"
          onClick={() => setMobileOpen((current) => !current)}
          type="button"
        >
          {mobileOpen ? <X aria-hidden="true" size={20} /> : <Menu aria-hidden="true" size={20} />}
        </button>
      </header>

      {mobileOpen ? (
        <div
          className="fixed inset-x-0 top-16 z-20 border-b border-slate-800 bg-slate-950 px-4 py-4 shadow-2xl lg:hidden"
          id="mobile-navigation"
        >
          <Navigation onNavigate={() => setMobileOpen(false)} />
          <div className="mt-4">
            <ConnectionStatus />
          </div>
        </div>
      ) : null}

      <div className="lg:pl-72">
        <main
          className="mx-auto w-full max-w-[96rem] px-4 py-7 sm:px-6 sm:py-10 lg:px-10"
          id="main-content"
        >
          <Outlet />
        </main>
      </div>

      <NavLink
        aria-label="Create incident"
        className="fixed bottom-5 right-5 z-10 inline-flex h-12 w-12 items-center justify-center rounded-full bg-cyan-300 text-slate-950 shadow-[0_12px_30px_rgba(34,211,238,0.22)] transition hover:bg-cyan-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300 lg:hidden"
        to="/incidents/new"
      >
        <Plus aria-hidden="true" size={21} />
      </NavLink>

      <span className="sr-only">
        Investigation conclusions require evidence, uncertainty, and human review.
      </span>
      <ArrowRight className="hidden" aria-hidden="true" />
    </div>
  )
}
