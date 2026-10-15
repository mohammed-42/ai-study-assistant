export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T | undefined> {
  const token = localStorage.getItem('sb-auth-token') || sessionStorage.getItem('sb-auth-token')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> || {}),
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }))
    throw new Error(error.message || response.statusText)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}
