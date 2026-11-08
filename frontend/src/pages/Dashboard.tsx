import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, BarChart3, Boxes, CalendarDays, CheckCircle2, Clock3, FlaskConical, LoaderCircle, Search, Truck } from 'lucide-react'
import { Findings } from '../components/Findings'
import { Workflow } from '../components/Workflow'
import { useInvestigation } from '../hooks/useInvestigation'
import { api } from '../services/api'
import type { Example, Metadata, Mode, Value } from '../types'

const count = (value: Value | undefined) => typeof value === 'number' ? value.toLocaleString('en') : '—'
const percent = (value: Value | undefined) => typeof value === 'number' ? value.toFixed(2) + '%' : '—'
const month = (value?: string) => value ? new Date(value + '-01T00:00:00Z').toLocaleDateString('en', {
  month: 'short', year: 'numeric', timeZone: 'UTC',
}) : '—'

export function Dashboard({ metadata, mode, loadError }: { metadata: Metadata | null; mode: Mode; loadError: string }) {
  const [question, setQuestion] = useState('')
  const [examples, setExamples] = useState<Example[]>([])
  const [examplesError, setExamplesError] = useState(false)
  const investigation = useInvestigation()

  useEffect(() => {
    let active = true
    setExamples([])
    setExamplesError(false)
    api<Example[]>('/examples?mode=' + mode).then(data => { if (active) setExamples(data) })
      .catch(() => { if (active) setExamplesError(true) })
    return () => { active = false }
  }, [mode])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (question.trim().length >= 3) void investigation.run(question.trim(), mode)
  }

  const overview = metadata?.overview
  const metrics = [
    { label: 'On-time delivery', value: percent(overview?.on_time_rate), detail: 'Across the full snapshot', Icon: CheckCircle2, tone: 'teal' },
    { label: 'Valid deliveries', value: count(overview?.valid_deliveries), detail: 'Completed and KPI eligible', Icon: Boxes, tone: 'blue' },
    { label: 'Late deliveries', value: count(overview?.late_deliveries), detail: 'Arrived after the promise', Icon: Clock3, tone: 'amber' },
    { label: 'Latest reporting period', value: month(metadata?.dataset.latest_month), detail: 'Last complete snapshot month', Icon: CalendarDays, tone: 'violet' },
  ]

  return <>
    <header className="hero"><span className="eyebrow"><Truck size={16} /> DELIVERY OPERATIONS</span>
      <h1>Agentic AI Business Analytics Copilot</h1>
      <p>Investigate operational performance with AI-assisted SQL analytics and verified evidence.</p>
    </header>
    <div className="dataset"><FlaskConical size={17} /><strong>Simulated dataset</strong>
      <span>{metadata ? month(metadata.dataset.first_month) + ' – ' + month(metadata.dataset.latest_month) : loadError ? 'Unavailable' : 'Loading…'}</span>
      <span className="pill push">{metadata ? 'Snapshot ' + metadata.dataset.version : 'SQLite snapshot'}</span>
    </div>
    {loadError && <p role="alert" className="error">{loadError}</p>}
    <div className="metric-grid">
      {metrics.map(({ label, value, detail, Icon, tone }) => <section className="card metric" key={label}>
        <div className="metric-top"><h2>{label}</h2><span className={'tile ' + tone}><Icon size={17} /></span></div>
        <strong>{value}</strong><p>{detail}</p>
      </section>)}
    </div>
    <div className="investigation-grid">
      <section className="card question" aria-labelledby="question-title">
        <div className="card-heading"><span className="tile"><Search size={19} /></span><div>
          <h2 id="question-title">Ask an operational question</h2><p>Explore shipment KPIs, compare periods, and investigate delivery drivers.</p>
        </div></div>
        {mode === 'llm' && <p className="mb-3 text-sm text-slate-600">
          {metadata?.llm_model} interprets your question. Shipment rows and SQL evidence stay in this application.
        </p>}
        <form onSubmit={submit}>
          <label htmlFor="question" className="sr-only">Delivery analytics question</label>
          <textarea id="question" rows={3} maxLength={600} required minLength={3} value={question}
            placeholder="Why did our on-time delivery rate decrease in May?" onChange={event => setQuestion(event.target.value)} />
          <div className="form-footer"><small>{question.length} / 600</small>
            <button className="primary" type="submit" disabled={investigation.loading || question.trim().length < 3}>
              {investigation.loading ? <><LoaderCircle className="spin" size={16} /> Investigating…</>
                : <>Run investigation <ArrowRight size={16} /></>}</button></div>
        </form>
        {investigation.error && <p className="error" role="alert">{investigation.error}</p>}
        <div className="examples"><h3>Try an example</h3>
          {examplesError ? <p>Example questions are unavailable.</p>
            : <div className="chips">{examples.map(example => <button type="button" key={example.label}
              disabled={investigation.loading} onClick={() => {
                setQuestion(example.question)
                void investigation.run(example.question, mode)
              }}>{example.label}<ArrowRight size={13} /></button>)}</div>}
        </div>
      </section>
      <Workflow steps={investigation.steps} />
    </div>
    {investigation.result ? <Findings result={investigation.result} />
      : <section className="card empty" aria-live="polite"><span className="tile"><BarChart3 size={20} /></span>
        <h2>{investigation.loading ? 'Investigation in progress' : 'Your investigation will appear here'}</h2>
        <p>{investigation.loading ? 'Follow the live workflow above.' : 'Run a question to see the analysis, charts, and executed SQL.'}</p>
      </section>}
  </>
}
