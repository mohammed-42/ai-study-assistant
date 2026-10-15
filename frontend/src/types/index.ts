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
    }
  }
}
