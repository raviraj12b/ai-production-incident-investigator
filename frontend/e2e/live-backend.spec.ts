import { expect, test } from '@playwright/test'

const liveEnabled = process.env.E2E_LIVE === '1'
test.use({ trace: 'off', screenshot: 'off', video: 'off' })

test.describe('live local backend and worker', () => {
  test.skip(!liveEnabled, 'Set E2E_LIVE=1 only after the complete local stack is ready.')

  test('runs incident intake through immutable review against the real stack', async ({
    page,
    request,
  }) => {
    test.setTimeout(Number(process.env.E2E_TIMEOUT_MS ?? 300_000))
    const reviewerCredential = process.env.E2E_REVIEWER_API_KEY
    if (!reviewerCredential) throw new Error('E2E_REVIEWER_API_KEY is required for the live test')

    const readiness = await request.get('/ready')
    expect(readiness.ok()).toBeTruthy()

    const suffix = Date.now()
    const end = new Date(Date.now() - 5 * 60_000)
    const start = new Date(end.getTime() - 10 * 60_000)
    await page.goto('/incidents/new')
    await page.getByLabel('Title').fill(`Live browser verification ${suffix}`)
    await page.getByLabel('Service').fill('incident-demo-api')
    await page.getByLabel('Severity').selectOption('HIGH')
    await page.getByLabel('Window start (your local timezone)').fill(localDateTime(start))
    await page.getByLabel('Window end (your local timezone)').fill(localDateTime(end))
    await page
      .getByLabel('Description (optional)')
      .fill('Created by the opt-in Phase 06.9 live Playwright workflow.')
    await page.getByRole('button', { name: 'Create incident' }).click()

    await expect(page).toHaveURL(/\/incidents\/[0-9a-f-]+$/)
    await page.getByLabel('Focus (optional)').fill('Verify the bounded live telemetry workflow')
    await page.getByRole('button', { name: 'Queue investigation' }).click()

    await expect(page).toHaveURL(/\/investigations\/[0-9a-f-]+$/)
    await expect(page.getByText('AWAITING REVIEW', { exact: true })).toBeVisible({
      timeout: Number(process.env.E2E_TIMEOUT_MS ?? 300_000),
    })
    await expect(page.getByRole('heading', { name: 'Report and hypotheses' })).toBeVisible()

    await page.getByLabel('Reviewer credential').fill(reviewerCredential)
    await page.getByLabel('Inconclusive').check()
    await page
      .getByLabel('Comment (optional)')
      .fill(`Live Phase 06.9 browser verification ${suffix}`)
    await page.getByRole('button', { name: 'Review decision' }).click()
    await page.getByRole('button', { name: 'Submit immutable review' }).click()

    await expect(page.getByText('Review completed')).toBeVisible()
    await expect(page.getByText('COMPLETED', { exact: true })).toBeVisible()
  })
})

function localDateTime(value: Date): string {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}
