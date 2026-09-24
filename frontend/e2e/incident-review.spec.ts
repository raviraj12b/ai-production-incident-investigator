import { expect, test } from '@playwright/test'

import { installFixtureApi } from './fixtureApi'

test('creates an incident and completes its evidence-backed review', async ({ page }) => {
  const captures = await installFixtureApi(page)

  await page.goto('/incidents/new')
  await page.getByLabel('Title').fill('Checkout fixture incident')
  await page.getByLabel('Service').fill('checkout-api')
  await page.getByLabel('Severity').selectOption('HIGH')
  await page.getByLabel('Window start (your local timezone)').fill('2026-09-21T10:00')
  await page.getByLabel('Window end (your local timezone)').fill('2026-09-21T10:30')
  await page.getByLabel('Description (optional)').fill('Fixture-driven browser workflow.')
  await page.getByRole('button', { name: 'Create incident' }).click()

  await expect(page).toHaveURL(/\/incidents\/incident-e2e$/)
  await expect(
    page.getByRole('heading', { level: 1, name: 'Checkout fixture incident' }),
  ).toBeVisible()
  expect(captures.incidentIdempotencyKey).toBeTruthy()
  expect(captures.incidentBody?.service).toBe('checkout-api')
  expect(Date.parse(String(captures.incidentBody?.window_end))).toBeGreaterThan(
    Date.parse(String(captures.incidentBody?.window_start)),
  )

  await page.getByLabel('Focus (optional)').fill('Checkout errors during fixture window')
  await page.getByRole('button', { name: 'Queue investigation' }).click()

  await expect(page).toHaveURL(/\/investigations\/investigation-e2e$/)
  await expect(page.getByText('AWAITING REVIEW', { exact: true })).toBeVisible()
  expect(captures.investigationIdempotencyKey).toBeTruthy()
  expect(captures.investigationBody).toEqual({ focus: 'Checkout errors during fixture window' })

  await expect(
    page
      .getByRole('list', { name: 'Evidence timeline' })
      .getByText('Fixture checkout requests returned HTTP 500.'),
  ).toBeVisible()
  await expect(
    page.getByText('Fixture evidence shows elevated checkout errors during the incident window.'),
  ).toBeVisible()
  await expect(page.getByText('Supporting evidence')).toBeVisible()
  await expect(page.getByText('CHANGE_FEED_NOT_CONFIGURED').first()).toBeVisible()

  await page.getByLabel('Reviewer credential').fill('fixture-reviewer-secret')
  await page.getByLabel('Accepted').check()
  await page.getByLabel('Comment (optional)').fill('Fixture evidence supports this review.')
  await page.getByRole('button', { name: 'Review decision' }).click()
  await page.getByRole('button', { name: 'Submit immutable review' }).click()

  await expect(page.getByText('Review completed')).toBeVisible()
  await expect(page.getByText('COMPLETED', { exact: true })).toBeVisible()
  expect(captures.reviewAuthorization).toBe('Bearer fixture-reviewer-secret')
  expect(captures.reviewBody).toEqual({
    decision: 'ACCEPTED',
    comment: 'Fixture evidence supports this review.',
  })
})
