import { test, expect } from './support/fixtures'
import { login, saveScreenshot } from './support/helpers'
import {
  deleteTestUser,
  newCredentials,
  waitForUserAndProvision,
} from './support/supabase-admin'

test('register creates a new account', async ({ page }) => {
  const credentials = newCredentials()
  let id: string | null = null
  let release = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })

  try {
    // Hold the first authenticated requests until the test user's profile exists.
    // The app only provisions a profile on its first authenticated request.
    await page.route('**/api/**', async (route) => {
      await gate
      await route.continue()
    })

    await page.goto('/register')
    await expect(page.getByText('Create your account')).toBeVisible()
    await saveScreenshot(page, 'register')

    await page.getByLabel('Full name', { exact: true }).fill('E2E Register')
    await page.getByLabel('Email', { exact: true }).fill(credentials.email)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page
      .getByLabel('Confirm password', { exact: true })
      .fill(credentials.password)
    await page.getByRole('button', { name: 'Create account', exact: true }).click()

    await expect(page).not.toHaveURL(/\/register\/?$/)
    id = await waitForUserAndProvision(credentials.email, credentials.password)
    release()

    if (new URL(page.url()).pathname === '/login') {
      await page.getByLabel('Email', { exact: true }).fill(credentials.email)
      await page.getByLabel('Password', { exact: true }).fill(credentials.password)
      await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    }
    await expect(page.getByText('Your study overview.')).toBeVisible()
    await saveScreenshot(page, 'register-result')
  } finally {
    release()
    if (id) await deleteTestUser({ id, ...credentials })
  }
})

test('login rejects a wrong password, then logs in and out', async ({
  page,
  e2eUser,
  errors,
}) => {
  errors.allowConsole(/status of 400/)

  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill(e2eUser.email)
  await page.getByLabel('Password', { exact: true }).fill('Wrong-password-123!')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()

  await expect(page.getByText(/Invalid login credentials/i)).toBeVisible()
  await saveScreenshot(page, 'login-wrong-password')

  await page.getByLabel('Password', { exact: true }).fill(e2eUser.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByText('Your study overview.')).toBeVisible()
  await saveScreenshot(page, 'dashboard')

  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByText('Welcome back')).toBeVisible()
  await saveScreenshot(page, 'login-after-logout')
})
