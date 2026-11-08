import { Check, Circle, LoaderCircle, Minus, Workflow as WorkflowIcon, X } from 'lucide-react'
import type { WorkflowStep } from '../types'

const icons = { pending: Circle, running: LoaderCircle, successful: Check, failed: X, skipped: Minus }

export function Workflow({ steps }: { steps: WorkflowStep[] }) {
  const done = steps.filter(step => step.status === 'successful').length
  return <section className="card workflow" aria-labelledby="workflow-title">
    <div className="card-heading"><span className="tile"><WorkflowIcon size={18} /></span><div>
      <h2 id="workflow-title">Agent workflow</h2><p>Live execution trace</p>
    </div><span className="pill push">{done} / {steps.length}</span></div>
    <ol className="steps">
      {steps.map(step => {
        const Icon = icons[step.status]
        return <li key={step.key} data-status={step.status}>
          <span className="step-icon"><Icon size={13} /></span>
          <span>{step.label}</span><span className="step-status">{step.status}</span>
        </li>
      })}
    </ol>
  </section>
}
