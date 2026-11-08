import { test, expect } from './support/fixtures'
import { login, saveScreenshot } from './support/helpers'

test('unknown route shows the not-found page', async ({ page }) => {
  await page.goto('/this-route-does-not-exist')
  await expect(
    page.getByRole('heading', { name: 'Page not found', level: 1 })
  ).toBeVisible()
  await expect(page.getByRole('link', { name: 'Back to home' })).toBeVisible()
  await saveScreenshot(page, 'not-found')
})

test('/dashboard redirects to the dashboard', async ({ page, e2eUser }) => {
  await login(page, e2eUser)
  await page.goto('/dashboard')
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText('Your study overview.')).toBeVisible()
})
