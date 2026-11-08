const BACKEND_URL = process.env.E2E_BACKEND_URL || 'http://localhost:8000'
const FRONTEND_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'

async function reachable(url: string, expectedOk: boolean): Promise<boolean> {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(30_000) })
    return expectedOk ? response.status === 200 : response.status < 500
  } catch {
    return false
  }
}

export default async function globalSetup() {
  const backendOk = await reachable(`${BACKEND_URL}/api/health`, true)
  const frontendOk = await reachable(FRONTEND_URL, false)

  if (!backendOk || !frontendOk) {
    const problems: string[] = []
    if (!backendOk) problems.push(`backend health at ${BACKEND_URL}/api/health`)
    if (!frontendOk) problems.push(`frontend at ${FRONTEND_URL}`)
    throw new Error(
      `E2E servers unavailable: ${problems.join(' and ')}. ` +
        'This config does not start servers; start the backend on :8000 and the frontend on :5173 first. STOPPING.'
    )
  }
}
