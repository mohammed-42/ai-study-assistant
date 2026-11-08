import fs from 'node:fs'
import path from 'node:path'

import { expect, type Page } from '@playwright/test'

import type { TestUser } from './supabase-admin'

export async function login(page: Page, user: TestUser): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill(user.email)
  await page.getByLabel('Password', { exact: true }).fill(user.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByText('Your study overview.')).toBeVisible()
}

export async function saveScreenshot(page: Page, name: string): Promise<void> {
  const directory = path.resolve(process.cwd(), 'e2e/screenshots')
  fs.mkdirSync(directory, { recursive: true })
  await page.screenshot({
    path: path.join(directory, `${name}.png`),
    fullPage: true,
  })
}

export function uniqueName(prefix: string): string {
  return `${prefix} ${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}
