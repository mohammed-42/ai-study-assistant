import { test, expect } from './support/fixtures'
import { login, saveScreenshot } from './support/helpers'

test('documents shows an error state with retry instead of the empty state', async ({
  page,
  e2eUser,
  errors,
}) => {
  errors.allowConsole(/status of 500/)

  await login(page, e2eUser)
  await page.route('**/api/documents**', (route) =>
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'internal error' }),
    })
  )

  await page.goto('/documents')
  await expect(page.getByText('Failed to load documents')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry', exact: true })).toBeVisible()
  await expect(page.getByText('No documents yet')).toBeHidden()
  await saveScreenshot(page, 'documents-error')
})

test('dashboard shows an error state with retry instead of the empty state', async ({
  page,
  e2eUser,
  errors,
}) => {
  errors.allowConsole(/status of 500/)

  await login(page, e2eUser)
  await page.route('**/api/planner/dashboard**', (route) =>
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'internal error' }),
    })
  )

  await page.reload()
  await expect(page.getByText('Could not load your dashboard')).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Retry loading dashboard', exact: true })
  ).toBeVisible()
  await expect(page.getByText('No upcoming exams.')).toBeHidden()
  await saveScreenshot(page, 'dashboard-error')
})
