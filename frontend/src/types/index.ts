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
  embedding?: number[]
  created_at: string
}

export interface ChatSession {
  id: string
  owner_id: string
  subject_id: string | null
  title: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  citation_ids: string[] | null
  is_insufficient: boolean
  created_at: string
}

export interface TutorRequest {
  content: string
  session_id?: string
  subject_id?: string
  document_ids?: string[]
  top_k?: number
  min_similarity?: number
}

// Notes
export type NoteType = 'summary' | 'key_concepts' | 'definitions' | 'revision'

export interface Note {
  id: string
  owner_id: string
  subject_id: string | null
  document_id: string | null
  title: string
  note_type: NoteType
  content: string
  created_at: string
  updated_at: string
}

export interface NoteCreate {
  subject_id?: string
  document_id?: string
  title: string
  note_type: NoteType
  content: string
}

// Quizzes
export type QuizType = 'mcq' | 'short_answer' | 'mixed'
export type QuizDifficulty = 'easy' | 'medium' | 'hard'
export type QuizStatus = 'draft' | 'active'

export interface Quiz {
  id: string
  owner_id: string
  subject_id: string | null
  document_id: string | null
  title: string
  quiz_type: QuizType
  difficulty: QuizDifficulty
  question_count: number
  status: QuizStatus
  created_at: string
  updated_at: string
  questions?: QuizQuestion[]
}

export interface QuizQuestion {
  id: string
  quiz_id: string
  question_text: string
  question_type: 'mcq' | 'short_answer'
  options?: string[]
  correct_option_index?: number
  model_answer?: string
  document_id: string | null
  page_start: number | null
  page_end: number | null
  explanation: string | null
  order: number
  created_at: string
}

export interface QuizAttempt {
  id: string
  quiz_id: string
  user_id: string
  score: number | null
  total_questions: number
  correct_answers: number
  completed_at: string | null
  created_at: string
  responses: QuizResponse[]
}

export interface QuizResponse {
  question_id: string
  selected_option_index: number | null
  user_answer: string | null
  is_correct: boolean
  correct_option_index: number | null
  model_answer: string | null
  explanation: string | null
}

export interface QuizSummary {
  total_attempts: number
  average_score: number | null
  best_score: number | null
  recent_attempts: QuizAttempt[]
}

export interface QuizGenerateRequest {
  subject_id?: string
  document_id?: string
  title: string
  quiz_type: QuizType
  difficulty: QuizDifficulty
  question_count: number
}

export interface QuizSubmitRequest {
  responses: {
    question_id: string
    selected_option_index?: number
    user_answer?: string
  }[]
}
