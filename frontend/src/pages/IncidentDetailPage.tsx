import { ArrowLeft, Fingerprint } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../components/PageHeader'

export function IncidentDetailPage() {
  const { incidentId } = useParams()

  return (
    <>
      <Link className="back-link" to="/incidents">
        <ArrowLeft aria-hidden="true" size={16} />
        Incidents
      </Link>
      <div className="mt-6">
        <PageHeader
          description="Incident metadata and investigation history will be loaded from the versioned product API."
          eyebrow="Incident detail"
          title="Incident workspace"
        />
      </div>
      <section className="mt-8 surface-card p-6" aria-label="Requested incident identifier">
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <Fingerprint aria-hidden="true" className="text-cyan-300" size={18} />
          <span className="font-mono text-xs text-slate-300 break-all">{incidentId}</span>
        </div>
        <p className="mt-4 text-sm leading-6 text-slate-500">
          Data has not been requested because API integration belongs to 06.3.
        </p>
      </section>
    </>
  )
}
