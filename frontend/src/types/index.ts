export interface Subject {
  id: string
  owner_id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface SubjectCreate {
  name: string
  description?: string
}

export interface SubjectUpdate {
  name?: string
  description?: string
}

export interface UserProfile {
  id: string
  sub: string
  email: string
  full_name: string | null
  created_at: string
  updated_at: string
}

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: UserProfile
        Insert: Omit<UserProfile, 'id' | 'created_at' | 'updated_at'>
        Update: Partial<Omit<UserProfile, 'id' | 'created_at'>>
      }
      subjects: {
        Row: Subject
        Insert: Omit<Subject, 'id' | 'owner_id' | 'created_at' | 'updated_at'>
        Update: Partial<Omit<Subject, 'id' | 'owner_id' | 'created_at' | 'updated_at'>>
      }
      documents: {
        Row: AppDocument
        Insert: Omit<AppDocument, 'id' | 'owner_id' | 'created_at' | 'updated_at'>
        Update: Partial<Omit<AppDocument, 'id' | 'owner_id' | 'created_at' | 'updated_at'>>
      }
    }
  }
}

export type DocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed'

export interface AppDocument {
  id: string
  owner_id: string
  subject_id: string
  name: string
  doc_type: 'pdf' | 'image' | 'multi_image'
  status: DocumentStatus
  page_count: number
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface DocumentPage {
  id: string
  document_id: string
  page_number: number
  text: string
  source: 'text_layer' | 'ocr'
  needs_review: boolean
  user_edited: boolean
  page_image_key: string | null
  created_at: string
  updated_at: string
}

export interface DocumentChunk {
  id: string
  document_id: string
  page_start: number
  page_end: number
  content: string
  token_count: number
  created_at: string
}
