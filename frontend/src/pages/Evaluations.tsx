import { useEffect, useState } from 'react'
import { Activity, ClipboardList, Timer } from 'lucide-react'
import { api } from '../services/api'
import type { EvaluationReport, Metric, Mode } from '../types'

const score = (metric: Metric) => metric.rate === null ? '—' : (metric.rate * 100).toFixed(1) + '%'

export function Evaluations({ mode }: { mode: Mode }) {
  const [report, setReport] = useState<EvaluationReport | null>(null)
  const [message, setMessage] = useState('Loading benchmark results…')
  useEffect(() => {
    let active = true
    api<{ status: string; report: EvaluationReport | null }>('/evaluations?mode=' + mode).then(data => {
      if (!active) return
      setReport(data.report)
      setMessage(mode === 'llm'
        ? 'Run the LLM benchmark locally to publish a report for this provider and model.'
        : 'The versioned benchmark report is unavailable.')
    }).catch(() => { if (active) setMessage('Could not load benchmark results.') })
    return () => { active = false }
  }, [mode])

  return <>
    <div className="hero"><span className="eyebrow"><ClipboardList size={15} /> QUALITY ASSURANCE</span>
      <h1>Agent evaluation</h1><p>Inspect accuracy, evidence, safety, and response times against a versioned benchmark.</p></div>
    {!report ? <section className="card empty" role="status">{message}</section> : <>
      <section className="card benchmark"><div className="card-heading"><span className="tile"><Activity size={19} /></span>
        <div><h2>Benchmark score</h2><p>{report.mode} mode · benchmark {report.benchmark_version} · dataset {report.dataset_version}
          {report.model ? ' · ' + report.provider + ' / ' + report.model : ''}</p></div>
        <strong className="score push">{score(report.overall)}</strong></div>
        <p>{report.overall.passed} of {report.overall.total} cases passed · {new Date(report.generated_at).toLocaleDateString('en-GB', { timeZone: 'UTC' })} UTC</p>
      </section>
      <div className="metric-grid">
        {Object.entries({
          'Numeric accuracy': report.numeric_accuracy, 'SQL execution': report.sql_success,
          Groundedness: report.groundedness, 'Unsafe rejection': report.unsafe_rejection,
        }).map(([label, metric]) => <section className="card metric" key={label}>
          <h2>{label}</h2><strong>{score(metric)}</strong><p>{metric.passed} / {metric.total} applicable</p>
        </section>)}
      </div>
      <section className="card benchmark"><div className="card-heading"><span className="tile"><Timer size={19} /></span>
        <div><h2>Latency and cost</h2><p>Measured on the benchmark runner</p></div></div>
        <p>Median {report.latency_ms.p50} ms · p95 {report.latency_ms.p95} ms · Cost per question {
          report.average_cost_usd === null ? report.cost_status.replaceAll('_', ' ') : '$' + report.average_cost_usd.toFixed(6)
        }</p>
      </section>
      <section className="card evidence"><h2>Results by category</h2>
        <div className="category-scores">{Object.entries(report.categories).map(([category, metric]) =>
          <span className="pill" key={category}>{category.replaceAll('_', ' ')} · {metric.passed}/{metric.total}</span>)}</div>
      </section>
      <section className="card evidence"><h2>Individual cases</h2><div className="table-scroll"><table>
        <thead><tr>{['Case', 'Question', 'Status', 'Latency', 'Result'].map(column => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody>{report.cases.map(item => <tr key={item.id}><td>{item.id}<br /><small>{item.category}</small></td>
          <td>{item.question}{item.failure_reasons.length > 0 && <ul>{item.failure_reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}</td>
          <td>{item.actual_status}</td><td>{item.elapsed_ms} ms</td>
          <td><span className={'pill ' + (item.passed ? 'good' : 'warn')}>{item.passed ? 'Pass' : 'Fail'}</span></td>
        </tr>)}</tbody></table></div></section>
    </>}
  </>
}
