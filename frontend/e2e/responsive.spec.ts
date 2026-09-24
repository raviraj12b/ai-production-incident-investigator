import { expect, test } from '@playwright/test'

import { installFixtureApi } from './fixtureApi'

test('keeps the investigation workspace usable at 320 CSS pixels', async ({ page }) => {
  await installFixtureApi(page)
  await page.goto('/investigations/investigation-e2e')

  await expect(page.getByRole('heading', { name: 'Chronological evidence timeline' })).toBeVisible()
  await expect(
    page
      .getByRole('list', { name: 'Evidence timeline' })
      .getByText('Fixture checkout requests returned HTTP 500.'),
  ).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)

  const menuButton = page.getByRole('button', { name: 'Open navigation' })
  await menuButton.click()
  const mobileNavigation = page.getByRole('complementary', { name: 'Mobile navigation panel' })
  const incidentsLink = mobileNavigation.getByRole('link', { name: 'Incidents' })
  await expect(incidentsLink).toBeFocused()
  await incidentsLink.press('Escape')
  await expect(mobileNavigation).toBeHidden()
  await expect(menuButton).toBeFocused()

  await page.getByLabel('Reviewer credential').fill('fixture-reviewer-secret')
  await page.getByLabel('Inconclusive').check()
  await page.getByRole('button', { name: 'Review decision' }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
  await expect(page.getByRole('button', { name: 'Submit immutable review' })).toBeVisible()
})
