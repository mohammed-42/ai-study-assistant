import { test, expect } from './support/fixtures'
import { login, saveScreenshot, uniqueName } from './support/helpers'

test('settings saves the profile name', async ({ page, e2eUser }) => {
  await login(page, e2eUser)
  await page.goto('/settings')
  await expect(page.getByLabel('Email', { exact: true })).toHaveValue(e2eUser.email)
  await saveScreenshot(page, 'settings')

  const name = uniqueName('E2E Renamed')
  await page.getByLabel('Full name', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await expect(page.getByText('Profile updated')).toBeVisible()

  await page.reload()
  await expect(page.getByLabel('Full name', { exact: true })).toHaveValue(name)
})
