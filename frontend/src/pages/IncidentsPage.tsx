import { ArrowRight, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { FoundationNotice } from '../components/FoundationNotice'
import { PageHeader } from '../components/PageHeader'

export function IncidentsPage() {
  return (
    <>
      <PageHeader
        action={
          <Link className="primary-button" to="/incidents/new">
            <Plus aria-hidden="true" size={17} />
            New incident
          </Link>
        }
        description="Start from an operational incident, follow durable investigation progress, and review every conclusion against its evidence."
        eyebrow="Operations workspace"
        title="Incidents"
      />

      <FoundationNotice />

      <section aria-labelledby="incident-list-title" className="mt-6 surface-card p-5 sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="eyebrow">Incident queue</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-100" id="incident-list-title">
              No incident data loaded
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
              The typed API layer is intentionally deferred to 06.3. This foundation does not
              fabricate incidents or claim backend connectivity.
            </p>
          </div>
          <ArrowRight
            aria-hidden="true"
            className="mt-1 hidden text-slate-700 sm:block"
            size={20}
          />
        </div>
      </section>
    </>
  )
}
