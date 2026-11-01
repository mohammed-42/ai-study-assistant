import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { signOut } = vi.hoisted(() => ({
  signOut: vi.fn(async () => ({ error: null })),
}))

vi.mock('./supabase', () => ({
  getAccessToken: vi.fn(async () => 'test-token'),
  createSupabaseClient: vi.fn(() => ({ auth: { signOut } })),
}))

import { apiFetch } from './api'

function jsonResponse(body: unknown, status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

describe('apiFetch error messages', () => {
  beforeEach(() => {
    signOut.mockClear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reports a readable network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(apiFetch('/subjects/')).rejects.toThrow(
      "Can't reach the server. Check your connection."
    )
  })

  it('joins 422 validation field messages', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: [
              { loc: ['body', 'title'], msg: 'Field required' },
              { loc: ['body', 'exam_date'], msg: 'Invalid date' },
            ],
          },
          422
        )
      )
    )

    await expect(apiFetch('/planner/plans')).rejects.toThrow(
      'title: Field required; exam_date: Invalid date'
    )
  })

  it('uses the backend detail for 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: 'Document not found or not owned' }, 404)
      )
    )

    await expect(apiFetch('/documents/123')).rejects.toThrow(
      'Document not found or not owned'
    )
  })

  it('uses the backend usage message for 429', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: 'Gemini daily limit reached. Try again tomorrow.' }, 429)
      )
    )

    await expect(apiFetch('/notes/generate')).rejects.toThrow(
      'Gemini daily limit reached. Try again tomorrow.'
    )
  })

  it('uses the backend availability message for 503', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: 'The tutor is busy. Please try again later.' }, 503)
      )
    )

    await expect(apiFetch('/chat/sessions/1/messages')).rejects.toThrow(
      'The tutor is busy. Please try again later.'
    )
  })

  it('hides server details for 500', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: 'Traceback: secret=abc123' }, 500)
      )
    )

    await expect(apiFetch('/planner/dashboard')).rejects.toThrow(
      'Something went wrong. Please try again.'
    )
  })

  it('signs out and reports an expired session for 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Invalid token' }, 401))
    )

    await expect(apiFetch('/subjects/')).rejects.toThrow(
      'Your session expired. Please sign in again.'
    )
    expect(signOut).toHaveBeenCalledTimes(1)
  })
})
