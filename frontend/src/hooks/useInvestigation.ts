import { useEffect, useRef, useState } from 'react'
import { streamAnalysis } from '../services/api'
import type { Analysis, Mode, WorkflowStep } from '../types'

const labels = {
  interpret: 'Interpret question',
  validate: 'Validate analytical intent',
  definition: 'Retrieve KPI definition',
  plan: 'Create analysis plan',
  select: 'Select approved tools',
  execute: 'Execute read-only SQL',
  quality: 'Validate data quality',
  verify: 'Verify analytical evidence',
  answer: 'Generate grounded answer',
}

function pending(): WorkflowStep[] {
  return Object.entries(labels).map(([key, label]) => ({ key, label, status: 'pending' }))
}

export function useInvestigation() {
  const [steps, setSteps] = useState(pending)
  const [result, setResult] = useState<Analysis | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const active = useRef<AbortController | null>(null)
  useEffect(() => () => active.current?.abort(), [])

  async function run(question: string, mode: Mode) {
    if (active.current) return
    const controller = new AbortController()
    active.current = controller
    setLoading(true)
    setError('')
    setResult(null)
    setSteps(pending())
    try {
      await streamAnalysis(question, mode, event => {
        if (event.type === 'step') setSteps(current => current.map(step => step.key === event.step.key ? event.step : step))
        if (event.type === 'result') {
          setResult(event.result)
          setSteps(event.result.workflow_steps)
        }
      }, controller.signal)
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(failure instanceof Error ? failure.message : 'Analysis failed.')
        setSteps(current => current.map(step => step.status === 'running' ? { ...step, status: 'failed' } : step))
      }
    } finally {
      active.current = null
      if (!controller.signal.aborted) setLoading(false)
    }
  }
  return { steps, result, error, loading, run }
}
