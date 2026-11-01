import { AppDocument, DocumentPage, DocumentChunk, ChatSession, ChatMessage, TutorRequest, Note, NoteCreate, Quiz, QuizAttempt, QuizSummary, QuizGenerateRequest, QuizSubmitRequest, StudyPlan, StudyPlanCreate, StudyPlanUpdate, StudyTask, StudyTaskUpdate, DashboardData, UserProfile } from '@/types'
import { createSupabaseClient, getAccessToken } from './supabase'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const NETWORK_ERROR = "Can't reach the server. Check your connection."
const SESSION_ERROR = 'Your session expired. Please sign in again.'
const GENERIC_ERROR = 'Something went wrong. Please try again.'

export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function validationMessages(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (!Array.isArray(detail)) return null

  const messages = detail
    .map((item) => {
      if (typeof item === 'string') return item
      if (!item || typeof item !== 'object') return null
      const entry = item as Record<string, unknown>
      const msg = typeof entry.msg === 'string' ? entry.msg : null
      if (!msg) return null
      const location = Array.isArray(entry.loc)
        ? entry.loc.filter((part) => part !== 'body').join('.')
        : ''
      return location ? `${location}: ${msg}` : msg
    })
    .filter((message): message is string => Boolean(message))

  return messages.length > 0 ? messages.join('; ') : null
}

function backendMessage(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null
  const record = body as Record<string, unknown>
  return validationMessages(record.detail) ?? (typeof record.message === 'string' ? record.message : null)
}

function messageForStatus(status: number, detail: string | null): string {
  if (status === 401) return SESSION_ERROR
  if (status === 403) return detail ?? "You don't have permission to do that."
  if (status === 404) return detail ?? 'The requested item was not found.'
  if (status === 422) return detail ?? 'Please check the form and try again.'
  if (status === 429) return detail ?? 'You have reached a usage limit. Please try again later.'
  if (status === 503) return detail ?? 'The service is temporarily unavailable. Please try again later.'
  if (status >= 500) return GENERIC_ERROR
  return detail ?? GENERIC_ERROR
}

async function handleUnauthorized() {
  try {
    await createSupabaseClient().auth.signOut()
  } catch {
    // Ignore sign-out failures; the redirect still clears the expired session view.
  }

  if (typeof window === 'undefined') return
  try {
    window.sessionStorage.setItem('auth_notice', SESSION_ERROR)
  } catch {
    // Storage may be unavailable in private browsing.
  }
  if (window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T | undefined> {
  let token: string | null = null
  try {
    token = await getAccessToken()
  } catch {
    token = null
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> || {}),
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    })
  } catch {
    throw new ApiError(NETWORK_ERROR)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    if (response.status === 401) {
      await handleUnauthorized()
    }
    throw new ApiError(messageForStatus(response.status, backendMessage(body)), response.status)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

// Profile APIs
export const profileApi = {
  get: () => apiFetch<UserProfile>('/profile'),
  update: (fullName: string) =>
    apiFetch<UserProfile>('/profile', {
      method: 'PUT',
      body: JSON.stringify({ full_name: fullName }),
    }),
  deleteAccount: () => apiFetch<void>('/account', { method: 'DELETE' }),
}

// Document APIs
export const documentApi = {
  list: (subjectId?: string, pagination?: { limit?: number; offset?: number }) => {
    const params = new URLSearchParams()
    if (subjectId) params.set('subject_id', subjectId)
    if (pagination?.limit !== undefined) params.set('limit', String(pagination.limit))
    if (pagination?.offset !== undefined) params.set('offset', String(pagination.offset))
    const query = params.toString()
    return apiFetch<AppDocument[]>(`/documents/${query ? `?${query}` : ''}`)
  },
  get: (id: string) => apiFetch<AppDocument>(`/documents/${id}`),
  delete: (id: string) => apiFetch<void>(`/documents/${id}`, { method: 'DELETE' }),
  retry: (id: string) => apiFetch<AppDocument>(`/documents/${id}/retry`, { method: 'POST' }),
  upload: async (files: File[], subjectId: string, docType: string) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    const token = await getAccessToken()
    const params = new URLSearchParams({ subject_id: subjectId, doc_type: docType })
    
    const response = await fetch(`${API_URL}/documents/upload?${params.toString()}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    })
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: response.statusText }))
      throw new Error(typeof error.detail === 'string' ? error.detail : (error.message || response.statusText))
    }
    return response.json() as Promise<AppDocument>
  },
  getPages: (id: string) => apiFetch<DocumentPage[]>(`/documents/${id}/pages`),
  getPageImageUrl: (docId: string, pageId: string) =>
    apiFetch<{ url: string; expires_in: number }>(
      `/documents/${docId}/pages/${pageId}/image-url`
    ),
  getChunks: (id: string) => apiFetch<DocumentChunk[]>(`/documents/${id}/chunks`),
  editPage: (docId: string, pageId: string, data: {
    text: string
    needs_review?: boolean
    user_edited?: boolean
  }) => apiFetch<DocumentPage>(`/documents/${docId}/pages/${pageId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  rerunPageOcr: (docId: string, pageId: string) =>
    apiFetch<DocumentPage>(`/documents/${docId}/pages/${pageId}/rerun-ocr`, {
      method: 'POST',
    }),
}

// Chat/Tutor APIs
export const chatApi = {
  listSessions: () => apiFetch<ChatSession[]>('/chat/sessions'),
  createSession: (data: { subject_id?: string; title?: string }) => 
    apiFetch<ChatSession>('/chat/sessions', { method: 'POST', body: JSON.stringify(data) }),
  deleteSession: (id: string) => apiFetch<void>(`/chat/sessions/${id}`, { method: 'DELETE' }),
  listMessages: (sessionId: string) => apiFetch<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
  sendMessage: (sessionId: string, data: TutorRequest) => 
    apiFetch<ChatMessage>(`/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Notes APIs
export const noteApi = {
  list: (subjectId?: string, documentId?: string) => {
    const params = new URLSearchParams()
    if (subjectId) params.set('subject_id', subjectId)
    if (documentId) params.set('document_id', documentId)
    const query = params.toString()
    return apiFetch<Note[]>(`/notes${query ? `?${query}` : ''}`)
  },
  get: (id: string) => apiFetch<Note>(`/notes/${id}`),
  create: (data: NoteCreate) => apiFetch<Note>('/notes', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<NoteCreate>) => apiFetch<Note>(`/notes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => apiFetch<void>(`/notes/${id}`, { method: 'DELETE' }),
  generate: (params: { subject_id?: string; document_id?: string; note_type?: string; title?: string }) => {
    const qs = new URLSearchParams()
    if (params.subject_id) qs.set('subject_id', params.subject_id)
    if (params.document_id) qs.set('document_id', params.document_id)
    if (params.note_type) qs.set('note_type', params.note_type)
    if (params.title) qs.set('title', params.title)
    const query = qs.toString()
    return apiFetch<Note>(`/notes/generate${query ? `?${query}` : ''}`, { method: 'POST' })
  },
}

// Quiz APIs
export const quizApi = {
  list: (subjectId?: string) => {
    const params = subjectId ? `?subject_id=${subjectId}` : ''
    return apiFetch<Quiz[]>(`/quizzes/${params}`)
  },
  get: (id: string) => apiFetch<Quiz>(`/quizzes/${id}`),
  generate: (data: QuizGenerateRequest) =>
    apiFetch<Quiz>('/quizzes/generate', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id: string) => apiFetch<void>(`/quizzes/${id}`, { method: 'DELETE' }),
  submit: (id: string, data: QuizSubmitRequest) =>
    apiFetch<QuizAttempt>(`/quizzes/${id}/submit`, { method: 'POST', body: JSON.stringify(data) }),
  getAttempts: (id: string) => apiFetch<QuizAttempt[]>(`/quizzes/${id}/attempts`),
  getSummary: (id: string) => apiFetch<QuizSummary>(`/quizzes/${id}/summary`),
}

// Planner APIs
export const plannerApi = {
  listPlans: () => apiFetch<StudyPlan[]>('/planner/plans'),
  getPlan: (id: string) => apiFetch<StudyPlan>(`/planner/plans/${id}`),
  createPlan: (data: StudyPlanCreate) =>
    apiFetch<StudyPlan>('/planner/plans', { method: 'POST', body: JSON.stringify(data) }),
  updatePlan: (id: string, data: StudyPlanUpdate) =>
    apiFetch<StudyPlan>(`/planner/plans/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePlan: (id: string) => apiFetch<void>(`/planner/plans/${id}`, { method: 'DELETE' }),
  generateSchedule: (planId: string) =>
    apiFetch<StudyTask[]>(`/planner/plans/${planId}/generate`, { method: 'POST' }),
  regenerateSchedule: (planId: string) =>
    apiFetch<StudyTask[]>(`/planner/plans/${planId}/regenerate`, { method: 'POST' }),
  updateTask: (taskId: string, data: StudyTaskUpdate) =>
    apiFetch<StudyTask>(`/planner/tasks/${taskId}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTask: (taskId: string) => apiFetch<void>(`/planner/tasks/${taskId}`, { method: 'DELETE' }),
  getDashboard: () => apiFetch<DashboardData>('/planner/dashboard'),
}
