import { AppDocument, DocumentPage, DocumentChunk } from '@/types'

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
}
