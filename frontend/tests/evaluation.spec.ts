import { expect, test } from '@playwright/test'

test('evaluation shows the measured report and individual verdicts', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Evaluation', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Agent evaluation' })).toBeVisible()
  await expect(page.getByText(/50 of 50 cases passed/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Unsafe rejection' })).toBeVisible()
  await expect(page.getByText(/Cost per question not applicable/)).toBeVisible()
  await expect(page.getByRole('row')).toHaveCount(51)
})

test('mobile investigation fits the viewport and renders a trend', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Monthly trend' }).click()
  await expect(page.getByRole('heading', { name: 'On-time delivery rate', exact: true })).toBeVisible()
  await expect(page.locator('.recharts-surface').first()).toBeVisible()
  const overflows = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  expect(overflows).toBe(false)
})
