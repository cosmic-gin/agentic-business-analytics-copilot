import { defineConfig } from '@playwright/test'

const production = process.env.PLAYWRIGHT_PRODUCTION === '1'
const baseURL = production ? 'http://127.0.0.1:8000' : 'http://127.0.0.1:5173'

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  use: { baseURL, channel: process.env.PLAYWRIGHT_CHANNEL || undefined },
  webServer: [
    {
      command: 'uv run --no-sync uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-access-log',
      cwd: '..',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
    },
    ...production ? [] : [{
      command: 'pnpm dev --host 127.0.0.1 --strictPort',
      url: baseURL,
      reuseExistingServer: !process.env.CI,
    }],
  ],
})
