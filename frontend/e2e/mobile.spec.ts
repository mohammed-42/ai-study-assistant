import { test, expect } from './support/fixtures'
import { login, saveScreenshot } from './support/helpers'

test.use({ viewport: { width: 390, height: 844 } })

test('phone viewport has no horizontal page scroll', async ({ page, e2eUser }) => {
  await login(page, e2eUser)

  const pages = [
    {
      path: '/',
      readyText: 'Your study overview.',
      screenshot: 'mobile-dashboard',
    },
    {
      path: '/documents',
      readyText: 'No documents yet',
      screenshot: 'mobile-documents',
    },
    {
      path: '/subjects',
      readyText: 'No subjects yet',
      screenshot: 'mobile-subjects',
    },
  ]

  for (const item of pages) {
    await page.goto(item.path)
    await expect(page.getByText(item.readyText)).toBeVisible()
    const widths = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(
      widths.scrollWidth,
      `horizontal page scroll on ${item.path}`
    ).toBeLessThanOrEqual(widths.clientWidth)
    await saveScreenshot(page, item.screenshot)
  }
})
