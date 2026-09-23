import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Link, useRouteError } from 'react-router-dom'

export function RouteErrorPage() {
  useRouteError()

  return (
    <main
      className="mx-auto flex min-h-screen w-full max-w-2xl items-center px-4 py-10 sm:px-6"
      id="main-content"
    >
      <section className="surface-card w-full p-6 sm:p-8" aria-labelledby="route-error-title">
        <span className="feature-icon text-red-200">
          <AlertTriangle aria-hidden="true" size={21} />
        </span>
        <p className="eyebrow mt-5">Application error</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-100" id="route-error-title">
          This page could not be displayed
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          An unexpected interface error occurred. No technical error details are exposed here.
        </p>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row">
          <Link className="secondary-button" to="/incidents">
            Return to incidents
          </Link>
          <button className="primary-button" onClick={() => window.location.reload()} type="button">
            <RefreshCw aria-hidden="true" size={16} />
            Reload page
          </button>
        </div>
      </section>
    </main>
  )
}
