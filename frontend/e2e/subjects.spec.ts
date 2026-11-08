import { test, expect } from './support/fixtures'
import { login, saveScreenshot, uniqueName } from './support/helpers'

test('create, open and delete a subject', async ({ page, e2eUser }) => {
  await login(page, e2eUser)
  await page.goto('/subjects')
  await expect(
    page.locator('#main-content').getByRole('heading', { name: 'Subjects', level: 1 })
  ).toBeVisible()
  await saveScreenshot(page, 'subjects-empty')

  const name = uniqueName('E2E Subject')

  await page
    .getByRole('button', { name: 'New Subject', exact: true })
    .first()
    .click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name', { exact: true }).fill(name)
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()
  await expect(page.getByRole('heading', { name })).toBeVisible()
  await saveScreenshot(page, 'subjects-created')

  await page.goto('/')
  await expect(page.getByText('Your study overview.')).toBeVisible()
  await page.getByRole('link', { name: 'View subject →' }).first().click()
  await expect(page).toHaveURL(/\/subjects\/[0-9a-f-]+$/i)
  await expect(page.getByText(name).first()).toBeVisible()
  await saveScreenshot(page, 'subject-detail')

  await page.goto('/subjects')
  page.once('dialog', (confirmation) => confirmation.accept())
  await page
    .getByRole('button', { name: `Delete subject ${name}`, exact: true })
    .click()
  await expect(page.getByRole('heading', { name })).toHaveCount(0)
})
