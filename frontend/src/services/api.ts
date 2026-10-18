import { AppDocument, DocumentPage, DocumentChunk, ChatSession, ChatMessage, TutorRequest, Note, NoteCreate, Quiz, QuizAttempt, QuizSummary, QuizGenerateRequest, QuizSubmitRequest } from '@/types'

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

// Document APIs
export const documentApi = {
  list: (subjectId?: string) => {
    const params = subjectId ? `?subject_id=${subjectId}` : ''
    return apiFetch<AppDocument[]>(`/documents/${params}`)
  },
  get: (id: string) => apiFetch<AppDocument>(`/documents/${id}`),
  delete: (id: string) => apiFetch<void>(`/documents/${id}`, { method: 'DELETE' }),
  retry: (id: string) => apiFetch<AppDocument>(`/documents/${id}/retry`, { method: 'POST' }),
  upload: async (file: File, subjectId: string, docType: string) => {
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('sb-auth-token') || sessionStorage.getItem('sb-auth-token')
    
    const response = await fetch(`${API_URL}/documents/upload?subject_id=${subjectId}&doc_type=${docType}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    })
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: response.statusText }))
      throw new Error(error.message || response.statusText)
    }
    return response.json() as Promise<AppDocument>
  },
  getPages: (id: string) => apiFetch<DocumentPage[]>(`/documents/${id}/pages`),
  getChunks: (id: string) => apiFetch<DocumentChunk[]>(`/documents/${id}/chunks`),
  editPage: (docId: string, pageId: string, data: {
    text: string
    needs_review?: boolean
    user_edited?: boolean
  }) => apiFetch<DocumentPage>(`/documents/${docId}/pages/${pageId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
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
