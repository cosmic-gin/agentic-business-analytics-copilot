import { expect, test } from '@playwright/test'
import type { Analysis } from '../src/types'

test('configured LLM mode submits its mode and displays provider provenance', async ({ page }) => {
  const question = 'Why did on-time delivery decline in May?'
  const demo = await page.request.post('/api/ask', { data: { mode: 'demo', question } })
  expect(demo.ok()).toBe(true)
  const result = await demo.json() as Analysis

  await page.route('**/api/metadata', async route => {
    const response = await route.fetch()
    await route.fulfill({ response, json: {
      ...await response.json(), enabled_modes: ['demo', 'llm'], default_mode: 'demo',
      llm_provider: 'groq', llm_model: 'openai/gpt-oss-20b',
    } })
  })
  await page.route('**/api/ask/stream', async route => {
    expect(route.request().postDataJSON()).toEqual({ mode: 'llm', question })
    const body = JSON.stringify({ type: 'result', result: {
      ...result, mode: 'llm', execution_metadata: {
        ...result.execution_metadata,
        provider_usage: {
          provider: 'groq', model: 'openai/gpt-oss-20b', input_tokens: 100, output_tokens: 25, estimated_cost_usd: null,
        },
      },
    } }) + '\n'
    await route.fulfill({ status: 200, contentType: 'application/x-ndjson', body })
  })
  await page.goto('/')
  const mode = page.getByLabel('Planner mode')
  await expect(mode.getByRole('option', { name: 'LLM mode · Groq' })).toBeEnabled()
  await mode.selectOption('llm')
  await expect(page.getByText(/Shipment rows and SQL evidence stay/)).toBeVisible()
  await page.getByLabel('Delivery analytics question').fill(question)
  await page.getByRole('button', { name: 'Run investigation' }).click()
  await expect(page.getByText(/Groq · openai\/gpt-oss-20b · 100 input \/ 25 output tokens/)).toBeVisible()
  await expect(page.getByText('-3.00 pp', { exact: true })).toBeVisible()
})
