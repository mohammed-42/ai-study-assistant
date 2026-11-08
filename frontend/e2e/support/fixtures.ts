import { test as base, expect } from '@playwright/test'

import {
  createTestUser,
  deleteTestUser,
  provisionTestUser,
  type TestUser,
} from './supabase-admin'

export interface ErrorTracker {
  consoleErrors: string[]
  failedRequests: string[]
  allowConsole: (pattern: RegExp) => void
}

export const test = base.extend<{ e2eUser: TestUser; errors: ErrorTracker }>({
  e2eUser: async ({}, use) => {
    const user = await createTestUser()
    try {
      await provisionTestUser(user)
      await use(user)
    } finally {
      await deleteTestUser(user)
    }
  },

  errors: [
    async ({ page }, use) => {
      const allowed: RegExp[] = []
      const consoleErrors: string[] = []
      const failedRequests: string[] = []

      page.on('console', (message) => {
        if (message.type() !== 'error') return
        const location = message.location().url || ''
        if (location.endsWith('/favicon.ico')) return
        const text = message.text()
        // React reports development-only warnings through console.error.
        if (text.startsWith('Warning: ')) return
        consoleErrors.push(text)
      })

      page.on('requestfailed', (request) => {
        const failure = request.failure()
        if (!failure) return
        if (failure.errorText === 'net::ERR_ABORTED') return
        failedRequests.push(
          `${request.method()} ${request.url()} - ${failure.errorText}`
        )
      })

      const tracker: ErrorTracker = {
        consoleErrors,
        failedRequests,
        allowConsole: (pattern) => allowed.push(pattern),
      }

      await use(tracker)

      const unexpectedConsole = consoleErrors.filter(
        (text) => !allowed.some((pattern) => pattern.test(text))
      )
      expect(
        unexpectedConsole,
        `Unexpected console errors:\n${unexpectedConsole.join('\n')}`
      ).toEqual([])
      expect(
        failedRequests,
        `Unexpected failed network requests:\n${failedRequests.join('\n')}`
      ).toEqual([])
    },
    { auto: true },
  ],
})

export { expect }
