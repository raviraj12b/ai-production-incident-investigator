import { ArrowLeft, FileClock, Fingerprint } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../components/PageHeader'

export function InvestigationDetailPage() {
  const { investigationId } = useParams()

  return (
    <>
      <Link className="back-link" to="/incidents">
        <ArrowLeft aria-hidden="true" size={16} />
        Incidents
      </Link>
      <div className="mt-6">
        <PageHeader
          description="Evidence, hypotheses, uncertainty, provenance, ancestry, and human review will share one traceable workspace."
          eyebrow="Investigation"
          title="Evidence workspace"
        />
      </div>

      <div className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="surface-card p-6" aria-labelledby="evidence-foundation-title">
          <span className="feature-icon" aria-hidden="true">
            <FileClock size={21} />
          </span>
          <h2 className="mt-5 text-lg font-semibold text-slate-100" id="evidence-foundation-title">
            Evidence view not connected
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            This route intentionally shows no generated cause, confidence, timeline, or dependency
            relationship before the backend contract is connected.
          </p>
        </section>

        <aside className="surface-card p-6" aria-label="Requested investigation identifier">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            <Fingerprint aria-hidden="true" size={15} />
            Investigation ID
          </div>
          <p className="mt-3 break-all font-mono text-xs leading-5 text-slate-300">
            {investigationId}
          </p>
        </aside>
      </div>
    </>
  )
}
