import { test, expect } from './support/fixtures'
import { login, saveScreenshot } from './support/helpers'

test('dashboard shows empty states for a new user', async ({ page, e2eUser }) => {
  await login(page, e2eUser)

  await expect(page.getByText('No upcoming exams.')).toBeVisible()
  await expect(page.getByText('No tasks scheduled for today.')).toBeVisible()
  await expect(page.getByText('No materials uploaded yet.')).toBeVisible()
  await expect(page.getByText('No quiz attempts yet.')).toBeVisible()
  await expect(page.getByText('No study plan progress yet.')).toBeVisible()
  await expect(page.getByText('No subjects yet')).toBeVisible()

  await saveScreenshot(page, 'dashboard-empty')
})
