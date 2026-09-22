import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

export function CopyIdentifier({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1_500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="min-w-0">
      <p className="metadata-label">{label}</p>
      <div className="mt-1 flex items-start gap-2">
        <code className="min-w-0 flex-1 break-all text-xs leading-5 text-slate-400">{value}</code>
        <button
          aria-label={`Copy ${label}`}
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-800 hover:text-cyan-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"
          onClick={() => void copy()}
          type="button"
        >
          {copied ? <Check aria-hidden="true" size={14} /> : <Copy aria-hidden="true" size={14} />}
        </button>
      </div>
      <span className="sr-only" role="status">
        {copied ? `${label} copied` : ''}
      </span>
    </div>
  )
}
