import { ArrowLeft, SearchX } from 'lucide-react'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[65vh] items-center justify-center">
      <section className="max-w-lg text-center" aria-labelledby="not-found-title">
        <span className="mx-auto feature-icon" aria-hidden="true">
          <SearchX size={22} />
        </span>
        <p className="mt-6 eyebrow">404</p>
        <h1
          className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white"
          id="not-found-title"
        >
          Workspace not found
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          The requested frontend route does not exist.
        </p>
        <Link className="secondary-button mt-7" to="/incidents">
          <ArrowLeft aria-hidden="true" size={16} />
          Return to incidents
        </Link>
      </section>
    </div>
  )
}
