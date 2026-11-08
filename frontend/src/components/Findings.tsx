import { lazy, Suspense } from 'react'
import { CircleAlert, ClipboardCheck, Code2, FileText, ShieldCheck } from 'lucide-react'
import type { Analysis, Row } from '../types'

const AnalysisChart = lazy(() => import('./AnalysisChart'))

function DataTable({ rows }: { rows: Row[] }) {
  if (!rows.length) return <p>No rows returned.</p>
  const columns = Object.keys(rows[0])
  return <div className="table-scroll"><table><thead><tr>
    {columns.map(key => <th key={key} scope="col">{key.replaceAll('_', ' ')}</th>)}
  </tr></thead><tbody>{rows.map((row, i) => <tr key={i}>
    {columns.map(key => <td key={key}>{typeof row[key] === 'number'
      ? row[key].toLocaleString('en', { maximumFractionDigits: 3 }) : row[key] ?? '—'}</td>)}
  </tr>)}</tbody></table></div>
}

export function Findings({ result }: { result: Analysis }) {
  const comparison = result.kpi_comparison
  const quality = result.data_quality
  const usage = result.execution_metadata.provider_usage
  const rate = result.plan?.metric.endsWith('_rate')
  const value = (number: number | null) => number === null ? '—' : rate ? number.toFixed(2) + '%' : number.toLocaleString('en')
  return <div className="results">
    <section className="card answer" aria-labelledby="answer-title">
      <div className="card-heading"><span className="tile">
        {result.status === 'ok' ? <ClipboardCheck size={19} /> : <CircleAlert size={19} />}
      </span><div><h2 id="answer-title">Investigation result</h2><p>{result.question}</p></div>
      <span className={'pill push ' + (result.status === 'ok' ? 'good' : 'warn')}>
        {result.status === 'ok' ? 'Evidence verified' : result.status}
      </span></div>
      <p className="answer-summary" role="status">{result.summary}</p>
      {usage && <p className="my-2 text-sm text-slate-600">
        {usage.provider === 'groq' ? 'Groq' : 'OpenAI'} · {usage.model} · {usage.input_tokens} input / {usage.output_tokens} output tokens
        {usage.estimated_cost_usd !== null ? ' · Estimated $' + usage.estimated_cost_usd.toFixed(6) : ''}
      </p>}
      {comparison && result.status === 'ok' && <div className="comparison">
        <div><span>{comparison.previous_period}</span><strong>{value(comparison.previous_value)}</strong>
          <small>{comparison.previous_valid.toLocaleString('en')} valid · {comparison.previous_late} late</small></div>
        <div><span>{comparison.current_period}</span><strong>{value(comparison.current_value)}</strong>
          <small>{comparison.current_valid.toLocaleString('en')} valid · {comparison.current_late} late</small></div>
        {comparison.change_pp !== null && <div><span>Change</span>
          <strong className={comparison.change_pp < 0 && result.plan?.metric === 'on_time_rate' ? 'negative' : ''}>
            {comparison.change_pp > 0 ? '+' : ''}{comparison.change_pp.toFixed(2)} pp</strong></div>}
      </div>}
      {result.findings.map(finding => <div className="finding" key={finding.title}>
        <h3>{finding.title}</h3><p>{finding.detail}</p>
      </div>)}
      {result.kpi_definition && <details className="plain-detail"><summary>KPI definition</summary>
        <p>{result.kpi_definition.formula}. {result.kpi_definition.rule}</p></details>}
    </section>
    {result.chart_data && <Suspense fallback={<p role="status">Loading chart…</p>}>
      <AnalysisChart chart={result.chart_data} />
    </Suspense>}
    {quality && <section className="card quality"><div className="card-heading"><span className="tile">
      <ShieldCheck size={18} /></span><div><h2>Data quality</h2><p>Reporting cohort and exclusions</p></div></div>
      <dl className="quality-grid">
        {Object.entries({
          'Scoped records': quality.records, 'Valid deliveries': quality.valid_deliveries,
          'Excluded records': quality.excluded, 'KPI eligible': quality.completeness_pct === null
            ? '—' : quality.completeness_pct.toFixed(2) + '%',
          'Missing actual': quality.missing_actual, 'Missing promise': quality.missing_promise,
          Pending: quality.pending, Cancelled: quality.cancelled, 'After cutoff': quality.after_cutoff,
        }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
      <ul className="caveats">{result.caveats.map(caveat => <li key={caveat}>{caveat}</li>)}</ul>
    </section>}
    {!!result.supporting_evidence.length && <details className="card evidence"><summary><FileText size={18} />
      Supporting data</summary><DataTable rows={result.supporting_evidence} /></details>}
    {!!result.sql_evidence.length && <section className="card evidence"><div className="card-heading">
      <span className="tile"><Code2 size={18} /></span><div><h2>Executed SQL</h2><p>Read-only queries and bound parameters</p></div>
      <span className="pill push">{result.execution_metadata.query_count} queries</span></div>
      {result.sql_evidence.map(query => <details key={query.query_id}><summary>
        <code>{query.query_id}</code><span className="query-info">{query.status} · {query.row_count} rows · {query.elapsed_ms} ms</span>
      </summary><pre>{query.sql}</pre><h3>Bound parameters</h3><pre>{JSON.stringify(query.parameters, null, 2)}</pre>
        <DataTable rows={query.rows} /></details>)}
    </section>}
  </div>
}
