import fs from 'node:fs'
import path from 'node:path'

function readEnvFile(filePath: string): Record<string, string> {
  if (!fs.existsSync(filePath)) return {}
  const values: Record<string, string> = {}
  for (const line of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/)
    if (!match) continue
    let value = match[2]!.trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    values[match[1]!] = value
  }
  return values
}

const backendEnv = readEnvFile(path.resolve(process.cwd(), '../backend/.env'))

function env(name: string): string {
  return process.env[name] ?? backendEnv[name] ?? ''
}

export const BACKEND_URL = process.env.E2E_BACKEND_URL || 'http://localhost:8000'
export const FRONTEND_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'

export const SUPABASE_URL = env('SUPABASE_URL').replace(/\/+$/, '')
export const SUPABASE_ANON_KEY = env('SUPABASE_ANON_KEY')
export const SUPABASE_SERVICE_ROLE_KEY = env('SUPABASE_SERVICE_ROLE_KEY')

export function assertE2EConfig(): void {
  const missing: string[] = []
  if (!SUPABASE_URL) missing.push('SUPABASE_URL')
  if (!SUPABASE_ANON_KEY) missing.push('SUPABASE_ANON_KEY')
  if (!SUPABASE_SERVICE_ROLE_KEY) missing.push('SUPABASE_SERVICE_ROLE_KEY')
  if (missing.length > 0) {
    throw new Error(
      `Missing Supabase admin configuration for e2e tests: ${missing.join(', ')}. ` +
        'Set these in backend/.env (server-side only; never exposed to the browser).'
    )
  }
}
