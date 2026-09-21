import { Braces, CheckCircle2, Clock3, ShieldAlert } from 'lucide-react'

const principles = [
  {
    icon: CheckCircle2,
    title: 'Observed evidence',
    detail: 'Logs, traces, metrics, and changes retain their source provenance.',
  },
  {
    icon: Braces,
    title: 'Bounded hypotheses',
    detail: 'Model output stays separate from verified observations and contradictions.',
  },
  {
    icon: ShieldAlert,
    title: 'Visible uncertainty',
    detail: 'Missing signals and abstaining results are first-class outcomes.',
  },
]

export function FoundationNotice() {
  return (
    <section aria-labelledby="foundation-title" className="mt-8">
      <div className="surface-card overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-slate-800/80 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
          <div>
            <p className="eyebrow">Frontend foundation</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-100" id="foundation-title">
              The workspace is ready for its API contract
            </h2>
          </div>
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-amber-300/15 bg-amber-300/[0.06] px-3 py-1.5 text-xs font-medium text-amber-200">
            <Clock3 aria-hidden="true" size={14} />
            Foundation only
          </span>
        </div>

        <div className="grid gap-px bg-slate-800/70 md:grid-cols-3">
          {principles.map((principle) => {
            const Icon = principle.icon

            return (
              <article className="bg-slate-900/80 p-5 sm:p-6" key={principle.title}>
                <Icon aria-hidden="true" className="text-cyan-300" size={19} strokeWidth={1.8} />
                <h3 className="mt-4 text-sm font-semibold text-slate-100">{principle.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">{principle.detail}</p>
              </article>
            )
          })}
        </div>
      </div>
    </section>
  )
}
