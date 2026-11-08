import type { AnalysisEvent, Mode } from '../types'

async function requireOk(response: Response) {
  if (response.ok) return response
  const body = await response.json().catch(() => null)
  throw new Error(body?.error?.message ?? 'The analytics service could not complete the request.')
}

export async function api<T>(path: string): Promise<T> {
  const response = await requireOk(await fetch('/api' + path))
  return response.json() as Promise<T>
}

export async function streamAnalysis(
  question: string, mode: Mode, onEvent: (event: AnalysisEvent) => void, signal: AbortSignal,
) {
  const response = await requireOk(await fetch('/api/ask/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, mode }),
    signal,
  }))
  if (!response.body) throw new Error('The analytics stream is unavailable.')
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  let receivedResult = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += value
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.trim()) continue
        const event = JSON.parse(line) as AnalysisEvent
        if (event.type === 'error') throw new Error(event.message)
        if (event.type === 'result') receivedResult = true
        onEvent(event)
      }
    }
    if (!receivedResult) throw new Error('The analysis ended before a result arrived.')
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
