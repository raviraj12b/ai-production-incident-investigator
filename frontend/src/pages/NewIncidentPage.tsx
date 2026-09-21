import { ArrowLeft, ClipboardPlus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PageHeader } from '../components/PageHeader'

export function NewIncidentPage() {
  return (
    <>
      <Link className="back-link" to="/incidents">
        <ArrowLeft aria-hidden="true" size={16} />
        Incidents
      </Link>
      <div className="mt-6">
        <PageHeader
          description="Manual incident intake is the defined starting point. Automatic anomaly detection is outside the current product boundary."
          eyebrow="Incident intake"
          title="Create incident"
        />
      </div>

      <section className="mt-8 surface-card p-6 sm:p-8" aria-labelledby="form-contract-title">
        <span className="feature-icon" aria-hidden="true">
          <ClipboardPlus size={21} />
        </span>
        <h2 className="mt-5 text-lg font-semibold text-slate-100" id="form-contract-title">
          Form contract arrives in 06.4
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          The route and responsive layout are established. Inputs will be added only after the
          generated API types and error handling are verified in 06.3.
        </p>
      </section>
    </>
  )
}
