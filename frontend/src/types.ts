export type Mode = 'demo' | 'llm'
export type Provider = 'openai' | 'groq'
export type Value = string | number | null
export type Row = Record<string, Value>

export interface Metadata {
  dataset: { version: string; simulated: boolean; first_month: string; latest_month: string }
  overview: Row
  enabled_modes: Mode[]
  default_mode: Mode
  llm_provider: Provider | null
  llm_model: string | null
}

export interface Example { label: string; question: string }

export interface WorkflowStep {
  key: string
  label: string
  status: 'pending' | 'running' | 'successful' | 'failed' | 'skipped'
  elapsed_ms?: number | null
}

export interface ChartData {
  kind: 'bar' | 'line'
  title: string
  x_key: string
  series: Record<string, string>
  unit: 'percent' | 'count'
  rows: Row[]
}

export interface Evidence {
  query_id: string
  sql: string
  parameters: Row
  rows: Row[]
  row_count: number
  status: string
  elapsed_ms: number
}

export interface Analysis {
  question: string
  mode: Mode
  status: 'ok' | 'ambiguous' | 'unsupported' | 'rejected' | 'error'
  summary: string
  plan: { metric: string; intent: string; scope: { start: string; end: string } } | null
  kpi_definition: { label: string; formula: string; rule?: string } | null
  kpi_comparison: {
    previous_period: string; current_period: string
    previous_value: number | null; current_value: number | null; change_pp: number | null
    previous_valid: number; current_valid: number; previous_late: number; current_late: number
  } | null
  findings: { title: string; detail: string; evidence_ids: string[] }[]
  chart_data: ChartData | null
  sql_evidence: Evidence[]
  supporting_evidence: Row[]
  data_quality: {
    records: number; valid_deliveries: number; excluded: number; completeness_pct: number | null
    pending: number; cancelled: number; missing_actual: number; missing_promise: number; after_cutoff: number
  } | null
  caveats: string[]
  workflow_steps: WorkflowStep[]
  execution_metadata: {
    query_count: number; elapsed_ms: number; request_id: string | null
    provider_usage: {
      provider: Provider | null; model: string | null; input_tokens: number; output_tokens: number
      estimated_cost_usd: number | null
    } | null
  }
}

export type AnalysisEvent =
  | { type: 'step'; step: WorkflowStep }
  | { type: 'result'; result: Analysis }
  | { type: 'error'; message: string }

export interface Metric { passed: number; total: number; rate: number | null }

export interface EvaluationReport {
  benchmark_version: string
  dataset_version: string
  generated_at: string
  mode: Mode
  provider: Provider | null
  model: string | null
  overall: Metric
  numeric_accuracy: Metric
  sql_success: Metric
  groundedness: Metric
  unsafe_rejection: Metric
  latency_ms: Record<string, number>
  average_cost_usd: number | null
  cost_status: 'not_applicable' | 'unavailable' | 'measured'
  categories: Record<string, Metric>
  cases: {
    id: string; category: string; question: string; passed: boolean; actual_status: string
    elapsed_ms: number; failure_reasons: string[]
  }[]
}
