import { randomBytes } from 'node:crypto'

import {
  BACKEND_URL,
  SUPABASE_ANON_KEY,
  SUPABASE_SERVICE_ROLE_KEY,
  SUPABASE_URL,
  assertE2EConfig,
} from './env'

export interface TestUser {
  id: string
  email: string
  password: string
}

function adminHeaders(): Record<string, string> {
  assertE2EConfig()
  return {
    apikey: SUPABASE_SERVICE_ROLE_KEY,
    Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
    'Content-Type': 'application/json',
  }
}

export function newCredentials(): { email: string; password: string } {
  const unique = randomBytes(6).toString('hex')
  return {
    email: `e2e.${Date.now()}.${unique}@example.com`,
    password: `E2e-${randomBytes(12).toString('base64url')}!9a`,
  }
}

export async function createTestUser(): Promise<TestUser> {
  const { email, password } = newCredentials()
  const response = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: 'POST',
    headers: adminHeaders(),
    body: JSON.stringify({
      email,
      password,
      email_confirm: true,
      user_metadata: { full_name: 'E2E User' },
    }),
  })
  if (!response.ok) {
    throw new Error(`Supabase admin create user failed with HTTP ${response.status}`)
  }
  const body = (await response.json()) as { id: string }
  return { id: body.id, email, password }
}

export async function findUserIdByEmail(email: string): Promise<string | null> {
  const target = email.toLowerCase()
  for (let page = 1; page <= 10; page += 1) {
    const response = await fetch(
      `${SUPABASE_URL}/auth/v1/admin/users?page=${page}&per_page=200`,
      { headers: adminHeaders() }
    )
    if (!response.ok) {
      throw new Error(`Supabase admin list users failed with HTTP ${response.status}`)
    }
    const body = (await response.json()) as {
      users?: Array<{ id: string; email?: string }>
    }
    const users = body.users ?? []
    const match = users.find((user) => (user.email ?? '').toLowerCase() === target)
    if (match) return match.id
    if (users.length < 200) break
  }
  return null
}

export async function signInAsUser(
  email: string,
  password: string
): Promise<{ accessToken: string; id: string } | null> {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_ANON_KEY,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) return null
  const body = (await response.json()) as {
    access_token?: string
    user?: { id?: string }
  }
  if (!body.access_token || !body.user?.id) return null
  return { accessToken: body.access_token, id: body.user.id }
}

async function confirmUser(id: string): Promise<void> {
  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${id}`, {
    method: 'PUT',
    headers: adminHeaders(),
    body: JSON.stringify({ email_confirm: true }),
  }).catch(() => undefined)
}

async function adminDeleteUser(id: string): Promise<void> {
  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${id}`, {
    method: 'DELETE',
    headers: adminHeaders(),
  }).catch(() => undefined)
}

export async function userExists(id: string): Promise<boolean> {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${id}`, {
    headers: adminHeaders(),
  })
  return response.ok
}

async function ensureProfile(user: TestUser): Promise<void> {
  let session = await signInAsUser(user.email, user.password)
  if (!session) {
    await confirmUser(user.id)
    session = await signInAsUser(user.email, user.password)
  }
  if (!session) {
    throw new Error('Could not sign in as the throwaway e2e user')
  }
  const response = await fetch(`${BACKEND_URL}/api/subjects/`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  })
  if (!response.ok) {
    throw new Error(`E2E profile provisioning failed with HTTP ${response.status}`)
  }
}

export async function provisionTestUser(user: TestUser): Promise<void> {
  await ensureProfile(user)
}

export async function waitForUserAndProvision(
  email: string,
  password: string,
  timeoutMs = 30_000
): Promise<string> {
  const deadline = Date.now() + timeoutMs
  let id: string | null = null
  while (Date.now() < deadline) {
    id = await findUserIdByEmail(email)
    if (id) break
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  if (!id) {
    throw new Error('Registered user did not appear in Supabase in time')
  }
  await ensureProfile({ id, email, password })
  return id
}

export async function deleteTestUser(user: TestUser): Promise<void> {
  let session = await signInAsUser(user.email, user.password)
  if (!session) {
    await confirmUser(user.id)
    session = await signInAsUser(user.email, user.password)
  }

  if (session) {
    await fetch(`${BACKEND_URL}/api/account`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${session.accessToken}` },
    }).catch(() => undefined)
  }

  if (await userExists(user.id)) {
    await adminDeleteUser(user.id)
  }
}
